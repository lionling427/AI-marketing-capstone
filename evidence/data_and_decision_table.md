# Data and decision table

What data TraceReady touches, why, who may see it, how sensitive it is, how long it is kept, what the system may do on its own, and who must approve. All data in the prototype is **synthetic** (fictional companies, lots and people).

| Data source | Purpose | Access rights | Sensitivity | Retention | Permitted actions (system on its own) | Approval required | Human owner |
|---|---|---|---|---|---|---|---|
| Supplier documents: invoice, packing slip, bill of lading, pallet label photo (upload) | Read the receiving Key Data Elements (lot, product, qty, dates, source) | Receiving + QA staff of the distributor | Business confidential (prices, volumes) | 2 years after the record is created (FSMA 204, 21 CFR 1.1455(d)) | Extract fields; flag missing lot or quantity conflicts | Quantity choice + reason; lot verification; e-signature on the record | Receiving lead |
| Supplier emails (lot-code replies + label photo) | Fill a missing lot code | Case owner, QA | Business confidential | With the record (2 years) | Import; attach to the case; read the lot; check duplicate lot and pack date | Person verifies the lot against the photo before it is applied | Case owner |
| Store emails: signed delivery receipts | Record the Shipping event (who received which lot, how many cases) | Shipping + QA | Business confidential; receiver names (personal data, low) | 2 years | Import; read customer, invoice, lot, qty; match lot to receiving; check lot balance | Person checks and e-signs before shipments are linked; **signing is blocked** if a lot has no receiving record or more was shipped than received | Shipping lead |
| FDA records request | Start the 24-hour response | QA manager | Regulatory, confidential | Permanently with the incident | Build the sortable spreadsheet from signed records only | QA manager reviews and sends | QA / food safety manager |
| Recall notice (supplier) and store replies: photos + signed destruction forms | Prove every recalled case is accounted for | QA manager | Confidential; store staff names and signatures (personal data) | Permanently with the incident | Import; read counts into the response sheet; flag overdue stores; flag forms whose numbers do not add up | Block the lot; send notices; log calls; confirm each store's evidence; send report; e-sign to close | QA / food safety manager |
| Master data: trading partners, products, FDA columns | Location and product descriptions in every record | Admin | Business internal | While active + 2 years | Read only | Changes by admin | Operations manager |
| E-signatures + audit trail | Who confirmed what, when | QA, auditors | Personal data (name, drawn signature) | With the record they sign | Record every action automatically | – (cannot be edited) | QA manager |
| AI extraction results (`extractions`) | Show what was read and from where | Case owner | Same as the source document | With the record | Propose values only | Every value reaches a record only through a human step above | Case owner |
| FDA export (CSV) | Answer the FDA within 24 h | QA manager | Regulatory, confidential | Copy kept with the incident | Generate on request | Sending is a human action | QA manager |

**What the AI may never do on its own:** change a quantity, apply a lot code, link a shipment, confirm recall evidence, send anything outside the company, or sign. In the prototype the AI step is simulated (it returns checked answers from `data/expected/`); the rules and approval gates are real code.

## A consequential harmful error and its safeguard

**Error:** the AI misreads the lot on a store's signed delivery receipt (for example `RC-SLC-1109-01` instead of `RC-SLC-1109-07`). The shipment is linked to the wrong lot, so when lot `-07` is recalled that store is **missing from the recall list** and the product stays on sale. This is a false negative with a public-health consequence.

**Safeguards (tested in `tests/`, cases R6, U5, R7, U6):**
1. A shipped lot must exist in a signed receiving record; otherwise the line is marked "No receiving record".
2. Shipped cases per lot may not exceed received cases.
3. While either rule fails, the Sign button stays disabled; a person must check the receipt image against the table and sign.
4. Every link carries the signer, time and source email in the audit trail, so a later error can be traced back.

**Residual risk (not caught):** a misread that turns one valid lot into *another valid lot in the same delivery* (e.g. slicer → English cucumber lot) passes rule 1. Rule 2 catches it only if the totals then exceed what was received. The human check of the receipt image is the remaining safeguard. Next test: measure how often reviewers catch a seeded swap of this kind.

**Why the AI is still worth it:** without it, a clerk retypes every receipt and the same misread happens by hand, with no rule to catch it (baseline column in `tests/test_results.md`).
