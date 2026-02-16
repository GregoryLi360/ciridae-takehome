import sys

from app.pipeline.parse import parse_document

pdf_path = sys.argv[1] if len(sys.argv) > 1 else "../documents/proposal 1/jdr_proposal.pdf"
source = sys.argv[2] if len(sys.argv) > 2 else "jdr"

result = parse_document(pdf_path, source)

for room in result.rooms:
    print(f"\n=== {room.room_name} ({len(room.line_items)} items) ===")
    for item in room.line_items:
        qty = f"{item.quantity}" if item.quantity is not None else "?"
        unit = item.unit or "?"
        total = f"${item.total}" if item.total is not None else "$?"
        bbox_str = "bbox" if item.bbox else "NO BBOX"
        print(f"  {item.description[:55]:<55} {qty:>8} {unit:<4} {total:>12}  p{item.page_number}  {bbox_str}")
