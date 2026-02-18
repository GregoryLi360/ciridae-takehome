import base64
import re
from concurrent.futures import ThreadPoolExecutor

import fitz
from pydantic import BaseModel

from ..llm import vision_extract
from ..schemas import Bbox, ExtractedLineItem, ExtractedRoom, LineItemBboxes, ParsedDocument

_LLM_POOL = ThreadPoolExecutor(max_workers=8)


# --- LLM response models ---

class _RoomSection(BaseModel):
    room_name: str
    is_continuation: bool


class _PageRooms(BaseModel):
    rooms: list[_RoomSection]


class _LLMLineItem(BaseModel):
    description: str
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    total: float | None = None
    room_name: str


class _LLMPageItems(BaseModel):
    line_items: list[_LLMLineItem]


# --- Prompts ---

ROOM_SPLIT_PROMPT = """\
Identify all room sections on this Xactimate PDF proposal page.
For each room section, return:
- room_name: the canonical room name (e.g. "Bathroom", NOT "CONTINUED - Bathroom")
- is_continuation: true if the room continues from a previous page

Rules:
- Subsection headers (WALLS, TRIM/DOORS, FLOORS, CARPET, BATHTUB, MISCELLANEOUS) are NOT rooms.
- Subrooms, alcoves, or nested sub-areas within a room are NOT separate rooms. They belong to the parent room they open into. Use the parent room name instead.
- "Main Level", "Debris Removal", "Labor Minimums Applied" are room-level sections.
- If the page has no room sections (cover page, summary, photos), return an empty list.
- Pages with photos/images of damage, documentation photos, or photo captions are NOT line item pages. Return an empty list for these.
- A line item page has a structured table with columns like DESCRIPTION, QTY, REPLACE, TOTAL (or QUANTITY, UNIT PRICE, RCV). If you don't see this table structure, return an empty list."""

EXTRACTION_PROMPT_TEMPLATE = """\
Extract all line items from this Xactimate PDF proposal page.
The rooms on this page are: {rooms}

For each line item extract:
- description: the item description text (without the leading line number)
- quantity: numeric quantity
- unit: unit of measure (SF, LF, EA, HR, DA, SY, etc.)
- unit_price: per-unit cost. For JDR proposals this is the REPLACE column. For insurance proposals this is the UNIT PRICE column.
- total: the line item total. For JDR proposals this is the TOTAL column. For insurance proposals this is the RCV column (Replacement Cost Value), NOT the ACV column.
- room_name: which of the rooms above this item belongs to. Must be one of: {rooms}

Rules:
- Only extract numbered line items, not subtotals or room totals.
- Some insurance formats show quantity and unit price on a separate line below the description. Combine them into one line item.
- Items marked as "Bid Item" or "OPEN ITEM" with no pricing should still be extracted with null values for unit_price and total."""


# --- Helpers ---

def _render_page_b64(page: fitz.Page) -> str:
    pix = page.get_pixmap(dpi=200)
    return base64.b64encode(pix.tobytes("png")).decode()


def _normalize(text: str) -> str:
    """Normalize text for matching: lowercase, collapse whitespace, strip punctuation edges."""
    return re.sub(r"\s+", " ", text).strip().lower()


def _words_match(pdf_word: str, target_word: str) -> bool:
    """Fuzzy word comparison: handles quoting, punctuation, case."""
    a = pdf_word.lower().strip(".,;:()\"'""''")
    b = target_word.lower().strip(".,;:()\"'""''")
    if not a or not b:
        return False
    if a == b:
        return True
    # Handle curly-quote ↔ straight-quote, fraction chars, etc.
    a_norm = a.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
    b_norm = b.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
    if a_norm == b_norm:
        return True
    # One is a prefix of the other (handles truncated or merged words)
    if len(a) >= 3 and len(b) >= 3 and (a.startswith(b) or b.startswith(a)):
        return True
    return False


def _overlaps_claimed(bbox: Bbox, claimed: list[Bbox]) -> bool:
    """Check if a bbox vertically overlaps any already-claimed bbox."""
    for c in claimed:
        # Two rects overlap vertically if neither is fully above/below the other
        if bbox[1] < c[3] and bbox[3] > c[1]:
            return True
    return False


