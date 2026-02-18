"""Test script: re-locate bboxes and generate annotated PDF."""

import json
import sys

import fitz

from app.schemas import Bbox, ComparisonResult, LineItemBboxes
from app.pipeline.parse import _locate_bboxes
from app.pipeline.annotate import annotate_pdf

jdr_pdf = sys.argv[1] if len(sys.argv) > 1 else "../documents/proposal 1/jdr_proposal.pdf"
cache = sys.argv[2] if len(sys.argv) > 2 else ".eval_cache/comparison.json"
output = sys.argv[3] if len(sys.argv) > 3 else "annotated_output.pdf"

print(f"Loading comparison from {cache}...")
with open(cache) as f:
    result = ComparisonResult.model_validate(json.load(f))

total_matched = sum(len(r.matched) for r in result.rooms)
total_blue = sum(len(r.unmatched_jdr) for r in result.rooms)
total_nugget = sum(len(r.unmatched_ins) for r in result.rooms)
print(f"  {total_matched} matched, {total_blue} JDR-only, {total_nugget} insurance-only")

# Re-locate bboxes using the improved word-level matching
print("Re-locating bboxes with improved parser...")
doc = fitz.open(jdr_pdf)

class _FakeItem:
    """Adapter so _locate_bboxes can work with ExtractedLineItem data."""
    def __init__(self, item):
        self.description = item.description
        self.quantity = float(item.quantity) if item.quantity is not None else None
        self.unit = item.unit
        self.unit_price = float(item.unit_price) if item.unit_price is not None else None
        self.total = float(item.total) if item.total is not None else None

found = 0
total = 0
claimed_bboxes: dict[int, list[Bbox]] = {}
for room in result.rooms:
    for pair in room.matched:
        item = pair.jdr_item
        total += 1
        page_idx = item.page_number - 1
        page = doc[page_idx]
        claimed = claimed_bboxes.setdefault(page_idx, [])
        new_bboxes = _locate_bboxes(page, _FakeItem(item), claimed)
        if new_bboxes.description:
            found += 1
            claimed.append(new_bboxes.description)
        item.bboxes = new_bboxes
    for item in room.unmatched_jdr:
        total += 1
        page_idx = item.page_number - 1
        page = doc[page_idx]
        claimed = claimed_bboxes.setdefault(page_idx, [])
        new_bboxes = _locate_bboxes(page, _FakeItem(item), claimed)
        if new_bboxes.description:
            found += 1
            claimed.append(new_bboxes.description)
        item.bboxes = new_bboxes

doc.close()
print(f"  Located {found}/{total} description bboxes")

print(f"Annotating {jdr_pdf}...")
annotate_pdf(jdr_pdf, result, output)
print(f"Saved annotated PDF to {output}")
