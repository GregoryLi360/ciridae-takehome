# Insurance Rebuttal — Design Doc

## 1. System Architecture

```
┌─────────────┐     ┌──────────────────────────────────────────┐
│  React/Vite │────▶│  FastAPI Backend                         │
│  Frontend   │◀────│                                          │
└─────────────┘     │  ┌────────┐  ┌─────────┐ ┌─────────────┐ │
                    │  │PDF Parse│▶│ LLM     │▶│ Markup Gen  │ │
                    │  └────────┘  │ Matching│ └─────────────┘ │
                    │              └─────────┘                 │
                    └──────────┬───────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │ Ciridae LLM Gateway │
                    └─────────────────────┘
```

## 2. Data Model (Pydantic)

```python
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
    source: str                  # "jdr" | "insurance"
    rooms: list[ExtractedRoom]
```

## 3. Pipeline Steps

### Step 1 — PDF Parsing (Hybrid: LLM Vision + PyMuPDF)

Three-phase approach within a single `parse_document()` call:

1. **Room splitting (LLM)** — Render each page to a 200 DPI PNG via PyMuPDF, send to `claude-3-7-sonnet` to identify room sections. Returns canonical room names per page with continuation flags (e.g. "CONTINUED - Bathroom" → "Bathroom").
2. **Line item extraction (LLM)** — For each page that has rooms, send the image with the known room list from phase 1. LLM extracts numbered line items with description, quantity, unit, unit_price, total, and assigns each to a room. Structured output via Pydantic `response_format`.
3. **Per-field bbox location (PyMuPDF)** — For each extracted line item, use `fitz.Page.search_for()` to locate individual field positions on the page:
   - `description` — progressively shorter prefix search (60, 40, 25 chars)
   - `quantity`, `unit_price`, `total` — number search with comma formatting, constrained to the same row (±15pt vertical tolerance)
   - `unit` — text search constrained to the same row

Each field gets its own tight `(x0, y0, x1, y1)` bbox for targeted highlighting during annotation.

**Pydantic schemas** (`backend/app/schemas.py`):
- `LineItemBboxes` — per-field bboxes: description, quantity, unit, unit_price, total
- `ExtractedLineItem` — description, quantity, unit, unit_price, total, bboxes (`LineItemBboxes`), page_number
- `ExtractedRoom` — room_name, line_items
- `ParsedDocument` — source (`"jdr"` | `"insurance"`), rooms

**LLM response models** (internal to `parse.py`):
- `_PageRooms` → `_RoomSection` (room_name, is_continuation)
- `_LLMPageItems` → `_LLMLineItem` (description, quantity, unit, unit_price, total, room_name)

### Step 2 — Room Mapping (LLM)
- Single LLM call with both room lists → returns mapping as JSON:
  ```json
  [
    {"jdr_rooms": ["Kitchen", "Breakfast Area"], "ins_rooms": ["Kitchen Area"]},
    {"jdr_rooms": ["Master Bedroom"], "ins_rooms": ["Bedroom 1"]}
  ]
  ```
- Handles splits/merges and naming variations

### Step 3 — Line-Item Matching + Classification (Embeddings + Code)
- Embed all line-item descriptions from both documents using `text-embedding-3-small` via the gateway
- **Per mapped room group:**
  - Compute cosine similarity matrix (JDR items × Insurance items)
  - Run Hungarian algorithm (via `scipy.optimize.linear_sum_assignment`) to find optimal 1:1 assignment
  - Apply similarity threshold (e.g. 0.85) — pairs below threshold are unmatched
- Unmatched JDR items → **Blue**; unmatched Insurance items → **Nugget**
- For each matched pair, **deterministic code** checks:
  - `unit` — exact categorical match (SF, LF, EA, etc.)
  - `quantity`, `unit_price` — ±2% numeric tolerance
  - All pass → **Green**; any fail → **Orange** with diff notes

### Step 4 — Annotated PDF Generation
- **Tool:** `PyMuPDF (fitz)`
- Open the original JDR PDF
- For each line item, draw colored highlight over the description and relevant metadata fields using per-field bboxes from Step 1
- Add inline annotation with rationale note
- Append summary page per room listing Nuggets (insurance-only items)
- Save as new PDF

