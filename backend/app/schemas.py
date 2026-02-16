from decimal import Decimal

from pydantic import BaseModel


class ExtractedLineItem(BaseModel):
    description: str
    quantity: Decimal | None = None
    unit: str | None = None
    unit_price: Decimal | None = None
    total: Decimal | None = None
    bbox: tuple[float, float, float, float] | None = None
    page_number: int


class ExtractedRoom(BaseModel):
    room_name: str
    line_items: list[ExtractedLineItem]


class ParsedDocument(BaseModel):
    source: str
    rooms: list[ExtractedRoom]
