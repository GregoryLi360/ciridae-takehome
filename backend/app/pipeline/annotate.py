"""Step 4 — Annotated PDF generation using PyMuPDF.

Opens the original JDR PDF, draws colored highlights over per-field bboxes,
adds sticky-note annotations with LLM-generated rationale, and appends
summary pages for insurance-only (nugget) items.
"""

from concurrent.futures import ThreadPoolExecutor

import fitz
from pydantic import BaseModel

from ..llm import chat
from ..schemas import (
    ComparisonResult,
    ExtractedLineItem,
    MatchColor,
    MatchedPair,
    RoomComparison,
)

_LLM_POOL = ThreadPoolExecutor(max_workers=8)

# Highlight colors (RGB 0-1) — match the ground truth markup palette
HIGHLIGHT_COLORS: dict[MatchColor, tuple[float, float, float]] = {
    MatchColor.GREEN: (0.0, 1.0, 0.0),       # #00ff00
    MatchColor.ORANGE: (1.0, 0.5, 0.0),       # #ff7f00
    MatchColor.BLUE: (0.5, 0.8, 1.0),         # #7fccff  (sky blue)
}


# --- LLM comment generation ---

COMMENT_PROMPT = """\
You are writing annotations for a JDR (contractor) repair proposal being compared against an insurance adjuster's estimate for the same property damage.

For each item below, write a concise comment (1-3 sentences) explaining the comparison result:

- GREEN items: Confirm the match. Note any negligible pricing differences.
- ORANGE items: Explain the specific differences (quantity, unit, pricing, scope). Reference the insurance item details. Note implications for reimbursement.
- BLUE items: Explain that the adjuster's estimate does not include this item. If a related insurance-only item exists, mention it. Note whether this should be discussed with the adjuster.

Be specific — reference actual quantities, prices, and descriptions from both sides. Write from the perspective of advising the JDR contractor."""


class _ItemComment(BaseModel):
    comment: str


class _RoomComments(BaseModel):
    comments: list[_ItemComment]


def _format_item(item: ExtractedLineItem) -> str:
    qty = f"{item.quantity} {item.unit or ''}" if item.quantity else "—"
    price = f"${item.unit_price}" if item.unit_price else "—"
    total = f"${item.total}" if item.total else "—"
    return f"{item.description} | qty={qty} | price={price} | total={total}"


def _generate_comments(room: RoomComparison) -> list[str]:
    """Call LLM to generate rationale comments for all highlighted items in a room."""
    items_parts: list[str] = []

    for i, pair in enumerate(room.matched):
        label = "GREEN" if pair.color == MatchColor.GREEN else "ORANGE"
        line = f"[{i + 1}] ({label}) JDR: {_format_item(pair.jdr_item)}"
        line += f"\n     Insurance: {_format_item(pair.ins_item)}"
        if pair.diff_notes:
            diffs = "; ".join(f"{d.field}: JDR={d.jdr_value} vs INS={d.ins_value}" for d in pair.diff_notes)
            line += f"\n     Differences: {diffs}"
        items_parts.append(line)

    offset = len(room.matched)
    for i, item in enumerate(room.unmatched_jdr):
        line = f"[{offset + i + 1}] (BLUE) JDR: {_format_item(item)}"
        items_parts.append(line)

    if not items_parts:
        return []

    nuggets = "\n".join(
        f"  - {_format_item(item)}" for item in room.unmatched_ins
    ) or "(none)"

    jdr_label = room.jdr_room or "(none)"
    ins_label = room.ins_room or "(none)"
    room_label = f"JDR: {jdr_label} ↔ Insurance: {ins_label}"

    user_msg = (
        f"Room: {room_label}\n\n"
        f"Items to annotate ({len(items_parts)} total):\n"
        + "\n".join(items_parts)
        + f"\n\nInsurance-only items in this room (for context):\n{nuggets}\n\n"
        f"Return exactly {len(items_parts)} comments, one per item, in order."
    )

    total = len(items_parts)
    result = chat(COMMENT_PROMPT, user_msg, _RoomComments)

    comments = [c.comment for c in result.comments]
    # Pad or truncate to match expected count
    while len(comments) < total:
        comments.append("")
    return comments[:total]


def _highlight_rect(page: fitz.Page, rect: fitz.Rect, color: tuple[float, float, float]) -> None:
    """Add a highlight annotation over a single rect."""
    if rect.is_empty or rect.is_infinite or rect.width < 1 or rect.height < 1:
        return
    annot = page.add_highlight_annot(rect)
    annot.set_colors(stroke=color)
    annot.update()



def _get_description_rects(
    page: fitz.Page,
    item: ExtractedLineItem,
) -> list[fitz.Rect]:
    """Get highlight rects for the item's description.

    The stored bbox (from word-level matching in parse.py) already covers
    the full description including multi-line text. We split it into
    per-line rects for proper highlight rendering.
    """
    desc_bbox = item.bboxes.description
    if desc_bbox is None:
        return []

    full_rect = fitz.Rect(desc_bbox)
    line_height = 11  # approximate line height in points

    # If the bbox spans multiple lines, split into per-line rects
    # using the page's text dict for precise line boundaries
    if full_rect.height > line_height * 1.5:
        rects = []
        try:
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                for line in block.get("lines", []):
                    lr = fitz.Rect(line["bbox"])
                    # Check if this text line overlaps with our description bbox
                    if lr.intersects(full_rect) and lr.y0 >= full_rect.y0 - 2:
                        # Clip to description x-range
                        rects.append(fitz.Rect(
                            max(lr.x0, full_rect.x0),
                            lr.y0,
                            min(lr.x1, full_rect.x1),
                            lr.y1,
                        ))
        except Exception:
            pass
        if rects:
            return rects

    return [full_rect]


