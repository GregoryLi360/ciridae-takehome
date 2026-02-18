"""
Evaluate matching pipeline against ground truth from ciridae_markup.txt.

Stages (run individually or all at once):
  uv run python eval_matching.py parse-jdr    # parse JDR PDF → cache
  uv run python eval_matching.py parse-ins    # parse insurance PDF → cache
  uv run python eval_matching.py compare      # run matching → cache
  uv run python eval_matching.py eval         # evaluate against ground truth
  uv run python eval_matching.py              # run all stages
"""
import re
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

GT_PATH = "../ciridae_markup.txt"
JDR_PDF = "../documents/proposal 1/jdr_proposal.pdf"
INS_PDF = "../documents/proposal 1/insurance_proposal.pdf"
CACHE_DIR = Path(".eval_cache")


def log(msg: str):
    print(msg, flush=True)


# ── Ground truth ─────────────────────────────────────────────────────

def parse_ground_truth(path: str) -> dict[int, str]:
    content = Path(path).read_text()
    items: dict[int, str] = {}
    color = None
    for line in content.splitlines():
        m = re.match(r"COLOR:\s+(\w+)", line)
        if m:
            color = m.group(1)
            continue
        if color not in ("green", "orange", "sky_blue"):
            continue
        if "Text:" not in line:
            continue
        text = line.split("Text:", 1)[1].strip()
        for nm in re.finditer(r"\b(\d+)\.\s", text):
            n = int(nm.group(1))
            if 1 <= n <= 200:
                items[n] = color
    return items


def parse_gt_descriptions(path: str) -> dict[int, str]:
    content = Path(path).read_text()
    descs: dict[int, str] = {}
    color = None
    for line in content.splitlines():
        m = re.match(r"COLOR:\s+(\w+)", line)
        if m:
            color = m.group(1)
            continue
        if color not in ("green", "orange", "sky_blue"):
            continue
        if "Text:" not in line:
            continue
        text = line.split("Text:", 1)[1].strip()
        nums_and_pos = list(re.finditer(r"\b(\d+)\.\s", text))
        for idx, nm in enumerate(nums_and_pos):
            n = int(nm.group(1))
            if not (1 <= n <= 200):
                continue
            start = nm.end()
            end = nums_and_pos[idx + 1].start() if idx + 1 < len(nums_and_pos) else len(text)
            desc = text[start:end].strip()
            desc = re.sub(r"\b(tesolC|moordeB)\b", "", desc).strip()
            desc = re.sub(r"\s+", " ", desc)
            if desc:
                descs[n] = desc
    return descs


# ── Caching ──────────────────────────────────────────────────────────

