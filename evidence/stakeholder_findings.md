# Stakeholder findings

Our Phase 2 stakeholder evidence comes from three sources, kept apart so measured findings are not confused with assumptions:

| Source | What it is | Status |
|---|---|---|
| A. Phase 1 secondary research | Industry roundtable, FDA tabletop exercises, B2B switching research, competitor offers | Published evidence |
| B. Internal design reviews | The team clicked through every prototype version and recorded what was confusing or wrong | Real, done by the team |
| C. Persona walkthroughs | Team members role-played three target users, built from source A, through the full demo | Done by the team |

## A. What published evidence says about the users

| Finding | Source | Implication for the product |
|---|---|---|
| Distribution channels struggle with manual work, mixed pallets, limited IT budgets and data management | PFT–FDA industry roundtable, 2026 (Phase 1 ref. 4) | Start from documents they already receive; nothing for the customer to install |
| Coordination across the supply chain mattered more than any single technology | FDA traceability tabletop exercises, 2026 (Phase 1 ref. 5) | Build the whole chain (receiving → shipping → FDA → recall), not one screen |
| Relational and procedural switching costs predict staying with an incumbent | Switching-cost meta-analysis and B2B research (Phase 1 refs. 1–2) | Do not ask customers to replace their ERP; export FDA CSV |
| Stated intentions are not observed switching | Phase 1 ref. 3 | Measure adoption by a paid proof of value, not by "would you use it" |
| The main competitor already offers hands-on support at $2,500/year | iFoodDS public offering (Phase 1 refs. 6–7) | Compete on a measured outcome, not on support alone |

## B. Internal design reviews (about 40 rounds on the prototype)

| What we saw in the prototype | Why it mattered | Design change |
|---|---|---|
| Three unrelated demo scenarios felt like separate products | Viewers could not follow one lot through the chain | One continuous cucumber story from receiving to recall |
| Shipment records appeared without any source document | Not credible: where did the data come from? | Shipments now come from store-signed delivery receipts emailed back |
| Shipments were linked to the receiving record without anyone checking | The same risk as trusting AI with lots | Human check and e-signature before linking; the signer shows in History |
| Invoices were treated as coming from stores | Wrong direction: the distributor issues invoices | Stores return the signed delivery receipt instead |
| A question-mark help icon on almost every element | Screens felt cluttered | Help kept only for document names and technical terms |
| A step asking who the case owner is | Redundant: the signer is recorded at sign-off | Owner picker removed; signer recorded at each signature |
| Warehouse stock left after the recall | Made the recall story harder to follow | All 48 cases shipped; recall is about stores only |
| Background cases kept receiving new updates | Distracted from the main story | They stay Pending, waiting on other suppliers |
| Quantities shown in one place disagreed with another | Undermines trust in the record | Every count derives from the confirmed receiving quantity |

## C. Persona walkthroughs

Each persona was written from source A, then one team member walked through the full demo in that role and recorded reactions.

| Persona (fictional) | Task walked through | Reaction in role | Objection raised | What we changed or plan |
|---|---|---|---|---|
| **Receiving clerk**, mid-size produce distributor, 6 years on the dock, paper log + Excel | Receive the Rio Claro delivery; resolve missing lot and 50 vs 48 | "I like that it tells me what's wrong before I sign, not after." | "If the AI reads the lot wrong and I'm busy, I'll just click through." | Signing is blocked while a rule fails; the misread-lot case became our main harmful-error test |
| **QA / food-safety manager**, responsible for FDA requests and recalls | Answer the FDA 24-hour request; run the recall | "The spreadsheet in one click is the part I'd show my boss." | "Can I prove every case is accounted for, including what was sold before the notice?" | Recall response sheet with destroyed + sold per store; confirm blocked when totals do not add up |
| **Owner / operations manager**, 45 employees, no IT staff | Watch the 5-minute demo; consider price | "If it works with the emails we already get, my team doesn't have to learn a new system." | "I'm not replacing my ERP, and I won't pay before I see it on our own paperwork." | Positioning as a complement; $199 30-day proof of value on their documents (to be tested) |

## What we still need to learn from real stakeholders

1. Do stores in practice email back signed delivery receipts, or do drivers bring paper back?
2. How many clerk minutes does receiving take today, and how many with TraceReady?
3. Who signs the purchase: owner, operations or QA?
