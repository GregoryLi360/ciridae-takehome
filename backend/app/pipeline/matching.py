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
You are comparing line items from two construction repair proposals for the same room.
Match items from the JDR (contractor) list to items from the Insurance list that refer to the same work.

Rules:
- Match items that describe the same type of work, even if wording differs (e.g. "Bathtub - Reset" ↔ "Install Bathtub", "Carpet pad" ↔ "Carpet pad - per specs from independent pad analysis").
- Each item can appear in at most one match. Do not double-match.
- Only match items you are confident refer to the same scope of work. Leave items unmatched if unsure.
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


def _match_room_items(
    jdr_items: list[ExtractedLineItem],
    ins_items: list[ExtractedLineItem],
) -> tuple[list[MatchedPair], list[ExtractedLineItem], list[ExtractedLineItem]]:
    if not jdr_items or not ins_items:
        return [], list(jdr_items), list(ins_items)

    user_msg = (
        f"JDR items ({len(jdr_items)}):\n{_format_item_list(jdr_items)}\n\n"
        f"Insurance items ({len(ins_items)}):\n{_format_item_list(ins_items)}"
    )
    result = chat(MATCHING_PROMPT, user_msg, _RoomMatches)

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

        matched, unmatched_jdr, unmatched_ins = _match_room_items(group_jdr_items, group_ins_items)

        comparisons.append(RoomComparison(
            jdr_rooms=group.jdr_rooms,
            ins_rooms=group.ins_rooms,
            matched=matched,
            unmatched_jdr=unmatched_jdr,
            unmatched_ins=unmatched_ins,
        ))

    return ComparisonResult(rooms=comparisons)
