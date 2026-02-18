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
    source: str                  # "jdr" | "insurance"
    rooms: list[ExtractedRoom]

class DiffNote(BaseModel):
    field: str                   # "unit", "quantity", "unit_price", "total"
    jdr_value: str
    ins_value: str

class MatchedPair(BaseModel):
    jdr_item: ExtractedLineItem
    ins_item: ExtractedLineItem
    color: MatchColor            # GREEN or ORANGE
    diff_notes: list[DiffNote]

class RoomComparison(BaseModel):
    jdr_room: str | None = None
    ins_room: str | None = None
    matched: list[MatchedPair]
    unmatched_jdr: list[ExtractedLineItem]   # BLUE
    unmatched_ins: list[ExtractedLineItem]   # NUGGET

class ComparisonResult(BaseModel):
    rooms: list[RoomComparison]
```

## 3. Pipeline Steps

### Step 1 — PDF Parsing (Hybrid: LLM Text + Vision + PyMuPDF)

Two-phase approach within a single `parse_document()` call:

1. **Room splitting (PyMuPDF text + text LLM)** — Extract page text via PyMuPDF `get_text()`, then send to `fast-production` (text-only, no vision) to identify room sections. Returns canonical room names per page with continuation flags (e.g. "CONTINUED - Bathroom" → "Bathroom"). Pages with little/no text are skipped. Photo pages and summary pages are filtered out by checking for table structure.
2. **Line item extraction (vision LLM)** — Only content pages (those with rooms) are rendered to 200 DPI PNGs via PyMuPDF, then sent to `claude-3-7-sonnet` with the known room list from phase 1. LLM extracts numbered line items with description, quantity, unit, unit_price, total, and assigns each to a room. Structured output via Pydantic `response_format`. Items with no pricing data are filtered out.
3. **Per-field bbox location (PyMuPDF, JDR only)** — For each extracted JDR line item, locate field positions on the page. Tracks claimed bboxes per page so each item gets a unique location (prevents double highlights):
   - `description` — Word-level matching via `get_text("words")`: splits the LLM-extracted description into words, finds the best matching word sequence on the page using fuzzy word comparison (handles curly quotes, punctuation, truncated words), skipping already-claimed regions. Returns the union bbox of all matched words. Handles multi-line descriptions naturally. Falls back to `search_for` with progressively shorter prefixes (60, 40, 25 chars) if word matching fails.
   - `quantity`, `unit_price`, `total` — Number search with comma formatting variants, constrained to the same row (±15pt vertical tolerance from description bbox).
   - `unit` — Text search constrained to the same row.

Each field gets its own tight `(x0, y0, x1, y1)` bbox. Insurance items skip bbox location since they are not highlighted on the JDR PDF.

**Pydantic schemas** (`backend/app/schemas.py`):
- `LineItemBboxes` — per-field bboxes: description, quantity, unit, unit_price, total
- `ExtractedLineItem` — description, quantity, unit, unit_price, total, bboxes (`LineItemBboxes`), page_number
- `ExtractedRoom` — room_name, line_items
- `ParsedDocument` — source (`"jdr"` | `"insurance"`), rooms

**LLM response models** (internal to `parse.py`):
- `_PageRooms` → `_RoomSection` (room_name, is_continuation)
- `_LLMPageItems` → `_LLMLineItem` (description, quantity, unit, unit_price, total, room_name)

### Step 2 — Room Mapping (LLM)

- Single LLM call (`fast-production`) with both room lists → returns 1:1 pairs via Pydantic structured output:
  ```json
  [
    {"jdr_room": "Kitchen", "ins_room": "Kitchen Area"},
    {"jdr_room": "Master Bedroom", "ins_room": "Bedroom 1"},
    {"jdr_room": "Garage", "ins_room": null}
  ]
  ```
- Pairs rooms 1:1 that refer to the same physical space; handles naming variations
- Rooms with no counterpart are included alone with `null` for the missing side
- Every room from both lists appears in exactly one pair

### Step 3 — Line-Item Matching + Classification (LLM + Code)

**Matching (LLM):** Per mapped room pair, an LLM call (`fast-production`) matches JDR items to insurance items by semantic similarity of descriptions. The LLM receives both item lists with descriptions, quantities, units, and prices, and returns 0-based index pairs. Each item can appear in at most one match.

**Classification (deterministic code):** For each matched pair, checks fields with unit-aware logic:

- **When units match** (e.g. both SF, both EA):
  - `quantity` — ±2% numeric tolerance
  - `unit_price` — ±2% numeric tolerance
  - All pass → **Green**; any fail → **Orange** with `DiffNote`s

- **When units differ** (e.g. LF vs SF, HR vs EA):
  - Quantity and unit_price are incomparable across different measurement systems
  - Flag the unit difference, then compare `total` (±2%) to assess overall cost alignment
  - Both unit and total flagged → **Orange** with `DiffNote`s for `unit` and `total`

- Unmatched JDR items → **Blue**
- Unmatched Insurance items → **Nugget**

### Step 4 — Annotated PDF Generation (PyMuPDF + LLM)

- Open the original JDR PDF with PyMuPDF
- For each line item, draw a single colored highlight over the description text:
  - Multi-line descriptions are split into per-line rects using `get_text("dict")` line boundaries for proper highlight rendering
  - Each item gets one highlight color (green, orange, or blue)
- **LLM-generated sticky notes:** One LLM call (`fast-production`) per room generates concise rationale comments (1-3 sentences each) explaining the match result, referencing specific quantities, prices, and insurance items
- **Nugget annotations:** Insurance-only items are placed as sticky notes (no highlights) at the bottom of each room's last JDR page, including the room name for context
- Save as new PDF

**Highlight colors:**
| Color | RGB | Meaning |
|-------|-----|---------|
| Green | `(0, 1, 0)` | Exact match with insurance |
| Orange | `(1, 0.5, 0)` | Matched but with field differences |
| Blue | `(0.5, 0.8, 1)` | JDR only, no insurance match |

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

1. **Upload** — Two drag-and-drop zones (JDR / Insurance) with file type validation, submit button
2. **Processing** — Stage-by-stage progress indicator (parsing JDR → parsing insurance → matching → annotating → complete), polls `GET /api/jobs/{id}` every 2s via React Query
3. **Results** — Summary stat cards (green/orange/blue/nugget counts), room-by-room collapsible breakdown showing matched pairs with diff notes and dollar totals, annotated PDF download button

## 6. LLM Usage

All calls go through Ciridae Gateway (`https://api.llmgateway.ciridae.app`).

