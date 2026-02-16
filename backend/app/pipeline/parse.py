import base64
import re

import fitz
from pydantic import BaseModel

from ..llm import vision_extract
from ..schemas import ExtractedLineItem, ExtractedRoom, ParsedDocument


class _LLMLineItem(BaseModel):
    description: str
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    total: float | None = None


class _LLMRoom(BaseModel):
    room_name: str
    line_items: list[_LLMLineItem]


class _LLMPageResponse(BaseModel):
    rooms: list[_LLMRoom]


EXTRACTION_PROMPT = """\
Extract all line items from this Xactimate PDF proposal page.
Group items by room. For each line item extract:
- description: the item description text (without the leading line number)
- quantity: numeric quantity
- unit: unit of measure (SF, LF, EA, HR, DA, SY, etc.)
- unit_price: per-unit cost. For JDR proposals this is the REPLACE column. For insurance proposals this is the UNIT PRICE column.
- total: the line item total. For JDR proposals this is the TOTAL column. For insurance proposals this is the RCV column (Replacement Cost Value), NOT the ACV column.

Rules:
- Skip cover pages, summary/totals pages, notes, photo pages, and non-line-item text.
- If a room continues from a previous page (e.g. "CONTINUED - Bathroom"), use just the room name ("Bathroom").
- Only extract numbered line items from the table, not subtotals or room totals.
- Subsection headers within a room (e.g. WALLS, TRIM/DOORS, FLOORS, CARPET, BATHTUB, MISCELLANEOUS) are NOT separate rooms. Group all items under the parent room name.
- Some insurance formats show quantity and unit price on a separate line below the description. Combine them into one line item.
- Items marked as "Bid Item" or "OPEN ITEM" with no pricing should still be extracted with null values for unit_price and total."""


def _render_page_b64(page: fitz.Page) -> str:
    pix = page.get_pixmap(dpi=200)
    return base64.b64encode(pix.tobytes("png")).decode()


def _locate_bbox(page: fitz.Page, description: str) -> tuple[float, float, float, float] | None:
    text = re.sub(r"^\d+\.\s*", "", description)
    for length in [60, 40, 25]:
        query = text[:length].strip()
        if len(query) < 5:
            continue
        results = page.search_for(query)
        if results:
            r = results[0]
            return (0, r.y0, page.rect.width, r.y1)
    return None


def parse_document(pdf_path: str, source: str) -> ParsedDocument:
    doc = fitz.open(pdf_path)
    rooms_dict: dict[str, list[ExtractedLineItem]] = {}

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        image_b64 = _render_page_b64(page)
        llm_result = vision_extract(image_b64, _LLMPageResponse, EXTRACTION_PROMPT)

        for room in llm_result.rooms:
            for item in room.line_items:
                bbox = _locate_bbox(page, item.description)
                extracted = ExtractedLineItem(
                    description=item.description,
                    quantity=item.quantity,
                    unit=item.unit,
                    unit_price=item.unit_price,
                    total=item.total,
                    bbox=bbox,
                    page_number=page_idx + 1,
                )
                rooms_dict.setdefault(room.room_name, []).append(extracted)

    doc.close()
    rooms = [ExtractedRoom(room_name=name, line_items=items) for name, items in rooms_dict.items()]
    return ParsedDocument(source=source, rooms=rooms)
