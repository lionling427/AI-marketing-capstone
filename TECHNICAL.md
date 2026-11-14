# TraceReady – Technical design

This document explains how the prototype is built: the three parts and how they talk, the data model and every field we store, the API, and how to extend it. For what the product does and how to use it, see `README.md`.

---

## 1. Architecture

```
            Browser (frontend/)                          Server (backend/)                         Files (data/)
 ┌───────────────────────────────────┐       ┌──────────────────────────────────┐       ┌─────────────────────────────┐
 │ index.html + styles.css           │       │ app.py      HTTP server + routes │       │ seed/       company, lots,  │
 │ js/app.js   screens, story, i18n, │ HTTP  │ store.py    reset, sync, queries │ reads │             customers, ...  │
 │             signatures, FDA tables│◀────▶│ mailbox.py  inbox import + AI    │◀──────│ documents/  PDF + previews  │
 │ js/api.js   load data, import     │ JSON  │ fda.py      FDA columns, export, │       │ inbox/      .eml messages   │
 │             mail, save state      │       │             completeness check   │       │ expected/   checked answers │
 └───────────────────────────────────┘       │ schema.sql  → runtime/traceready.db (SQLite)       └─────────────────────────────┘
                                             └──────────────────────────────────┘
```

| Choice | Why |
|---|---|
| Python standard library only (`http.server`, `sqlite3`, `email`, `csv`) | Anyone can run it with `python3 backend/app.py`; nothing to install, nothing to break on a teacher's laptop. |
| SQLite, rebuilt from `data/` on every reset | The demo always starts from the same known state; the database file is disposable. |
| The page keeps the interaction logic; the server stores records | The page behaves exactly like the approved demo, while every case, event, signature and audit entry also lands in real tables that the API and exports read from. |
| Inbox = folder of `.eml` files | Real email format with real attachments. Replacing the folder with IMAP/Gmail later only changes `mailbox.load_inbox()`. |
| AI extraction behind one function | `mailbox.extract()` returns the checked answers in `data/expected/` (deterministic for demos); a model call can replace it and be scored against the same files. |

## 2. Runtime flow

**On page load** (`frontend/js/api.js`)
1. `POST /api/demo/reset`: the server deletes the database, runs `schema.sql`, loads partners, products, receiving documents, history and the two background cases from `data/seed/`, and loads every `.eml` from `data/inbox/` as *not yet arrived*.
2. `GET /api/bootstrap`: the page receives the seed data and puts it into its working state (supplier shipment, customers, shipments, history, open cases, story timeline, product descriptions, document picture URLs).
3. The first screen is drawn.

**When the story clock moves** (a story event fires every 3–5 seconds once its condition is met)
4. `POST /api/inbox/poll {until}`: every email whose `Date` is at or before the story clock is imported: `emails.imported_at` is set, each attachment becomes a `documents` row, and the extraction result is saved in `extractions`.

**After every change on screen**
5. The page builds a snapshot (`snapshot()` in `api.js`) and, 0.7 s after the last change and only if something changed, sends it with `POST /api/sync`. The server rewrites the case-derived tables: `cases`, `receiving_events`, `shipping_events`, `signatures` (PNG files in `backend/runtime/signatures/`), `audit_log`, `recall_contacts`, and recomputes `lots`.

**Without the server** (opening `frontend/index.html` directly) steps 1, 2, 4 and 5 are skipped: the page uses the identical copy of the data built into `app.js`.

### The story timeline (`data/seed/timeline.json`)

| Event | Story time | What arrives | Condition before it fires |
|---|---|---|---|
| ev1 | 2026-11-11 09:20 | Rio Claro: "still checking the lot code" | Lot request sent |
| ev2 | 2026-11-12 09:30 | Rio Claro: lot RC-SLC-1109-07 + label photo | Follow-up sent |
| ev3 | 2026-11-13 16:00 | 3 signed delivery receipts (emails dated 11-12 15:05, 15:40, 11-13 11:20) | Receiving case signed |
| ev4 | 2026-12-01 10:15 | FDA 24-hour records request | Shipments signed |
| ev5 | 2026-12-03 09:00 | Rio Claro recall notice | FDA spreadsheet sent |
| ev6 / ev7 | 2026-12-03 14:10 / 16:40 | FreshWay, Hillcrest replies (photo + destruction form) | Notices sent to all stores |
| ev8 | 2026-12-04 10:00 | Sunset Corner overdue (no reply in 24 h) | – |
| ev9 | 2026-12-04 15:20 | Sunset Corner reply (handwritten form) | A call was logged |
| ev10 | 2026-12-05 10:30 | Rio Claro confirms the recall report | Report sent |

