# AI Use Record

Two kinds of AI are involved: AI tools we used to build the project, and AI inside the product.

## 1. AI tools we used to build the project

| Tool | Used for | How we worked with it | What we checked or changed | Reviewed by |
|---|---|---|---|---|
| ChatGPT (OpenAI) | Phase 1 research and memo drafting: customer switching and adoption strategy, pricing questions and risks, competitor scan | We gave it our research questions and the sources we had found, asked for structured comparisons (evidence → finding → implication), then rewrote the memos in our own words | The memos cite a source for each statistic and price (switching-cost meta-analysis, PFT–FDA roundtable, FDA tabletop exercises, iFoodDS public pricing) and label unsourced points as hypotheses (e.g. our $79 / $179 price points) | LinLin, Jessie |
| Claude (Anthropic) | Phase 2 build: turned our 5-minute demo story into a clickable prototype (screens, three languages, signatures, recall flow); split it into frontend, backend and data; wrote the Python server, SQLite schema, inbox import, FDA export and validation rules; generated the synthetic documents, emails and checked answers; wrote and ran the test harness; drafted documentation | We worked in short iterations: one of us described a change in plain language (often with a screenshot of the current screen), Claude implemented it, and we clicked through the result before the next request. About 40 rounds in total | We redirected the design many times, for example: one continuous cucumber story instead of three separate scenarios; no warehouse stock, so every case is shipped; shipments must come from documents, not appear by themselves; a human check and signature before shipments are linked; fewer help icons; background cases that stay Pending. The evaluation then found four failures in the generated prototype, which were fixed and re-tested (`tests/README.md`) | All members; code areas reviewed by their owners (Jenny data, Gift backend, Norhelia frontend) |

**Facts we verified ourselves, not taken from AI output:** FSMA 204 Key Data Elements and Critical Tracking Events, the 24-hour electronic sortable spreadsheet and 2-year retention (21 CFR 1.1455), the FDA template columns, and recall communication duties (21 CFR 7.49). Cross-checked against FDA's Food Traceability Rule materials and the FDA sortable spreadsheet template during Phase 2.

**Known limits of AI-generated work in this repo**
- `frontend/js/app.js` was built in layers (`// ---- vN ----`), and later layers redefine earlier functions. It works and is tested end to end, but should be split into modules before further development.
- All business data is synthetic. Names, addresses and email domains are invented.

## 2. AI inside the product

| Item | Description |
|---|---|
| AI task | Read supplier documents, store receipts, recall forms and emails into structured fields (lot code, product, quantity, dates, customer, destroyed / sold counts) |
| Why AI | Inputs are unstructured and vary by supplier (PDF invoices, label photos, handwritten forms). Templates and OCR rules break on each new layout; a vision-language model reads them without per-supplier setup |
| Simpler alternative considered | Manual entry into a spreadsheet (today's baseline) or fixed OCR templates per supplier. Rejected as the main path because of setup cost per supplier; kept as a fallback for suppliers that send structured EDI |
| Configuration in the prototype | **Simulated:** `backend/mailbox.py → extract()` returns the checked answer from `data/expected/` (`method = 'fixture'` in the `extractions` table) |
| Planned configuration | One vision-capable model call per document with a fixed output schema (the same fields as `data/expected/`), temperature 0, every field linked to its source document |
| What the AI may do on its own | Propose field values and attach documents to a case |
| What requires human approval | Quantity decisions, applying a lot code, linking shipments, confirming recall evidence, sending anything outside the company, every signature (see `data_and_decision_table.md`) |
| Safeguards independent of the AI | Rules in `backend/checks.py`; signing blocked while a rule fails; audit trail |
| Status | Not yet implemented with a real model. No accuracy, cost or latency is claimed |
