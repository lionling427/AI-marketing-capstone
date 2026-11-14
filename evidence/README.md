# Evidence folder

| Required item | File |
|---|---|
| System diagram | [`system_diagram.png`](system_diagram.png) (source: `system_diagram.svg`) |
| Data-and-decision table (+ harmful error and safeguard) | [`data_and_decision_table.md`](data_and_decision_table.md) |
| Tests (method, baseline, criteria, results, revisions) | [`tests/README.md`](tests/README.md) · results table [`tests/test_results.md`](tests/test_results.md) · scripts `tests/run_evaluation.py`, `tests/run_before_revision.py` |
| Stakeholder findings (published evidence, design reviews, persona walkthroughs) | [`stakeholder_findings.md`](stakeholder_findings.md) |
| AI Use Record | [`ai_use_record.md`](ai_use_record.md) |
| Contributions | [`contributions.md`](contributions.md) |

**Labels used throughout.** *Synthetic*: all companies, people, lots and documents in `data/` are invented. *Simulated*: the inbox (a folder of `.eml` files released by a story clock) and the AI extraction (returns checked answers). *Not yet implemented*: real model call, real mailbox, user accounts, ERP integration, sending to the FDA. *Measured* vs *forecast* is marked in `tests/README.md`.