def _find_description_bbox(
    page: fitz.Page, description: str, claimed: list[Bbox] | None = None,
) -> Bbox | None:
    """Find the full description text using word-level matching.

    Uses get_text("words") to match the description word-by-word,
    then returns the union bbox covering all matched words (handles
    multi-line descriptions naturally).

    ``claimed`` is a list of bboxes already assigned to other items on
    this page — matches that overlap a claimed region are skipped so
    that each item highlights a unique location.
    """
    if claimed is None:
        claimed = []

    text = re.sub(r"^\d+\.\s*", "", description)
    target_words = text.split()
    if not target_words:
        return None

    page_words = page.get_text("words")
    # Each word: (x0, y0, x1, y1, "text", block_no, line_no, word_no)

    min_match = max(2, len(target_words) // 2)
    best_match: list[tuple] = []
    best_count = 0

    for i in range(len(page_words)):
        pw = page_words[i][4]
        if not _words_match(pw, target_words[0]):
            continue

        # Try to match the word sequence starting here
        matched = [page_words[i]]
        ti = 1  # target word index
        pi = i + 1  # page word index
        while ti < len(target_words) and pi < len(page_words):
            pw_next = page_words[pi][4]
            # Skip if next page-word is too far away (different section)
            if page_words[pi][1] - page_words[pi - 1][1] > 20:
                break
            if _words_match(pw_next, target_words[ti]):
                matched.append(page_words[pi])
                ti += 1
                pi += 1
            else:
                # The PDF may split words differently; skip one and try again
                pi += 1
                # But don't skip too many
                if pi - (i + len(matched)) > 3:
                    break

        if len(matched) > best_count and len(matched) >= min_match:
            candidate = (
                min(w[0] for w in matched),
                min(w[1] for w in matched),
                max(w[2] for w in matched),
                max(w[3] for w in matched),
            )
            if not _overlaps_claimed(candidate, claimed):
                best_count = len(matched)
                best_match = matched

    if best_match:
        x0 = min(w[0] for w in best_match)
        y0 = min(w[1] for w in best_match)
        x1 = max(w[2] for w in best_match)
        y1 = max(w[3] for w in best_match)
        return (x0, y0, x1, y1)

    # Fallback: use search_for with progressively shorter prefixes
    for length in [60, 40, 25]:
        query = text[:length].strip()
        if len(query) < 5:
            continue
        results = page.search_for(query)
        for r in results:
            candidate = (r.x0, r.y0, r.x1, r.y1)
            if not _overlaps_claimed(candidate, claimed):
                return candidate
    return None


def _find_number_bbox(page: fitz.Page, value: float | None, desc_bbox: Bbox | None) -> Bbox | None:
    """Find a numeric value on the same row as the description."""
    if value is None or desc_bbox is None:
        return None
    candidates = []
    candidates.append(f"{value:,.2f}")
    candidates.append(f"{value:.2f}")
    if value == int(value):
        candidates.append(f"{int(value):,}")
        candidates.append(str(int(value)))
    y_mid = (desc_bbox[1] + desc_bbox[3]) / 2
    tolerance = 15
    for text in candidates:
        results = page.search_for(text)
        for r in results:
            r_mid = (r.y0 + r.y1) / 2
            if abs(r_mid - y_mid) < tolerance:
                return (r.x0, r.y0, r.x1, r.y1)
    return None


def _find_unit_bbox(page: fitz.Page, unit: str | None, desc_bbox: Bbox | None) -> Bbox | None:
    """Find the unit text on the same row as the description."""
    if not unit or desc_bbox is None:
        return None
    y_mid = (desc_bbox[1] + desc_bbox[3]) / 2
    tolerance = 15
    results = page.search_for(unit)
    for r in results:
        r_mid = (r.y0 + r.y1) / 2
        if abs(r_mid - y_mid) < tolerance:
            return (r.x0, r.y0, r.x1, r.y1)
    return None


def _locate_bboxes(page: fitz.Page, item, claimed: list[Bbox] | None = None) -> LineItemBboxes:
    """Locate per-field bounding boxes for a line item."""
    desc_bbox = _find_description_bbox(page, item.description, claimed)
    return LineItemBboxes(
        description=desc_bbox,
        quantity=_find_number_bbox(page, item.quantity, desc_bbox),
        unit_price=_find_number_bbox(page, item.unit_price, desc_bbox),
        total=_find_number_bbox(page, item.total, desc_bbox),
        unit=_find_unit_bbox(page, item.unit, desc_bbox),
    )


# --- Main pipeline ---

def parse_document(pdf_path: str, source: str) -> ParsedDocument:
    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    # Phase 1: Pre-render all pages (sequential — fitz not thread-safe)
    page_images = [_render_page_b64(doc[i]) for i in range(total_pages)]

    # Phase 2: Room-split (parallel LLM calls)
    def _room_split(page_idx: int) -> list[str]:
        print(f"    [{source}] room-split page {page_idx+1}/{total_pages}", flush=True)
        result = vision_extract(page_images[page_idx], _PageRooms, ROOM_SPLIT_PROMPT)
        return [r.room_name for r in result.rooms]

    page_rooms = list(_LLM_POOL.map(_room_split, range(total_pages)))

    # Phase 3: Extract line items (parallel LLM calls, then sequential bbox location)
    content_pages = [i for i, r in enumerate(page_rooms) if r]

    def _extract(page_idx: int) -> tuple[int, list[str], _LLMPageItems]:
        rooms = page_rooms[page_idx]
        step = content_pages.index(page_idx)
        print(f"    [{source}] extract page {page_idx+1} ({step+1}/{len(content_pages)})", flush=True)
        prompt = EXTRACTION_PROMPT_TEMPLATE.format(rooms=", ".join(rooms))
        return page_idx, rooms, vision_extract(page_images[page_idx], _LLMPageItems, prompt)

    extraction_results = list(_LLM_POOL.map(_extract, content_pages))

    # Sequential bbox location (uses fitz Page objects)
    rooms_dict: dict[str, list[ExtractedLineItem]] = {}
    claimed_bboxes: dict[int, list[Bbox]] = {}  # page_idx -> claimed description bboxes
    for page_idx, rooms, result in extraction_results:
        page = doc[page_idx]
        for item in result.line_items:
            if item.quantity is None and item.unit_price is None and item.total is None:
                continue
            if source == "jdr":
                claimed = claimed_bboxes.setdefault(page_idx, [])
                bboxes = _locate_bboxes(page, item, claimed)
                if bboxes.description:
                    claimed.append(bboxes.description)
            else:
                bboxes = LineItemBboxes()
            extracted = ExtractedLineItem(
                description=item.description,
                quantity=item.quantity,
                unit=item.unit,
                unit_price=item.unit_price,
                total=item.total,
                bboxes=bboxes,
                page_number=page_idx + 1,
            )
            room_name = item.room_name if item.room_name in rooms else rooms[0]
            rooms_dict.setdefault(room_name, []).append(extracted)

    doc.close()
    rooms_list = [ExtractedRoom(room_name=name, line_items=items) for name, items in rooms_dict.items()]
    return ParsedDocument(source=source, rooms=rooms_list)
