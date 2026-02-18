"""Step 4 — Annotated PDF generation using PyMuPDF.

Opens the original JDR PDF, draws colored highlights over per-field bboxes,
adds sticky-note annotations with LLM-generated rationale, and appends
summary pages for insurance-only (nugget) items.
"""

import re

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

# Highlight colors (RGB 0-1) — match the ground truth markup palette
HIGHLIGHT_COLORS: dict[MatchColor, tuple[float, float, float]] = {
    MatchColor.GREEN: (0.0, 1.0, 0.0),       # #00ff00
    MatchColor.ORANGE: (1.0, 0.5, 0.0),       # #ff7f00
    MatchColor.BLUE: (0.5, 0.8, 1.0),         # #7fccff  (sky blue)
    MatchColor.NUGGET: (0.75, 0.52, 1.0),     # purple
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

    room_label = f"JDR rooms: {', '.join(room.jdr_rooms)} ↔ Insurance rooms: {', '.join(room.ins_rooms)}"

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


def _append_nugget_summary(
    doc: fitz.Document,
    nugget_groups: list[tuple[list[str], list[str], list[ExtractedLineItem]]],
) -> None:
    """Append summary page(s) listing insurance-only items by room."""
    W, H = 612, 792  # Letter size
    MARGIN = 50
    LINE_H = 14

    page = doc.new_page(width=W, height=H)
    y = MARGIN

    # Title
    page.insert_text(
        fitz.Point(MARGIN, y + 18),
        "Insurance-Only Items (Not in JDR Proposal)",
        fontsize=14,
        fontname="hebo",
        color=(0.5, 0.3, 0.8),
    )
    y += 40

    for jdr_rooms, ins_rooms, items in nugget_groups:
        if y > H - MARGIN - 40:
            page = doc.new_page(width=W, height=H)
            y = MARGIN

        room_label = ", ".join(ins_rooms) or ", ".join(jdr_rooms)
        page.insert_text(
            fitz.Point(MARGIN, y + LINE_H),
            room_label,
            fontsize=11,
            fontname="hebo",
            color=(0.2, 0.2, 0.2),
        )
        y += LINE_H + 8

        for item in items:
            if y > H - MARGIN:
                page = doc.new_page(width=W, height=H)
                y = MARGIN

            total_str = f"${float(item.total):,.2f}" if item.total else "—"
            qty_str = f"{item.quantity} {item.unit or ''}" if item.quantity else ""
            text = f"  {item.description}"
            if qty_str:
                text += f"  [{qty_str}]"
            text += f"  {total_str}"

            page.insert_text(
                fitz.Point(MARGIN + 10, y + LINE_H),
                text,
                fontsize=9,
                fontname="helv",
                color=(0.3, 0.3, 0.3),
            )
            y += LINE_H + 3

        y += 12


def annotate_pdf(
    jdr_pdf_path: str,
    result: ComparisonResult,
    output_path: str,
) -> str:
    """Generate an annotated copy of the JDR PDF with comparison highlights.

    - GREEN highlights: exact match with insurance
    - ORANGE highlights: matched but with field differences (differing fields also highlighted)
    - BLUE highlights: JDR only, no insurance match
    - Summary page(s): insurance-only (nugget) items listed by room
    """
    doc = fitz.open(jdr_pdf_path)

    nugget_groups: list[tuple[list[str], list[str], list[ExtractedLineItem]]] = []

    for room_idx, room in enumerate(result.rooms):
        room_label = ", ".join(room.jdr_rooms)
        n_items = len(room.matched) + len(room.unmatched_jdr)
        if n_items == 0:
            if room.unmatched_ins:
                nugget_groups.append((room.jdr_rooms, room.ins_rooms, room.unmatched_ins))
            continue

        print(f"  Generating comments for {room_label} ({n_items} items)...", flush=True)
        comments = _generate_comments(room)

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
            nugget_groups.append((room.jdr_rooms, room.ins_rooms, room.unmatched_ins))

    if nugget_groups:
        _append_nugget_summary(doc, nugget_groups)

    doc.save(output_path)
    doc.close()
    return output_path