| Call                 | Model               | Input                                         | Output Format   |
|----------------------|----------------------|-----------------------------------------------|-----------------|
| Room splitting       | `fast-production`    | Page text (PyMuPDF) + room ID prompt           | Pydantic schema |
| Line item extraction | `claude-3-7-sonnet`  | Page image + room context + extraction prompt  | Pydantic schema |
| Room mapping         | `fast-production`    | Two room-name lists                            | Pydantic schema |
| Line-item matching   | `fast-production`    | JDR + insurance item lists per room pair       | Pydantic schema |
| Comment generation   | `fast-production`    | Matched/unmatched items + context per room     | Pydantic schema |

**Cost control:** One text LLM call per page for room splitting + one vision call per content page for extraction. One text call each for room mapping and per-room matching. One text call per room for comment generation. Classification is pure deterministic code.

## 7. Key Design Decisions

- **LLM vision for PDF parsing** — Xactimate PDFs vary in layout; LLM vision handles tables, merged cells, and formatting inconsistencies without brittle heuristics
- **Text-based room splitting** — PyMuPDF extracts page text for room identification, avoiding expensive vision calls. Room headers are plain text and don't need image analysis.
- **Word-level bbox matching** — Uses `get_text("words")` with fuzzy word comparison instead of substring search, achieving high description coverage including multi-line wrapped text. Tracks claimed bboxes per page to prevent double highlights.
- **Two-phase LLM parsing** — Room splitting first gives the extraction LLM explicit context, ensures consistent room naming across pages, and avoids hallucinated room assignments
- **1:1 room mapping** — Rooms are paired one-to-one (or left unmatched with `null`), simplifying the pipeline and API compared to many-to-many grouping
- **LLM for semantic matching** — Construction item descriptions vary significantly in wording between proposals; LLM matching handles synonyms and reformulations (e.g. "Bathtub - Reset" ↔ "Install Bathtub") that string similarity would miss
- **Unit-aware classification** — When measurement systems differ (LF vs SF, HR vs EA), quantity and unit_price comparisons are skipped as meaningless; totals are compared instead to assess cost alignment
- **Deterministic classification** — Color assignment (green/orange) uses code with ±2% numeric tolerance, not LLM judgment, for consistency and auditability
- **Single color per item** — Each line item gets one highlight color on the description only, avoiding visual noise from per-field multi-color highlights
- **Inline nugget annotations** — Insurance-only items appear as sticky notes on the relevant room's last JDR page, matching the ground truth markup style
- **PyMuPDF for annotation** — Preserves original PDF layout; draws highlight annotations and sticky notes using bbox coordinates from parsing
- **Background processing** — PDF pipeline takes 30-90s; async avoids request timeouts

## 8. Tech Stack

- **Backend:** Python 3.13 with `uv`, FastAPI, PyMuPDF, Pydantic, OpenAI SDK
- **Frontend:** TypeScript, React 19, Vite
- **State/Data:** React Query (TanStack Query)
- **Styling/UI:** TailwindCSS, shadcn/ui
- **Validation:** Pydantic (backend) / TypeScript interfaces (frontend)
- **LLM Calls:** Ciridae LLM Gateway (OpenAI-compatible API)

## 9. Directory Structure

```
├── backend/
│   ├── app/
│   │   ├── schemas.py              # Pydantic schemas (data model + comparison types)
│   │   ├── llm.py                  # Gateway client (chat + vision_extract)
│   │   └── pipeline/
│   │       ├── parse.py            # PDF extraction (2-phase: rooms → items + bboxes)
│   │       ├── room_mapping.py     # LLM room mapping
│   │       ├── matching.py         # LLM semantic matching + deterministic classification
│   │       └── annotate.py         # PDF markup generation (highlights + LLM comments)
│   ├── eval_matching.py            # End-to-end eval against ground truth
│   ├── test_matching.py            # CLI test for full pipeline
│   ├── test_annotate.py            # Annotation test with cached data
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── App.tsx                 # Root component with state machine
│   │   ├── api/
│   │   │   ├── hooks.ts            # React Query hooks (create, poll, items)
│   │   │   ├── types.ts            # TypeScript interfaces (JobResponse, ItemsResponse)
│   │   │   └── mock.ts             # Demo mode mock data
│   │   └── components/
│   │       ├── UploadForm.tsx       # Dual PDF drag-and-drop
│   │       ├── JobStatus.tsx        # Processing stage indicator
│   │       ├── ResultViewer.tsx     # Results with room breakdown
│   │       ├── Header.tsx           # App header
│   │       ├── Aurora.tsx           # Background animation
│   │       └── ui/                  # shadcn/ui primitives
│   ├── package.json
│   └── vite.config.ts
├── documents/                       # Input PDFs (proposal sets)
├── DESIGN.md
└── README.md
```
