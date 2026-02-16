from decimal import Decimal

from pydantic import BaseModel


Bbox = tuple[float, float, float, float]


class LineItemBboxes(BaseModel):
    description: Bbox | None = None
    quantity: Bbox | None = None
    unit: Bbox | None = None
    unit_price: Bbox | None = None
    total: Bbox | None = None


class ExtractedLineItem(BaseModel):
    description: str
    quantity: Decimal | None = None
    unit: str | None = None
    unit_price: Decimal | None = None
    total: Decimal | None = None
    bboxes: LineItemBboxes = LineItemBboxes()
    page_number: int


class ExtractedRoom(BaseModel):
    room_name: str
    line_items: list[ExtractedLineItem]


class ParsedDocument(BaseModel):
    source: str
    rooms: list[ExtractedRoom]