def _add_note(page: fitz.Page, point: fitz.Point, text: str) -> None:
    """Add a sticky-note annotation at the given point."""
    annot = page.add_text_annot(point, text, icon="Comment")
    annot.update()


def _annotate_item(
    page: fitz.Page,
    item: ExtractedLineItem,
    color: MatchColor,
    comment: str,
) -> None:
    """Highlight an item's description (one color) and add a sticky note."""
    rects = _get_description_rects(page, item)
    if not rects:
        return

    rgb = HIGHLIGHT_COLORS[color]
    for rect in rects:
        _highlight_rect(page, rect, rgb)

    # Place sticky note to the right of the first description rect
    if comment:
        first = rects[0]
        _add_note(page, fitz.Point(first.x1 + 2, first.y0), comment)


def _last_jdr_page(room: RoomComparison) -> int | None:
    """Return the 0-based page index of the last JDR item in a room."""
    pages: list[int] = []
    for pair in room.matched:
        pages.append(pair.jdr_item.page_number)
    for item in room.unmatched_jdr:
        pages.append(item.page_number)
    return max(pages) - 1 if pages else None


def _add_nugget_notes(
    page: fitz.Page,
    items: list[ExtractedLineItem],
    room_name: str | None = None,
) -> None:
    """Place sticky-note annotations for insurance-only items at the page bottom-right."""
    x = page.rect.width - 40
    y = page.rect.height - 50
    room_prefix = f"[{room_name}] " if room_name else ""
    for item in reversed(items):
        total_str = f"${float(item.total):,.2f}" if item.total else "—"
        qty_str = f"{item.quantity} {item.unit or ''}" if item.quantity else ""
        text = f"{room_prefix}[Insurance only] {item.description}"
        if qty_str:
            text += f"\nQty: {qty_str}"
        text += f"\nTotal: {total_str}"
        _add_note(page, fitz.Point(x, y), text)
        y -= 20


def annotate_pdf(
    jdr_pdf_path: str,
    result: ComparisonResult,
    output_path: str,
) -> str:
    """Generate an annotated copy of the JDR PDF with comparison highlights.

    - GREEN highlights: exact match with insurance
    - ORANGE highlights: matched but with field differences
    - BLUE highlights: JDR only, no insurance match
    - Nugget sticky notes: insurance-only items placed at bottom-right of
      each room's last JDR page (no highlights)
    """
    doc = fitz.open(jdr_pdf_path)

    # Step 1: Parallel comment generation (LLM calls, no fitz)
    rooms_with_items: list[tuple[int, RoomComparison]] = []
    for i, room in enumerate(result.rooms):
        n_items = len(room.matched) + len(room.unmatched_jdr)
        if n_items > 0:
            rooms_with_items.append((i, room))

    def _gen_comments(args: tuple[int, RoomComparison]) -> list[str]:
        _, room = args
        room_label = room.jdr_room or "(none)"
        n_items = len(room.matched) + len(room.unmatched_jdr)
        print(f"  Generating comments for {room_label} ({n_items} items)...", flush=True)
        return _generate_comments(room)

    all_comments = list(_LLM_POOL.map(_gen_comments, rooms_with_items))
    comments_by_idx = {i: c for (i, _), c in zip(rooms_with_items, all_comments)}

    # Step 2: Sequential highlight application (fitz not thread-safe)
    for room_idx, room in enumerate(result.rooms):
        n_items = len(room.matched) + len(room.unmatched_jdr)
        if n_items == 0:
            # Room has only insurance items — place nugget notes on the
            # first page as a fallback (rare with 1:1 mapping).
            if room.unmatched_ins:
                _add_nugget_notes(doc[0], room.unmatched_ins, room.ins_room or room.jdr_room)
            continue

        comments = comments_by_idx.get(room_idx, [])

        for i, pair in enumerate(room.matched):
            page_idx = pair.jdr_item.page_number - 1
            if 0 <= page_idx < len(doc):
                _annotate_item(
                    doc[page_idx], pair.jdr_item, pair.color,
                    comments[i],
                )

        offset = len(room.matched)
        for i, item in enumerate(room.unmatched_jdr):
            page_idx = item.page_number - 1
            if 0 <= page_idx < len(doc):
                _annotate_item(
                    doc[page_idx], item, MatchColor.BLUE,
                    comments[offset + i],
                )

        if room.unmatched_ins:
            page_idx = _last_jdr_page(room)
            if page_idx is not None and 0 <= page_idx < len(doc):
                _add_nugget_notes(doc[page_idx], room.unmatched_ins, room.ins_room or room.jdr_room)

    doc.save(output_path)
    doc.close()
    return output_path
