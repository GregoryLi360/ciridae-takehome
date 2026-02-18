import sys

from app.pipeline.parse import parse_document
from app.pipeline.matching import compare_documents

jdr_path = sys.argv[1] if len(sys.argv) > 1 else "../documents/proposal 1/jdr_proposal.pdf"
ins_path = sys.argv[2] if len(sys.argv) > 2 else "../documents/proposal 1/insurance_proposal.pdf"

print("Parsing JDR document...")
jdr = parse_document(jdr_path, "jdr")
print(f"  Found {len(jdr.rooms)} rooms, {sum(len(r.line_items) for r in jdr.rooms)} total items")

print("Parsing insurance document...")
ins = parse_document(ins_path, "insurance")
print(f"  Found {len(ins.rooms)} rooms, {sum(len(r.line_items) for r in ins.rooms)} total items")

print("\nComparing documents...")
result = compare_documents(jdr, ins)

COLOR_SYMBOLS = {"green": "G", "orange": "O", "blue": "B", "nugget": "N"}

for room in result.rooms:
    label = f"JDR:{room.jdr_rooms} <-> INS:{room.ins_rooms}"
    matched_count = len(room.matched)
    blue_count = len(room.unmatched_jdr)
    nugget_count = len(room.unmatched_ins)
    print(f"\n{'=' * 80}")
    print(f"  {label}")
    print(f"  matched={matched_count}  unmatched_jdr(blue)={blue_count}  unmatched_ins(nugget)={nugget_count}")
    print(f"{'=' * 80}")

    for pair in room.matched:
        sym = COLOR_SYMBOLS[pair.color.value]
        desc = pair.jdr_item.description[:50]
        print(f"  [{sym}] {desc}")
        if pair.diff_notes:
            for d in pair.diff_notes:
                print(f"       {d.field}: JDR={d.jdr_value} vs INS={d.ins_value}")

    for item in room.unmatched_jdr:
        print(f"  [B] {item.description[:50]}  (JDR only)")

    for item in room.unmatched_ins:
        print(f"  [N] {item.description[:50]}  (INS only)")

print(f"\n--- Summary ---")
total_matched = sum(len(r.matched) for r in result.rooms)
total_green = sum(1 for r in result.rooms for p in r.matched if p.color.value == "green")
total_orange = sum(1 for r in result.rooms for p in r.matched if p.color.value == "orange")
total_blue = sum(len(r.unmatched_jdr) for r in result.rooms)
total_nugget = sum(len(r.unmatched_ins) for r in result.rooms)
print(f"Matched: {total_matched} (green={total_green}, orange={total_orange})")
print(f"Unmatched JDR (blue): {total_blue}")
print(f"Unmatched INS (nugget): {total_nugget}")
print(f"Total items: {total_matched + total_blue + total_nugget}")
