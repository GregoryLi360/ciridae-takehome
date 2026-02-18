from decimal import Decimal

from pydantic import BaseModel

from ..llm import chat
from ..schemas import (
    ComparisonResult,
    DiffNote,
    ExtractedLineItem,
    MatchColor,
    MatchedPair,
    ParsedDocument,
    RoomComparison,
)
from .room_mapping import RoomGroup, map_rooms


class _ItemMatch(BaseModel):
    jdr_index: int
    ins_index: int


class _RoomMatches(BaseModel):
    matches: list[_ItemMatch]


MATCHING_PROMPT = """\
You are comparing line items from two construction repair proposals for the same job.
Match items from the JDR (contractor) list to items from the Insurance list that refer to the same work.

Rules:
- Match items that describe the same type of work, even if wording differs significantly.
- Each item can appear in at most one match. Do not double-match.
- When two JDR items could match the same insurance item, prefer the one whose units/quantities \
are more compatible (e.g. both in SF rather than LF vs SF).
- Match items even when methodology or materials differ if they serve the same purpose:
  - "Mortar bed for tile floors" ↔ "Floor leveling cement" (both floor prep for tile)
  - "Concrete grinding" ↔ "Floor leveling cement" (both substrate preparation)
  - "Tile tub surround - 60 to 75 SF" ↔ "Ceramic/porcelain tile (Tub Surround)"
  - "Tandem axle dump trailer" ↔ "Haul debris - per pickup truck load" (both debris removal)
  - "Content Manipulation (Bid Item)" ↔ "Contents - move out then reset" (both content handling)
  - "Seal/prime (1 coat) then paint (2 coats)" ↔ "Paint the walls - one coat" (both wall painting)
  - "Seal (1 coat) & paint (1 coat) baseboard" ↔ "Paint baseboard - one coat" (both baseboard painting)
  - "R&R Carpet pad" ↔ "Carpet pad - per specs from independent pad analysis"
- Match even if quantities or pricing differ substantially — classification handles that separately.
- Only leave items unmatched if you cannot identify any corresponding work on the other side.
- Return indices as 0-based integers referring to the numbered lists provided."""


SECONDARY_MATCHING_PROMPT = """\
You are reviewing unmatched JDR line items from a construction repair proposal.
These items were not matched in a first pass. Some may partially overlap in scope with \
insurance items that were already matched to other JDR items.

For each unmatched JDR item, check if it describes work that partially overlaps with any \
of the insurance items listed. A partial overlap means the insurance item covers some of \
the same work but not all (e.g. "Door hinges (set of 3) and slab - Detach & reset" \
partially overlaps "Interior door - Reset - slab only" because the door reset is covered \
but the hinge work is not).

Rules:
- Only match when there is genuine scope overlap, not just same room/trade.
- An insurance item CAN be matched multiple times here (this is a secondary pass).
- Return indices as 0-based integers referring to the numbered lists provided."""


def _within_tolerance(a: Decimal | None, b: Decimal | None, pct: float = 0.02) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if a == 0 and b == 0:
        return True
    if a == 0 or b == 0:
        return False
    return abs(float(a - b) / float(a)) <= pct


def _classify_pair(jdr: ExtractedLineItem, ins: ExtractedLineItem) -> tuple[MatchColor, list[DiffNote]]:
    diffs: list[DiffNote] = []

    units_match = (jdr.unit or "").strip().upper() == (ins.unit or "").strip().upper()

    if not units_match:
        # Units differ — quantity and unit_price are incomparable across
        # different measurement systems (e.g. LF vs SF, HR vs EA).
        # Flag the unit difference and compare totals instead.
        diffs.append(DiffNote(field="unit", jdr_value=str(jdr.unit or ""), ins_value=str(ins.unit or "")))
        if not _within_tolerance(jdr.total, ins.total):
            diffs.append(DiffNote(field="total", jdr_value=str(jdr.total or ""), ins_value=str(ins.total or "")))
    else:
        if not _within_tolerance(jdr.quantity, ins.quantity):
            diffs.append(DiffNote(field="quantity", jdr_value=str(jdr.quantity or ""), ins_value=str(ins.quantity or "")))

        if not _within_tolerance(jdr.unit_price, ins.unit_price):
            diffs.append(DiffNote(field="unit_price", jdr_value=str(jdr.unit_price or ""), ins_value=str(ins.unit_price or "")))

    color = MatchColor.GREEN if not diffs else MatchColor.ORANGE
    return color, diffs


def _format_item_list(items: list[ExtractedLineItem]) -> str:
    lines = []
    for i, item in enumerate(items):
        qty = f"{item.quantity}" if item.quantity is not None else "?"
        unit = item.unit or "?"
        price = f"${item.unit_price}" if item.unit_price is not None else "$?"
        lines.append(f"  [{i}] {item.description} | qty={qty} {unit} | price={price}")
    return "\n".join(lines)


