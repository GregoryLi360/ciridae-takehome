from __future__ import annotations

import asyncio
import os
import tempfile
from dataclasses import dataclass, field
from uuid import uuid4

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.pipeline.annotate import annotate_pdf
from app.pipeline.matching import compare_documents
from app.pipeline.parse import parse_document
from app.schemas import ComparisonResult, MatchColor

app = FastAPI()

# ---------------------------------------------------------------------------
# In-memory job store
# ---------------------------------------------------------------------------

STATUS_ORDER = [
    "pending",
    "parsing",
    "matching",
    "annotating",
    "complete",
]


@dataclass
class Job:
    id: str
    status: str = "pending"
    progress: str | None = None
    step: int = 0
    total_steps: int = 1
    error: str | None = None
    jdr_path: str = ""
    ins_path: str = ""
    result: ComparisonResult | None = None
    output_pdf: str | None = None
    summary: dict | None = None


jobs: dict[str, Job] = {}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_summary(result: ComparisonResult) -> dict:
    total_jdr = 0
    total_ins = 0
    matched_green = 0
    matched_orange = 0
    unmatched_blue = 0
    unmatched_nugget = 0

    for room in result.rooms:
        matched_green += sum(1 for m in room.matched if m.color == MatchColor.GREEN)
        matched_orange += sum(
            1 for m in room.matched if m.color == MatchColor.ORANGE
        )
        total_jdr += len(room.matched) + len(room.unmatched_jdr)
        total_ins += len(room.matched) + len(room.unmatched_ins)
        unmatched_blue += len(room.unmatched_jdr)
        unmatched_nugget += len(room.unmatched_ins)

    return {
        "total_jdr_items": total_jdr,
        "total_ins_items": total_ins,
        "matched_green": matched_green,
        "matched_orange": matched_orange,
        "unmatched_blue": unmatched_blue,
        "unmatched_nugget": unmatched_nugget,
    }


def _job_response(job: Job) -> dict:
    resp: dict = {
        "id": job.id,
        "status": job.status,
        "step": job.step,
        "total_steps": job.total_steps,
    }
    if job.progress:
        resp["progress"] = job.progress
    if job.summary:
        resp["summary"] = job.summary
    if job.error:
        resp["error"] = job.error
    return resp


# ---------------------------------------------------------------------------
# Background pipeline
# ---------------------------------------------------------------------------


async def _run_pipeline(job: Job) -> None:
    try:
        # --- Parsing (progress reported per-page via callback) ---
        job.status = "parsing"
        job.step = 0
        job.total_steps = 1
        job.progress = "Starting..."

        import threading
        _progress_lock = threading.Lock()
        _source_progress: dict[str, tuple[int, int]] = {}  # source -> (step, total)

        def _make_progress_cb(source: str):
            def _on_progress(step: int, total: int, label: str) -> None:
                with _progress_lock:
                    _source_progress[source] = (step, total)
                    combined_step = sum(s for s, _ in _source_progress.values())
                    combined_total = sum(t for _, t in _source_progress.values())
                    job.step = combined_step
                    job.total_steps = combined_total
                    job.progress = label
            return _on_progress

        jdr_doc, ins_doc = await asyncio.gather(
            asyncio.to_thread(parse_document, job.jdr_path, "jdr", _make_progress_cb("jdr")),
            asyncio.to_thread(parse_document, job.ins_path, "insurance", _make_progress_cb("insurance")),
        )

        # --- Matching ---
        job.status = "matching"
        job.step = 0
        job.total_steps = 1
        job.progress = "Mapping rooms and matching line items..."
        result = await asyncio.to_thread(compare_documents, jdr_doc, ins_doc)
        job.step = 1

        # --- Annotating ---
        job.status = "annotating"
        job.step = 0
        job.total_steps = 1
        job.progress = "Generating comments and highlights..."
        output_path = os.path.join(
            os.path.dirname(job.jdr_path), "annotated_output.pdf"
        )
        await asyncio.to_thread(annotate_pdf, job.jdr_path, result, output_path)
        job.step = 1

        job.result = result
        job.output_pdf = output_path
        job.summary = _build_summary(result)
        job.status = "complete"
        job.progress = None
    except Exception as exc:
        job.status = "error"
        job.error = str(exc)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/api/jobs")
async def create_job(jdr: UploadFile, insurance: UploadFile) -> dict:
    job_id = uuid4().hex
    tmp = tempfile.mkdtemp(prefix=f"ciridae-{job_id}-")

    jdr_path = os.path.join(tmp, "jdr.pdf")
    ins_path = os.path.join(tmp, "insurance.pdf")

    with open(jdr_path, "wb") as f:
        f.write(await jdr.read())
    with open(ins_path, "wb") as f:
        f.write(await insurance.read())

    job = Job(id=job_id, jdr_path=jdr_path, ins_path=ins_path)
    jobs[job_id] = job

    asyncio.create_task(_run_pipeline(job))

    return _job_response(job)


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_response(job)


@app.get("/api/jobs/{job_id}/items")
async def get_job_items(job_id: str) -> dict:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status == "error":
        raise HTTPException(status_code=409, detail=job.error)
    if job.status != "complete" or job.result is None:
        raise HTTPException(status_code=409, detail="Job not complete")
    return job.result.model_dump()


@app.get("/api/jobs/{job_id}/result")
async def get_job_result(job_id: str) -> FileResponse:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status == "error":
        raise HTTPException(status_code=409, detail=job.error)
    if job.status != "complete" or job.output_pdf is None:
        raise HTTPException(status_code=409, detail="Job not complete")
    return FileResponse(
        job.output_pdf,
        media_type="application/pdf",
        filename="annotated_output.pdf",
    )