def _cache(name: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"{name}.json"


def _has_cache(name: str) -> bool:
    return _cache(name).exists()


# ── Stages ───────────────────────────────────────────────────────────

def stage_parse_jdr():
    from app.pipeline.parse import parse_document
    from app.schemas import ParsedDocument

    p = _cache("jdr")
    if p.exists():
        log("  [cache hit] jdr already parsed")
        doc = ParsedDocument.model_validate_json(p.read_text())
    else:
        log("  Parsing JDR PDF...")
        doc = parse_document(JDR_PDF, "jdr")
        p.write_text(doc.model_dump_json(indent=2))
        log("  [saved] .eval_cache/jdr.json")

    n = sum(len(r.line_items) for r in doc.rooms)
    log(f"  JDR: {n} items / {len(doc.rooms)} rooms")
    return doc


def stage_parse_ins():
    from app.pipeline.parse import parse_document
    from app.schemas import ParsedDocument

    p = _cache("ins")
    if p.exists():
        log("  [cache hit] ins already parsed")
        doc = ParsedDocument.model_validate_json(p.read_text())
    else:
        log("  Parsing insurance PDF...")
        doc = parse_document(INS_PDF, "insurance")
        p.write_text(doc.model_dump_json(indent=2))
        log("  [saved] .eval_cache/ins.json")

    n = sum(len(r.line_items) for r in doc.rooms)
    log(f"  INS: {n} items / {len(doc.rooms)} rooms")
    return doc


def stage_compare():
    from app.pipeline.matching import compare_documents
    from app.schemas import ComparisonResult, ParsedDocument

    # Need both parsed docs
    for name in ("jdr", "ins"):
        if not _has_cache(name):
            log(f"  ERROR: run 'parse-{name}' first")
            sys.exit(1)

    p = _cache("comparison")
    if p.exists():
        log("  [cache hit] comparison already done")
        result = ComparisonResult.model_validate_json(p.read_text())
    else:
        jdr = ParsedDocument.model_validate_json(_cache("jdr").read_text())
        ins = ParsedDocument.model_validate_json(_cache("ins").read_text())
        log("  Running comparison (1 LLM call per room group)...")
        result = compare_documents(jdr, ins)
        p.write_text(result.model_dump_json(indent=2))
        log("  [saved] .eval_cache/comparison.json")

    matched = sum(len(r.matched) for r in result.rooms)
    green = sum(1 for r in result.rooms for p in r.matched if p.color.value == "green")
    orange = sum(1 for r in result.rooms for p in r.matched if p.color.value == "orange")
    blue = sum(len(r.unmatched_jdr) for r in result.rooms)
    nugget = sum(len(r.unmatched_ins) for r in result.rooms)
    log(f"  matched={matched} (G={green} O={orange})  blue={blue}  nugget={nugget}")
    return result


def stage_eval():
    from app.schemas import ComparisonResult

    if not _has_cache("comparison"):
        log("  ERROR: run 'compare' first")
        sys.exit(1)

    result = ComparisonResult.model_validate_json(_cache("comparison").read_text())

    log("Ground truth...")
    gt = parse_ground_truth(GT_PATH)
    gt_descs = parse_gt_descriptions(GT_PATH)
    counts = Counter(gt.values())
    log(f"  {len(gt)} items: green={counts.get('green',0)}, "
        f"orange={counts.get('orange',0)}, sky_blue={counts.get('sky_blue',0)}")

    # Collect pipeline JDR items
    pipe_items: list[tuple[str, str, str]] = []
    for room in result.rooms:
        label = room.jdr_room or "(none)"
        for pair in room.matched:
            pipe_items.append((pair.jdr_item.description, pair.color.value, label))
        for item in room.unmatched_jdr:
            pipe_items.append((item.description, "blue", label))

    log(f"  Pipeline JDR items: {len(pipe_items)}")

    # Match GT items to pipeline items by description similarity
    records = []
    used: set[int] = set()

    for item_num in sorted(gt.keys()):
        gt_color = gt[item_num]
        gt_desc = gt_descs.get(item_num, "")

        best_i = None
        best_score = 0.0
        for i, (desc, _, _) in enumerate(pipe_items):
            if i in used:
                continue
            score = SequenceMatcher(None, _clean(gt_desc), _clean(desc)).ratio()
            if score > best_score:
                best_score = score
                best_i = i

        if best_i is not None and best_score > 0.4:
            desc, pipe_color, room = pipe_items[best_i]
            used.add(best_i)
            pipe_norm = "sky_blue" if pipe_color == "blue" else pipe_color
            records.append({
                "item": item_num, "gt": gt_color, "pipe": pipe_norm,
                "ok": pipe_norm == gt_color, "sim": best_score,
                "desc": desc[:55], "room": room,
            })
        else:
            records.append({
                "item": item_num, "gt": gt_color, "pipe": "MISSING",
                "ok": False, "sim": best_score, "desc": "", "room": "",
            })

    # ── Report ──
    correct = sum(r["ok"] for r in records)
    total = len(records)
    missing = sum(1 for r in records if r["pipe"] == "MISSING")

    log(f"\n{'='*80}")
    log(f"  ACCURACY: {correct}/{total} = {100*correct/total:.1f}%")
    log(f"  Missing from pipeline: {missing}")
    log(f"{'='*80}")

    # Confusion matrix
    log(f"\n  {'GT \\\\ Pipeline':>16} | {'green':>7} {'orange':>7} {'sky_blue':>8} {'MISSING':>7} | {'total':>5}")
    log(f"  {'-'*62}")
    for gt_c in ["green", "orange", "sky_blue"]:
        row = []
        for pipe_c in ["green", "orange", "sky_blue", "MISSING"]:
            row.append(sum(1 for r in records if r["gt"] == gt_c and r["pipe"] == pipe_c))
        log(f"  {gt_c:>16} | {row[0]:>7} {row[1]:>7} {row[2]:>8} {row[3]:>7} | {sum(row):>5}")

    # Mismatches
    mismatches = [r for r in records if not r["ok"]]
    if mismatches:
        log(f"\n  Mismatches ({len(mismatches)}):")
        for r in mismatches:
            log(f"    #{r['item']:3d}  GT={r['gt']:8}  Pipe={r['pipe']:8}  "
                f"sim={r['sim']:.2f}  {r['room']:20s} {r['desc']}")

    # Pipeline items not matched to any GT item
    unmatched_pipe = [pipe_items[i] for i in range(len(pipe_items)) if i not in used]
    if unmatched_pipe:
        log(f"\n  Pipeline items not in GT ({len(unmatched_pipe)}):")
        for desc, color, room in unmatched_pipe:
            log(f"    [{color:8}] {room:20s} {desc[:55]}")


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


# ── Main ─────────────────────────────────────────────────────────────

STAGES = {
    "parse-jdr": stage_parse_jdr,
    "parse-ins": stage_parse_ins,
    "compare": stage_compare,
    "eval": stage_eval,
}

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    stage = args[0] if args else None

    if stage and stage not in STAGES:
        log(f"Unknown stage '{stage}'. Options: {', '.join(STAGES)}")
        sys.exit(1)

    if stage:
        log(f"\n=== Stage: {stage} ===")
        STAGES[stage]()
    else:
        # Run all stages
        for name, fn in STAGES.items():
            log(f"\n=== Stage: {name} ===")
            fn()

    log("\nDone.")


if __name__ == "__main__":
    main()
