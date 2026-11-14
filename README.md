# TraceReady

**Traceability records for produce distributors, ready before the FDA asks.**

TraceReady reads the paperwork a distributor already gets (supplier invoices, packing slips, bills of lading, pallet labels, signed delivery receipts and emails), turns it into FSMA 204 traceability records, chases what is missing, and produces the FDA's 24-hour sortable spreadsheet and a documented recall in minutes instead of days.

This folder is a working prototype: a web page, a small backend with a database, and a complete set of sample documents and emails that tell one story from start to finish.

---

## 1. The problem we solve

The FDA's Food Traceability Rule (FSMA 204) requires every company that receives or ships foods on the Food Traceability List (cucumbers, leafy greens, tomatoes, peppers, herbs and more) to keep **Key Data Elements** for each **Critical Tracking Event** and to hand them to the FDA **as an electronic sortable spreadsheet within 24 hours** of a request. The compliance date is July 20, 2028.

For a mid-size produce distributor today:

| Pain point | What it looks like on the warehouse floor |
|---|---|
| Records live on paper and in inboxes | The lot code is on a pallet label photo, the quantity on the packing slip, the supplier address on the invoice. Nobody has them in one row. |
| Supplier documents are incomplete or contradict each other | A smudged lot code, or the invoice says 50 cases and the dock counted 48. Someone has to email the supplier and remember to follow up. |
| Shipping records are not linked to receiving records | Which stores got lot RC-SLC-1109-07? Answering means digging through delivery receipts by hand. |
| A 24-hour FDA request is a fire drill | Building the FDA spreadsheet takes a day or more and is often incomplete. |
| Recalls are hard to prove | Calls, emails, photos and destruction forms end up scattered; the supplier and FDA want proof that every case is accounted for. |

## 2. Who it is for

- **Receiving clerks and inventory staff**: upload the documents, fix the problems TraceReady flags, sign off.
- **Food safety / QA managers**: review and sign records, answer the FDA, run recalls.
- **Operations managers and owners** of produce distributors and wholesalers (roughly 20–200 employees) who need to comply with FSMA 204 without buying an ERP.

## 3. What it does

| Feature | Where in the app |
|---|---|
| **Read receiving documents**: upload the supplier's invoice, packing slip, bill of lading and pallet label photo; TraceReady groups them into one receiving case and reads every field. | *+ New case* |
| **Find problems**: missing lot code, quantity conflicts between documents. | Step 3 of a case |
| **Resolve with the supplier**: draft and send the lot-code request, read the reply when it arrives, verify the lot from the label photo. | Step 4 |
| **Sign off** with an electronic signature and get the record in FDA template columns. | Step 5 |
| **Connected inbox**: emails from suppliers, stores, the FDA arrive automatically and are attached to the right case. | *Cases in progress* |
| **Record shipments from signed delivery receipts**: stores email back the receipt they signed; TraceReady reads customer, lot and quantity, checks the lot balance, and a person checks and signs before it is linked to the receiving record. | *Cases in progress → SH-2026-0131* |
| **History**: search completed records by date or lot code; each record shows the product flow (came from → our warehouse → went to), a Receiving tab and a Shipping tab with who signed each. | *History* |
| **Trace a lot** forward and back in one search. | *Trace & recall* |
| **FDA 24-hour request**: build the sortable spreadsheet (receiving and shipping tabs, FDA template columns) from the signed records and send it. | Incident INC-2026-0007 |
| **Recall**: block the lot, notify every store that received it, log calls, collect photos and signed destruction forms (AI reads them into a response sheet), report back to the supplier, sign and close. | Incident INC-2026-0007 |
| **Audit trail** on every case: who did what and when. | Right side of every case |
| **Three languages**: English, 中文, Español. | Top right |

## 4. Start it

You need **Python 3.8 or newer** (macOS: already installed if you have Anaconda; otherwise from python.org). Nothing else to install.

```bash
cd ~/Desktop/TraceReady/AI-marketing-capstone
python3 backend/app.py
```

The browser opens **http://localhost:8000** by itself. Stop the server with `Ctrl + C`.

- Every time the page is loaded, the story starts again from the beginning (the server resets the database from `data/`).
- You can also double-click `frontend/index.html` to run the same story without the server; in that mode nothing is saved to the database.
- If port 8000 is busy: `PORT=8010 python3 backend/app.py`.

## 5. Walk through the story (about 5 minutes)

The story follows one delivery of cucumbers from **Rio Claro Growers** to **Green Valley Produce** (our distributor) in Oakland, CA. Emails arrive on their own: a small notice appears at the bottom right with a **Go there →** button. While you wait, the story clock jumps ahead (3–5 seconds = hours or days in the story).

