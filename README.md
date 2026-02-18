# Insurance Rebuttal

Compares a JDR contractor repair proposal against an insurance adjuster's estimate, matching line items room-by-room and producing an annotated PDF highlighting discrepancies.

## Quick Start

```bash
# Backend
cd backend
cp .env.example .env   # then edit .env and add your GATEWAY_API_KEY
uv sync
uv run uvicorn app.main:app --reload

# Frontend (in a separate terminal)
cd frontend
npm install
npm run dev
```

The backend runs on http://localhost:8000. The frontend runs on http://localhost:5173 and proxies `/api` requests to the backend.

### Environment Variables

The backend requires a `.env` file in `backend/` with:

```
GATEWAY_API_KEY=your_key_here
```

## Architecture

```
React/Vite Frontend  ──▶  FastAPI Backend
                          ├── PDF Parse (LLM vision + PyMuPDF)
                          ├── Room Mapping (LLM)
                          ├── Line-Item Matching (LLM)
                          ├── Classification (deterministic)
                          └── Annotated PDF Generation (PyMuPDF + LLM comments)
                               │
                          Ciridae LLM Gateway
```

## Pipeline

### Step 1 — PDF Parsing (`parse.py`)

Three-phase hybrid approach:

1. **Room splitting** — Each page is rendered at 200 DPI and sent to `claude-3-7-sonnet` to identify room sections (e.g. "Bathroom", "Garage"). Handles continuations across pages and filters out photo/summary pages.
2. **Line item extraction** — Pages with rooms are sent to the same vision model with the known room list as context. Extracts description, quantity, unit, unit_price, total, and room assignment via structured Pydantic output.
3. **Bbox location** — For JDR items, uses PyMuPDF's `get_text("words")` to locate each field's bounding box on the page:
   - **Description** — Word-level matching: splits the LLM-extracted description into words and finds the best matching word sequence on the page, returning the union bbox of all matched words. Handles multi-line descriptions, curly quotes, and truncated words. Falls back to `search_for` with progressively shorter prefixes.
   - **Quantity, unit_price, total** — Number search with comma formatting variants, constrained to the same row (±15pt vertical tolerance from the description bbox).
   - **Unit** — Text search constrained to the same row.

### Step 2 — Room Mapping (`room_mapping.py`)

Single LLM call (`fast-production`) with both room name lists. Groups rooms that refer to the same physical space (e.g. "Bathroom" ↔ "Hall Bathroom", "Bedroom 1" ↔ "Bedroom"). Handles splits, merges, and naming variations. Rooms with no counterpart get a group with an empty list on the other side.

### Step 3 — Line-Item Matching (`matching.py`)

Per mapped room group, an LLM call matches JDR items to insurance items by semantic similarity of descriptions. Each item can appear in at most one match.

**Classification** is deterministic code:
- **Green** — All fields match: unit (exact), quantity (±2%), unit_price (±2%)
- **Orange** — Matched but with field differences, recorded as `DiffNote`s
- **Blue** — JDR item with no insurance match
- **Nugget** — Insurance item with no JDR match

**Unit-aware comparison**: When units differ (e.g. LF vs SF, HR vs EA), quantity and unit_price are incomparable across measurement systems. Instead of flagging all three fields, the classifier flags the unit difference and compares totals to assess whether the overall cost aligns.

### Step 4 — Annotated PDF Generation (`annotate.py`)

- Opens the original JDR PDF with PyMuPDF
- Draws colored highlight annotations over each line item's description using the per-field bboxes from Step 1
- Multi-line descriptions are split into per-line rects using `get_text("dict")` line boundaries for proper highlight rendering
- **LLM-generated sticky notes**: One LLM call per room generates concise rationale comments (1-3 sentences each) explaining the match result, referencing specific quantities, prices, and insurance items
- Appends summary pages listing insurance-only (nugget) items grouped by room

**Highlight colors:**
| Color | Meaning | RGB |
|-------|---------|-----|
| Green | Exact match | `(0, 1, 0)` |
| Orange | Matched with differences | `(1, 0.5, 0)` |
| Blue | JDR only, no insurance match | `(0.5, 0.8, 1)` |
| Purple | Insurance only (summary pages) | `(0.75, 0.52, 1)` |

## Tech Stack

**Backend:** Python 3.13, FastAPI, PyMuPDF, Pydantic, OpenAI SDK, uv

**Frontend:** TypeScript, React 19, Vite, TailwindCSS, shadcn/ui, React Query, Zod

## Directory Structure

```
├── backend/
│   ├── app/
│   │   ├── schemas.py              # Pydantic data models
│   │   ├── llm.py                  # Gateway client (chat + vision)
│   │   └── pipeline/
│   │       ├── parse.py            # PDF extraction (3-phase)
│   │       ├── room_mapping.py     # LLM room mapping
│   │       ├── matching.py         # Semantic matching + classification
│   │       └── annotate.py         # PDF markup generation
│   ├── test_matching.py            # End-to-end pipeline test
│   ├── test_annotate.py            # Annotation test with cached data
│   └── pyproject.toml
├── frontend/
│   └── src/
│       ├── App.tsx                 # Root component with state machine
│       ├── api/                    # React Query hooks + Zod schemas
│       └── components/
│           ├── UploadForm.tsx      # Dual PDF dropzone
│           ├── JobStatus.tsx       # Processing stage indicator
│           └── ResultViewer.tsx    # Results with room breakdown
├── documents/                      # Input PDFs (proposal sets)
└── DESIGN.md                       # Design document
```