## 3. Folder structure

```
frontend/
  index.html        page shell
  styles.css        design tokens and components
  js/app.js         screens, story events, translations (EN/中文/ES), signature pad, FDA tables
  js/api.js         bridge to the backend: load data, import mail, save state
  tests/e2e_story.py  plays the whole story in a headless browser and checks the database (optional, needs Playwright)
backend/
  app.py            HTTP server, static files, API routes
  store.py          reset + seed loading, sync, queries, trace
  mailbox.py        .eml parsing, inbox import, extraction
  fda.py            FDA template column map, CSV export, Key Data Element check
  checks.py         validation rules (receiving, supplier lot, shipment, recall), used by /api/validation and the tests
  schema.sql        database schema
  runtime/          created at start: traceready.db and signature PNGs (not committed)
data/
  seed/             JSON source data (section 5)
  documents/        receiving/ (invoice, packing slip, BOL, pallet label PDFs), shipping/ (signed delivery receipt PDFs), previews/ (pictures shown in the page)
  inbox/            11 .eml messages with attachments, in story order
  expected/         the correct extraction for each document
  tools/generate_documents.py   rebuilds documents/, inbox/ and expected/ from seed/ (needs reportlab)
evidence/
  system diagram, data-and-decision table, tests/ (evaluation scripts and results), AI Use Record, stakeholder findings, contributions
```

## 4. Database (`backend/schema.sql`)

All times are local story time in ISO 8601 (`2026-11-12T15:05:00`). Location blocks always use the same seven fields: `name, phone, street, city, state, zip, country`.

### 4.1 Master data

**trading_partners**: everyone we trade with, and ourselves

| Field | Meaning |
|---|---|
| id | row id |
| name | business name (unique) |
| role | `self`, `supplier`, `customer`, `regulator` |
| contact, email | person and address we write to |
| phone, street, city, state, zip, country | location description used in FDA records |

**products**: how each product is described in FDA records

| Field | Meaning | Example |
|---|---|---|
| name | product name | Slicer cucumbers |
| commodity | FDA commodity | Cucumbers |
| variety | variety | Slicer |
| pack_size | packaging size | 24 ct |
| pack_style | packaging style | Carton |
| gtin | GS1 trade item number | 10850022300049 |

**lots**: one row per Traceability Lot Code (recomputed after every sync)

| Field | Meaning |
|---|---|
| tlc | Traceability Lot Code (primary key, the link between receiving and shipping) |
| product, supplier, tlc_source | what it is, who sold it, who assigned the lot code |
| received_qty, shipped_qty, on_hand_qty | lot balance in cases |
| status | `active` or `recalled` (set when the lot is blocked in a recall) |

### 4.2 Work

**cases**

| Field | Meaning |
|---|---|
| id | `TR-…` receiving, `SH-…` shipment confirmation, `FDA-…` FDA request, `INC-…` incident/recall |
| kind | `receiving`, `shipping`, `fda_request`, `recall`, `incident` |
| status | `new_update` (something arrived), `pending` (waiting on someone), `complete` |
| title, supplier, products, lots | what the case is about |
| owner | who created it; signer: who signed it complete |
| created_at, updated_at, completed_at | for completed receiving cases, `completed_at` is the shipment confirmation time |
| reasons | JSON list: why it is still open (shown in *Cases in progress*) |

**audit_log**: `case_id, at, actor, action` (one line per step, e.g. *"Sent lot code request for Slicer cucumbers"*).

**signatures**: `case_id, step (receiving | shipping | incident), signer, signed_at, image_file`.

### 4.3 Sources

**emails**: `direction (in | out), message_id, event_key, case_id, from_addr, to_addr, subject, body, sent_at, imported_at, file`. An email with `imported_at = NULL` has not arrived yet in the story.

**documents**: `case_id, email_id, filename, doc_type, path, source (upload | email)`. Document types: `invoice, packing_slip, bill_of_lading, pallet_label, delivery_receipt, lot_label_photo, destroyed_photo, destruction_form`.

**extractions**: `email_id, source_file, kind, fields_json, method (fixture | llm), created_at`. Kinds and their fields:

| kind | fields |
|---|---|
| receiving_documents | supplier, supplierLocation, po, invoice, bol, shipDate, receiveDate, tlcSource; lines[product, gtin, packDate, unit, lotOnDocuments, qtyInvoice, qtyPackingSlip]; problems[type, product, …] |
| supplier_lot_reply | product, lot, evidence |
| delivery_receipt | customer, customerLocation, invoice, deliveryDate, receivedBy, lines[product, lot, qty, unit] |
| fda_request | commodity, supplier, from, to, deadlineHours |
| recall_reply | customer, lot, casesReceived, destroyed, soldBeforeNotice, method, signedBy |

### 4.4 FSMA 204 Critical Tracking Events

`receiving_events` and `shipping_events` follow the **FDA sortable spreadsheet template column for column** (36 columns each; headers in `data/seed/fda_columns.json`, mapping in `backend/fda.py`). The export writes the FDA header row and the columns in this order.

| # | Receiving column | Shipping column | FDA template header |
|---|---|---|---|
| 1–3 | tlc, quantity, unit_of_measure | same | Traceability Lot Code, Quantity, Unit of Measure |
| 4–9 | product_name, brand_name, commodity, variety, packaging_size, packaging_style | same | Product Description – … |
| 10–16 | prev_source_* (7 location fields) | recipient_* | Immediate Previous Source / Immediate Subsequent Recipient |
| 17–23 | received_at_* | shipped_from_* | Where the food was received / Location from which you shipped |
| 24 | receive_date (mm/dd/yyyy) | ship_date | Date received / Shipping date |
| 25–31 | tlc_source_* | same | Traceability Lot Code Source |
| 32 | tlc_source_reference | same | TLC Source Reference |
| 33–36 | ref_doc_type, ref_doc_number, ref_doc_type2, ref_doc_number2 | same | Reference Document Type/Number (invoice, bill of lading) |

Plus `case_id` (the receiving record) and, for shipping, `confirm_case_id` (the case where the delivery receipts were checked and signed).

`fda.REQUIRED` lists the Key Data Elements that must not be empty; `GET /api/compliance` reports rows that miss any. In the sample data it flags the older history records, whose reference documents were never entered: exactly the kind of gap the product is meant to catch.

**recall_contacts**: one row per store that received the recalled lot: `incident_id, lot, customer, contact, phone, delivered, invoice, cases_received, status (none → sent → replied → confirmed), overdue, calls (JSON), reply_at, destroyed, sold_before_notice`.

**demo_state**: `clock` = the story's current time.

## 5. Seed data (`data/seed/`)

| File | Contents |
|---|---|
| company.json | Green Valley Produce: location, team, inbox address |
| receiving_shipment.json | The Rio Claro delivery (case TR-2026-0420): PO, BOL, invoice, dates, supplier location, TLC source, lines (product, printed lot, `realLot` sent later by email, invoice and packing-slip quantities, GTIN, pack date), documents |
| receiving_documents.json | Field layout of the invoice, packing slip, BOL and pallet label (used to draw the PDFs) |
| customers.json | The three stores: location, contact, cases of the recalled lot, recall outcome |
| shipments.json | Deliveries per invoice: lines `[product, lot, cases]`, receipt file, email time |
| history.json | Records completed before the story (TR-2026-0398 … 0409) |
| open_cases.json | TR-2026-0412 and TR-2026-0415: waiting on other suppliers, stay *Pending* |
| timeline.json | Story events and the recalled lot |
| product_descriptions.json | Commodity, variety, pack size, pack style per product |
| fda_columns.json | The FDA template headers for both tabs |
| email_text.json | English text of every email |
| background_scenarios.json | Documents of the background cases |

Times inside seed files are written `{"$t": "2026-11-12T15:05:00"}` (local time) so the story shows the same clock times in every time zone.

To change the story, edit `seed/`, then run `python3 data/tools/generate_documents.py` to redraw the PDFs, emails and expected answers.

## 6. API

All responses are JSON unless noted. Base URL `http://localhost:8000`.

