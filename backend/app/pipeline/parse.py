import base64
import re

import fitz
from pydantic import BaseModel

from ..llm import vision_extract
from ..schemas import Bbox, ExtractedLineItem, ExtractedRoom, LineItemBboxes, ParsedDocument


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
- "Main Level", "Debris Removal", "Labor Minimums Applied" are room-level sections.
- If the page has no room sections (cover page, summary, photos), return an empty list."""

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


def _search_text(page: fitz.Page, text: str) -> Bbox | None:
    """Search for text on page and return its tight bounding box."""
    results = page.search_for(text)
    if results:
        r = results[0]
        return (r.x0, r.y0, r.x1, r.y1)
    return None


def _find_description_bbox(page: fitz.Page, description: str) -> Bbox | None:
    """Find the description text, trying progressively shorter prefixes."""
    text = re.sub(r"^\d+\.\s*", "", description)
    for length in [60, 40, 25]:
        query = text[:length].strip()
        if len(query) < 5:
            continue
        bbox = _search_text(page, query)
        if bbox:
            return bbox
    return None


def _find_number_bbox(page: fitz.Page, value: float | None, desc_bbox: Bbox | None) -> Bbox | None:
    """Find a numeric value on the same row as the description."""
    if value is None or desc_bbox is None:
        return None
    # Try multiple formatting: with commas, without, integer form
    candidates = []
    candidates.append(f"{value:,.2f}")  # 1,734.96
    candidates.append(f"{value:.2f}")   # 1734.96
    if value == int(value):
        candidates.append(f"{int(value):,}")  # 1,735
        candidates.append(str(int(value)))     # 1735
    y_mid = (desc_bbox[1] + desc_bbox[3]) / 2
    tolerance = 15  # points vertical tolerance for same-row matching
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


def _locate_bboxes(page: fitz.Page, item) -> LineItemBboxes:
    """Locate per-field bounding boxes for a line item."""
    desc_bbox = _find_description_bbox(page, item.description)
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
    page_images: list[str] = []
    page_rooms: list[list[str]] = []

    # Phase 1: Render all pages and identify room sections
    for page_idx in range(len(doc)):
        image_b64 = _render_page_b64(doc[page_idx])
        page_images.append(image_b64)

        result = vision_extract(image_b64, _PageRooms, ROOM_SPLIT_PROMPT)
        rooms = [r.room_name for r in result.rooms]
        page_rooms.append(rooms)

    # Phase 2: Extract line items from pages that have rooms
    rooms_dict: dict[str, list[ExtractedLineItem]] = {}

    for page_idx, rooms in enumerate(page_rooms):
        if not rooms:
            continue

        rooms_str = ", ".join(rooms)
        prompt = EXTRACTION_PROMPT_TEMPLATE.format(rooms=rooms_str)
        result = vision_extract(page_images[page_idx], _LLMPageItems, prompt)

        page = doc[page_idx]
        for item in result.line_items:
            bboxes = _locate_bboxes(page, item)
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
