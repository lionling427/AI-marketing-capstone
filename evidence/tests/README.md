# Evaluation

**Results table:** [`test_results.md`](test_results.md) (same data in `test_results.csv`; raw output in `raw_results.json`).

## What is being evaluated

TraceReady's job: turn the documents and emails a produce distributor already receives into FSMA 204 receiving and shipping records, and **stop a wrong record before it is signed**. The evaluation therefore tests two things:

1. **Do the rules catch the problems that matter** (missing lots, disagreeing quantities, wrong lot codes, shipments that do not match receiving, recall evidence that does not add up, missing Key Data Elements)?
2. **Does the prototype enforce human review** (a person must decide, and signing is blocked while a rule fails)?

**Not evaluated yet: AI extraction accuracy.** In this prototype the extraction step is simulated: it returns the checked answers in `data/expected/`. No accuracy, cost or latency figure for a real model is reported here. The test harness is ready for it: a real extractor can be scored field by field against the same files.

## Baseline

Today's process at the target customer (from Phase 1 research; to be confirmed by observation): paper documents and emails, re-typed into a spreadsheet or ERP form that accepts whatever is typed. Baseline results in the table describe what that process does with the same input; they are **described, not measured**. A measured baseline (timed clerk session on the same documents) is the next test.

## Method

- Cases were written **before** running, with an expected result and a pass criterion each (`run_evaluation.py`, dictionary `C`).
- Coverage required by the brief: normal (R1, R9, U1, U2, U4, U10), missing information (R2, U7, U9, U12), boundary / unusual (R3, R5, R7, R8, U6, U8), consequential harmful error (R4, R6, U3, U5), performance (U11).
- Two layers: **R** = rule functions in `backend/checks.py`; **U** = the running prototype in a headless browser (what the user sees and is allowed to do).
- The rules are deterministic, so one run decides each case; the full suite was run twice with identical results. Latency was repeated 10 times.
- The four risky cases U3, U5, U6, U8 were also run against the version before the revisions (`v14_before_revision.html`, `run_before_revision.py`).

**Pass criteria** (fixed before running): the observed result equals the expected result exactly. For U11, every repetition under 1 second. Overall success criterion: 100% of harmful-error cases blocked before signature; no false alarm on the normal cases.

## Results (measured)

| Measure | Result |
|---|---|
| Cases passed | **21 / 21** after revisions |
| Harmful-error cases blocked before signature | **4 / 4** (R4, R6, U3, U5) |
| False alarms on normal cases | **0** (R1, R9, U2, U4) |
| Same risky cases before revision (v14) | **4 / 4 failed**: wrong lot shown as "matched" and signable; over-shipment shown as "Balances"; duplicate lot could be applied; evidence that did not add up could be confirmed |
| FDA spreadsheet build (both cucumber lots, 2 receiving + 5 shipping rows) | page: under 1 ms; server CSV: about 1 ms median, under 10 ms max (10 runs) |
| End-to-end story (U10) | completes; server FDA CSV = on-screen spreadsheet, cell for cell |
| Human-review burden in the full story | 17 human actions, of which 3 e-signatures (receiving, shipment link, incident close) |
| Cost per run | $0 (local, no model calls). Real-model cost: **not measured** |

## Important failures and revisions

1. **Problem detection was scripted.** Before the evaluation, "missing lot" and "quantity conflict" were flags written into the demo data. Revision: they are now derived from the document fields (lot empty or unreadable; invoice qty ≠ packing-slip qty), and the flags were removed from `data/seed/`.
2. **Every shipment line showed "matched" and every lot "Balances"** regardless of the data (U5, U6 failed on v14). Revision: lines whose lot has no receiving record and lots shipped beyond what was received are marked, and signing is blocked.
3. **Any lot code from the supplier could be applied** (U3 failed). Revision: a code already used in the delivery, or whose date part does not match the pack date, cannot be applied.
4. **Recall evidence that did not add up could be confirmed** (U8 failed). Revision: confirm is replaced by a warning until destroyed + sold = received.

## False positives and false negatives

- **False negative (most serious):** a wrong lot accepted. Consequence: a store that received the recalled lot is not notified (U5). Blocked by the rules plus human sign-off. Remaining gap: a swap between two *valid* lots of the same delivery passes the lot rule (see the data and decision table).
- **False positive:** a correct record held up. Cost: clerk time. Example risk: rule R5 assumes the supplier encodes the pack date (MMDD) in the lot; a supplier that does not would trigger false alarms. This rule must be configured per supplier before real use.
- No confidence score is used. A model's confidence would not be a validated probability; the gate is the rule result plus a human signature.

## Forecasts (not measured)

- Time to answer an FDA records request: hours to days by hand vs minutes with TraceReady, assuming records were captured at receiving. To be measured with a customer's real request drill.
- Extraction accuracy on real, messy documents: unknown until a model is connected.

## How to rerun

```bash
python3 backend/app.py                          # terminal 1
pip install playwright && playwright install chromium
python3 evidence/tests/run_evaluation.py        # terminal 2, about 1 minute
python3 evidence/tests/run_before_revision.py   # optional: the four cases on the old version
python3 frontend/tests/e2e_story.py             # optional: full story, about 4 minutes
```
