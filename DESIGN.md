# Insurance Rebuttal — Design Doc

## 1. System Architecture

```
┌─────────────┐     ┌──────────────────────────────────────────┐     ┌─────────────┐
│  React/Vite  │────▶│  FastAPI Backend                         │────▶│  Postgres    │
│  Frontend    │◀────│                                          │◀────│  (SQLAlchemy)│
└─────────────┘     │  ┌────────┐ ┌─────────┐ ┌─────────────┐ │     └─────────────┘
                    │  │PDF Parse│▶│ LLM     │▶│ Markup Gen  │ │
                    │  └────────┘ │ Matching │ └─────────────┘ │
                    │             └─────────┘                  │
                    └──────────┬───────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │ Ciridae LLM Gateway  │
                    └─────────────────────┘
```

## 2. Data Model

```sql
jobs
  id            UUID PK
  status        ENUM(pending, processing, complete, failed)
  created_at    TIMESTAMP
  jdr_filename  TEXT
  ins_filename  TEXT

line_items
  id            UUID PK
  job_id        UUID FK → jobs
  source        ENUM(jdr, insurance)
  room_raw      TEXT          -- original room name from PDF
  room_mapped   TEXT          -- normalized room key after mapping
  description   TEXT
  quantity      DECIMAL
  unit          TEXT
  unit_price    DECIMAL
  total         DECIMAL
  page_number   INT

match_results
  id            UUID PK
  job_id        UUID FK → jobs
  jdr_item_id   UUID FK → line_items (nullable)
  ins_item_id   UUID FK → line_items (nullable)
  classification ENUM(green, orange, blue, nugget)
  notes         TEXT          -- rationale annotation
```

## 3. Pipeline Steps

### Step 1 — PDF Parsing (Hybrid: LLM Vision + PyMuPDF)

Three-phase approach within a single `parse_document` call:

1. **Room splitting (LLM)** — Render each page to a 200 DPI image, send to LLM to identify which room sections appear on each page and whether they are new or continued. Returns a document-level room map (room name → page ranges).
2. **Line item extraction (LLM)** — For each page, send the image along with the known room context from phase 1. LLM extracts line items and assigns them to the correct room. Structured output via Pydantic `response_format`.
3. **Bbox location (PyMuPDF)** — For each extracted description, use `fitz.Page.search_for()` to find the text position on the page. Extend to full page width to represent the row region.

Splitting rooms first ensures consistent naming across pages (e.g. "CONTINUED - Bathroom" maps back to "Bathroom") and gives the extraction LLM explicit room context rather than requiring it to infer structure.

**Pydantic schemas** (`backend/app/schemas.py`):
- `ExtractedLineItem` — description, quantity, unit, unit_price, total, bbox `(x0, y0, x1, y1)`, page_number
- `ExtractedRoom` — room_name, line_items
- `ParsedDocument` — source (`"jdr"` | `"insurance"`), rooms

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
- For each line item, draw colored highlight rectangle over its row region using bbox from Step 1
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

All calls go through Ciridae Gateway (`https://llm-gateway-5q22j.ondigitalocean.app`).

| Call                | Model/Service              | Input                              | Output Format   |
|---------------------|----------------------------|------------------------------------|-----------------|
| PDF parsing         | `claude-3-5-sonnet`        | Page images + extraction prompt    | Pydantic schema |
| Room mapping        | `fast-production`          | Two room-name lists                | JSON array      |
| Description embeddings | `text-embedding-3-small` | All line-item descriptions         | Vector arrays   |

**Cost control:** Batch pages where possible for parsing. Embeddings are a single batch call per document. Matching is pure compute (cosine sim + Hungarian algorithm). Expect ~10-20 LLM calls + 2 embedding calls per job.

## 7. Key Design Decisions

- **LLM vision for PDF parsing** — Xactimate PDFs vary in layout; LLM vision handles tables, merged cells, and formatting inconsistencies without brittle heuristics
- **Embeddings for matching, code for math** — Embedding similarity + Hungarian algorithm gives fast, deterministic, cheap matching; ±2% numeric comparison stays as code
- **LLM only where irreplaceable** — Room mapping (fuzzy name resolution with splits/merges) and PDF parsing (vision) are the only LLM calls; everything else is compute
- **PyMuPDF for annotation** — Preserves original PDF layout; draws colored rectangles and text annotations precisely using bbox coordinates from parsing
- **Background processing** — PDF pipeline takes 30-90s; async avoids request timeouts

## 8. Tech Stack

- **Backend:** Python with `uv`, FastAPI
- **Database:** Postgres with SQLAlchemy 2.x
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
│   │   ├── models.py            # SQLAlchemy models
│   │   ├── schemas.py           # Pydantic schemas
│   │   ├── pipeline/
│   │   │   ├── parse.py         # PDF extraction
│   │   │   ├── room_mapping.py  # LLM room mapping
│   │   │   ├── matching.py      # Semantic matching + classification
│   │   │   └── annotate.py      # PDF markup generation
│   │   ├── llm.py               # Gateway client wrapper
│   │   └── db.py                # DB session + engine
│   ├── alembic/                 # Migrations
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
└── README.md
```