def _match_items_llm(
    jdr_items: list[ExtractedLineItem],
    ins_items: list[ExtractedLineItem],
    prompt: str = MATCHING_PROMPT,
) -> tuple[list[MatchedPair], list[ExtractedLineItem], list[ExtractedLineItem]]:
    """Run LLM matching and return matched pairs + leftovers."""
    if not jdr_items or not ins_items:
        return [], list(jdr_items), list(ins_items)

    user_msg = (
        f"JDR items ({len(jdr_items)}):\n{_format_item_list(jdr_items)}\n\n"
        f"Insurance items ({len(ins_items)}):\n{_format_item_list(ins_items)}"
    )
    result = chat(prompt, user_msg, _RoomMatches)

    matched_pairs: list[MatchedPair] = []
    matched_jdr_idx: set[int] = set()
    matched_ins_idx: set[int] = set()

    for m in result.matches:
        if (
            0 <= m.jdr_index < len(jdr_items)
            and 0 <= m.ins_index < len(ins_items)
            and m.jdr_index not in matched_jdr_idx
            and m.ins_index not in matched_ins_idx
        ):
            color, diffs = _classify_pair(jdr_items[m.jdr_index], ins_items[m.ins_index])
            matched_pairs.append(MatchedPair(
                jdr_item=jdr_items[m.jdr_index],
                ins_item=ins_items[m.ins_index],
                color=color,
                diff_notes=diffs,
            ))
            matched_jdr_idx.add(m.jdr_index)
            matched_ins_idx.add(m.ins_index)

    unmatched_jdr = [item for i, item in enumerate(jdr_items) if i not in matched_jdr_idx]
    unmatched_ins = [item for j, item in enumerate(ins_items) if j not in matched_ins_idx]

    return matched_pairs, unmatched_jdr, unmatched_ins


def compare_documents(jdr: ParsedDocument, ins: ParsedDocument) -> ComparisonResult:
    jdr_room_names = [r.room_name for r in jdr.rooms]
    ins_room_names = [r.room_name for r in ins.rooms]
    room_groups: list[RoomGroup] = map_rooms(jdr_room_names, ins_room_names)

    jdr_rooms = {r.room_name: r for r in jdr.rooms}
    ins_rooms = {r.room_name: r for r in ins.rooms}

    # Track rooms with no insurance counterpart for global fallback
    orphan_jdr_items: list[ExtractedLineItem] = []

    comparisons: list[RoomComparison] = []
    for group in room_groups:
        group_jdr_items: list[ExtractedLineItem] = []
        for rn in group.jdr_rooms:
            if rn in jdr_rooms:
                group_jdr_items.extend(jdr_rooms[rn].line_items)

        group_ins_items: list[ExtractedLineItem] = []
        for rn in group.ins_rooms:
            if rn in ins_rooms:
                group_ins_items.extend(ins_rooms[rn].line_items)

        # If no insurance counterpart, defer items to global fallback
        if group_jdr_items and not group_ins_items:
            orphan_jdr_items.extend(group_jdr_items)
            comparisons.append(RoomComparison(
                jdr_rooms=group.jdr_rooms,
                ins_rooms=group.ins_rooms,
                matched=[],
                unmatched_jdr=group_jdr_items,
                unmatched_ins=[],
            ))
            continue

        matched, unmatched_jdr, unmatched_ins = _match_items_llm(
            group_jdr_items, group_ins_items,
        )

        comparisons.append(RoomComparison(
            jdr_rooms=group.jdr_rooms,
            ins_rooms=group.ins_rooms,
            matched=matched,
            unmatched_jdr=unmatched_jdr,
            unmatched_ins=unmatched_ins,
        ))

    # ── Phase 2: Global fallback for orphan rooms only ──
    # Only items from JDR rooms with NO insurance counterpart get a second
    # chance to match against all remaining unmatched insurance items.
    if orphan_jdr_items:
        all_unmatched_ins: list[ExtractedLineItem] = []
        for comp in comparisons:
            all_unmatched_ins.extend(comp.unmatched_ins)

        if all_unmatched_ins:
            global_matched, still_unmatched_jdr, still_unmatched_ins = _match_items_llm(
                orphan_jdr_items, all_unmatched_ins,
            )
            if global_matched:
                newly_matched_jdr = {id(p.jdr_item) for p in global_matched}
                newly_matched_ins = {id(p.ins_item) for p in global_matched}

                # Remove newly matched items from their original room comparisons
                for comp in comparisons:
                    comp.unmatched_jdr = [
                        it for it in comp.unmatched_jdr if id(it) not in newly_matched_jdr
                    ]
                    comp.unmatched_ins = [
                        it for it in comp.unmatched_ins if id(it) not in newly_matched_ins
                    ]

                # Add global matches to a cross-room comparison group
                comparisons.append(RoomComparison(
                    jdr_rooms=["(cross-room)"],
                    ins_rooms=["(cross-room)"],
                    matched=global_matched,
                    unmatched_jdr=[],
                    unmatched_ins=[],
                ))

    return ComparisonResult(rooms=comparisons)