| Method | Path | Purpose |
|---|---|---|
| POST | /api/demo/reset | Rebuild the database from `data/` |
| GET | /api/bootstrap | Seed data for the page |
| POST | /api/inbox/poll `{"until": "2026-11-12T10:00:00"}` | Import emails that have arrived by that time |
| POST | /api/sync | Save the page's working state (snapshot format in `api.js → snapshot()`) |
| GET | /api/health | Server status and story clock |
| GET | /api/cases`?status=pending` | Cases |
| GET | /api/cases/{id} | One case with its receiving/shipping events, signatures, audit and documents |
| GET | /api/history`?date=2026-11-10&lot=RC-SLC` | Completed records by date (created or completed) or lot |
| GET | /api/lots | Lot balances and status |
| GET | /api/trace/{tlc} | Came from / went to for a lot |
| GET | /api/inbox`?all=1` | Arrived emails (`all=1` includes not-yet-arrived) |
| GET | /api/emails/{id}/attachments/{n} | Download an attachment |
| GET | /api/documents | All source files |
| GET | /api/extractions | AI results |
| GET | /api/signatures, /api/signatures/{file}.png | Signatures and their images |
| GET | /api/audit`?case=TR-2026-0420` | Audit trail |
| GET | /api/recall | Recall contacts and outcomes |
| GET | /api/compliance | Rows missing required Key Data Elements |
| GET | /api/validation | All rules in `checks.py` re-run on the extractions and saved records |
| GET | /api/export/fda.csv`?cte=receiving|shipping&lot=&from=&to=&case=` | FDA sortable spreadsheet (CSV download). `from`/`to` filter on the event date (YYYY-MM-DD) |
| GET | /files/{path} | Files under `data/documents/` |

## 7. Frontend notes

- `app.js` renders every screen as HTML strings into `#app`; buttons carry `data-a` ids that map to functions (`A(fn)`). One state object `S` holds the cases, history, shipments, incident and story clock.
- The file was built in layers during the demo iterations (marked `// ---- vN: … ----`); later layers redefine earlier functions. Splitting it into modules per screen is the first refactor to do.
- `api.js` changes nothing on screen. It wraps three functions: `render0` (to save after each change), `playNext` (to import mail when the clock moves) and the four document-picture functions (to load pictures from `data/documents/previews/`).
- Downloads: on screen, spreadsheets are copied to the clipboard (paste into Excel). With the server running, the same data downloads as CSV from `/api/export/fda.csv`.

## 8. Validation rules

The same rules run on screen (`app.js`, block `v15`) and on the server (`backend/checks.py`):

| Rule | Where it stops the user |
|---|---|
| Lot unreadable or missing (empty or contains `?`) | Receiving record cannot be signed until a lot is applied |
| Invoice quantity ≠ packing-slip quantity | A person must choose the quantity and give a reason |
| Supplier's lot already used in the delivery, or its date part ≠ pack date | "Verify and apply lot code" is not available |
| Shipped lot has no receiving record | Line marked; shipment cannot be signed |
| More cases shipped than received | Lot marked; shipment cannot be signed |
| Recall form: destroyed + sold ≠ received | "Confirm evidence" replaced by a warning |
| Required Key Data Element empty | Listed by `/api/compliance` |

Problems are derived from the document fields; the seed data contains no "problem" flags.

## 9. Verifying it

The full evaluation (21 cases, baseline, before/after revision) is in `evidence/tests/`.


`frontend/tests/e2e_story.py` (needs `pip install playwright` and `playwright install chromium`) starts from a running server, plays the whole story in a headless browser, then checks through the API that:

- TR-2026-0412 and TR-2026-0415 are the only open cases and are `pending`;
- three signatures exist (receiving, shipping, incident);
- all 11 emails were imported and 9 extractions saved;
- lot RC-SLC-1109-07 shows 48 received, 48 shipped and `recalled`;
- the server's FDA CSV for TR-2026-0420 equals, cell for cell, the spreadsheet shown on screen (2 receiving rows, 5 shipping rows).

## 10. Next steps toward a real product

1. **Real inbox**: replace `mailbox.load_inbox()` with an IMAP or Gmail API reader; match emails to cases by invoice/PO/lot instead of the `X-TraceReady-Case` header.
2. **Real extraction**: in `mailbox.extract()`, send PDFs/images to a vision model, keep `method='llm'`, and score it against `data/expected/`.
3. **Server-side state**: move case actions (send request, apply lot, sign) into API endpoints so the server, not the page, owns the workflow; then add users and login.
4. **Inferred links**: when a pick sheet has no lot code, propose the lot by product, date and on-hand balance, and ask a person to confirm.
5. **Excel export** (.xlsx, one tab per event) and a direct e-mail to the FDA contact.