**Part 1 – Receiving with problems (Nov 10–12)**
1. On the first screen, click **Upload all**. The four Rio Claro documents are uploaded and grouped into case **TR-2026-0420**. Click **Confirm and continue →**.
2. **Check for problems →** then **Review problems →**. Two problems: the slicer cucumbers have **no readable lot code**, and the invoice says **50 cases** while the packing slip and dock count say **48**.
3. Quantity: choose **48 CS**, reason **Dock count**, **Save decision**.
4. Lot code: **Draft supplier request** → **Send request**. The case now waits in *Cases in progress*.
5. The supplier replies that they are still checking. Click **Send follow-up**.
6. The supplier replies with lot **RC-SLC-1109-07** and a label photo. Click **Verify and apply lot code** → **Continue to sign-off →**, type a name, sign in the box, tick the box, **Sign and complete**.

**Part 2 – Shipping (Nov 12–13)**

7. The three stores email back their **signed delivery receipts**. Open **SH-2026-0131** (notice or *Cases in progress*). Check the emails, the table the AI read and the lot balance (30 in / 30 out, 48 in / 48 out). Type your name, sign, tick the box, **Sign and link to TR-2026-0420**.

**Part 3 – FDA request (Dec 1)**

8. Three weeks later the FDA asks for 24-hour records on cucumbers from Rio Claro. Open the incident **INC-2026-0007**, **Build FDA spreadsheet** (2 receiving rows, 5 shipping rows, FDA template columns), **Send to FDA**.

**Part 4 – Recall (Dec 3–5)**

9. Rio Claro recalls slicer cucumbers lot RC-SLC-1109-07. **Block this lot (no receiving or shipping)** → **Send recall notice to all** (FreshWay Market #12, Hillcrest Grocery, Sunset Corner Market).
10. FreshWay and Hillcrest reply with photos and signed destruction forms. Sunset Corner does not reply within 24 hours: **Log call** → **Reached, will act today** → **Save call**. Its handwritten form arrives later.
11. **Confirm evidence** for each store (20 destroyed; 13 destroyed + 3 sold before notice; 12 destroyed), **Build recall report** → **Send to Rio Claro**. Rio Claro confirms.
12. Type your name, sign, tick the box and click **Sign and complete** to close the incident.

**Part 5 – Look it up later**

13. **History**: open **TR-2026-0420** with **View**: product flow for both lots, the Receiving tab (2) and Shipping tab (5) with the signatures. Copy any tab as CSV for Excel.
14. **Cases in progress** still shows **TR-2026-0412** and **TR-2026-0415**: older cases waiting on other suppliers. They stay *Pending* on purpose.

## 6. See the data behind the page

While the server runs, these links show what has been stored (open them in the browser):

| Link | Shows |
|---|---|
| http://localhost:8000/api/cases | All cases and their status |
| http://localhost:8000/api/history?lot=RC-SLC-1109-07 | Completed records for a lot |
| http://localhost:8000/api/trace/RC-SLC-1109-07 | Where a lot came from and went |
| http://localhost:8000/api/inbox | Emails that have arrived so far |
| http://localhost:8000/api/extractions | What the AI read from each document |
| http://localhost:8000/api/export/fda.csv?cte=shipping&lot=RC-SLC-1109-07 | FDA shipping spreadsheet (downloads a .csv) |
| http://localhost:8000/api/export/fda.csv?cte=receiving | FDA receiving spreadsheet |
| http://localhost:8000/api/signatures | Who signed what, and when |
| http://localhost:8000/api/compliance | Saved records that are missing a required Key Data Element |
| http://localhost:8000/api/validation | Every rule re-run on what the server holds |

## 7. What is in this folder

```
AI-marketing-capstone/
├── README.md            this guide
├── TECHNICAL.md         how the platform is built: structure, data model, fields, API
├── requirements-dev.txt optional developer tools (the app itself needs nothing)
├── frontend/            the web page (what you click) and its connection to the backend
├── backend/             Python server, database schema, inbox import, validation rules, FDA export
├── data/                the sample company: seed data, documents (PDF), emails (.eml), expected AI results
└── evidence/            system diagram, data-and-decision table, tests and results, AI Use Record, stakeholder findings, contributions
```

## 8. Data status

| What | Status |
|---|---|
| Companies, people, addresses, lots, quantities, documents, emails | **Synthetic.** Invented for the cucumber story; any resemblance to real businesses is accidental |
| FDA column layout, Key Data Elements, 24-hour spreadsheet | Real requirement (FSMA 204, 21 CFR Part 1 Subpart S) |
| Inbox | **Simulated:** `data/inbox/*.eml` released by a story clock |
| AI extraction | **Simulated:** returns the checked answers in `data/expected/` |
| Validation rules, approvals, signatures, database, FDA export | **Implemented** and tested (`evidence/tests/`) |

The page footer states the same in all three languages.

## 9. Known limitations

- Not connected to a real mailbox, ERP or the FDA; nothing is sent outside the computer.
- AI extraction accuracy, cost and speed on real documents are not measured yet.
- One user, no login. The signature is a drawn image plus name and time, not a certified e-signature.
- The pack-date rule for supplier lot codes assumes the supplier puts the pack date (MMDD) in the lot; it must be configured per supplier.
- A swap between two valid lots of the same delivery is caught only by the human check (see `evidence/data_and_decision_table.md`).
- `frontend/js/app.js` was built in layers during the demo iterations and should be split into modules before further development.