## 4. API Endpoints

| Method | Path                     | Description                          |
|--------|--------------------------|--------------------------------------|
| POST   | `/api/jobs`              | Upload JDR + Insurance PDFs, create job |
| GET    | `/api/jobs/{id}`         | Poll job status + summary stats      |
| GET    | `/api/jobs/{id}/result`  | Download annotated PDF               |
| GET    | `/api/jobs/{id}/items`   | Get all line items + classifications  |

Job processing runs as a background task (`BackgroundTasks` or simple task queue).

## 5. Frontend

Single-page app with three states:

1. **Upload** — Two file dropzones (JDR / Insurance), submit button
2. **Processing** — Progress indicator, poll `GET /api/jobs/{id}` via React Query
3. **Result** — Embedded PDF viewer + download button; optional summary table of matches/discrepancies with dollar totals

## 6. LLM Usage

All calls go through Ciridae Gateway (`https://api.llmgateway.ciridae.app`).

| Call                | Model                    | Input                              | Output Format   |
|---------------------|----------------------------|------------------------------------|-----------------|
| Room splitting      | `claude-3-7-sonnet`      | Page image + room ID prompt        | Pydantic schema |
| Line item extraction| `claude-3-7-sonnet`      | Page image + room context + extraction prompt | Pydantic schema |
| Room mapping        | `fast-production`          | Two room-name lists                | JSON array      |
| Description embeddings | `text-embedding-3-small` | All line-item descriptions         | Vector arrays   |

**Cost control:** Two LLM calls per page (room split + extraction). Embeddings are a single batch call per document. Matching is pure compute (cosine sim + Hungarian algorithm).

## 7. Key Design Decisions

- **LLM vision for PDF parsing** — Xactimate PDFs vary in layout; LLM vision handles tables, merged cells, and formatting inconsistencies without brittle heuristics
- **Per-field bboxes** — Each metadata field (description, qty, unit, price, total) gets its own bbox so the annotation step can highlight specific fields that differ, not just the entire row
- **Two-phase LLM parsing** — Room splitting first gives the extraction LLM explicit context, ensures consistent room naming across pages, and avoids hallucinated room assignments
- **Embeddings for matching, code for math** — Embedding similarity + Hungarian algorithm gives fast, deterministic, cheap matching; ±2% numeric comparison stays as code
- **LLM only where irreplaceable** — Room mapping (fuzzy name resolution with splits/merges) and PDF parsing (vision) are the only LLM calls; everything else is compute
- **PyMuPDF for annotation** — Preserves original PDF layout; draws colored rectangles precisely using per-field bbox coordinates from parsing
- **Background processing** — PDF pipeline takes 30-90s; async avoids request timeouts

## 8. Tech Stack

- **Backend:** Python with `uv`, FastAPI
- **Frontend:** TypeScript, React, Vite
- **State/Data:** React Query
- **Styling/UI:** TailwindCSS, shadcn/ui
- **Validation:** zod (frontend) / Pydantic (backend)
- **LLM Calls:** Ciridae LLM Gateway (OpenAI-compatible API)

## 9. Directory Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app + routes
│   │   ├── schemas.py           # Pydantic schemas
│   │   ├── pipeline/
│   │   │   ├── parse.py         # PDF extraction (3-phase)
│   │   │   ├── room_mapping.py  # LLM room mapping
│   │   │   ├── matching.py      # Semantic matching + classification
│   │   │   └── annotate.py      # PDF markup generation
│   │   └── llm.py               # Gateway client wrapper
│   ├── test_parse.py            # CLI test script for parse pipeline
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── UploadForm.tsx
│   │   │   ├── JobStatus.tsx
│   │   │   └── ResultViewer.tsx
│   │   └── api/                 # React Query hooks
│   ├── package.json
│   └── vite.config.ts
├── documents/                   # Input PDFs (proposal sets)
├── DESIGN.md
└── README.md
```
