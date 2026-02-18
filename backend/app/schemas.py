from decimal import Decimal
from enum import Enum

from pydantic import BaseModel


Bbox = tuple[float, float, float, float]


class MatchColor(str, Enum):
    GREEN = "green"
    ORANGE = "orange"
    BLUE = "blue"
    NUGGET = "nugget"


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


class DiffNote(BaseModel):
    field: str
    jdr_value: str
    ins_value: str


class MatchedPair(BaseModel):
    jdr_item: ExtractedLineItem
    ins_item: ExtractedLineItem
    color: MatchColor
    diff_notes: list[DiffNote] = []


class RoomComparison(BaseModel):
    jdr_rooms: list[str]
    ins_rooms: list[str]
    matched: list[MatchedPair] = []
    unmatched_jdr: list[ExtractedLineItem] = []
    unmatched_ins: list[ExtractedLineItem] = []


class ComparisonResult(BaseModel):
    rooms: list[RoomComparison]
