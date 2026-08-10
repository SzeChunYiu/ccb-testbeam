# Active Task

- **Task ID:** `ARU-MC01-EVENT-STAVE-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T140500Z`
- **Remote main at branch point:** `d088b5a886e0c8891d7926af7015193db7a503b8`
- **Parent issues:** `#1052`, `#1164`; inferential parent `#1049`; weight dependency `#880`.
- **Branch / PR:** `feat/mc01-event-stave-truth-contract` / `#1169`.
- **Selected atom:** legacy MC charged hit/step rows -> generator-event identity + trigger-membership graph -> one event weight -> per-event/per-B-stave deposited-energy intermediate.
- **Exact measurand:** `E_dep(e,k)=sum_h EDep_h I(event=e, arm=B, layer=k)` in MeV. A separate charged-only sum is retained diagnostically. Statistical unit is one generator event.
- **Resolved local mechanisms:** raw hit rows are rejected as an invariant DATA-comparison unit; transport-step splitting leaves event/stave EDep unchanged while changing row multiplicity. Sample I is retained as a bit inside the Sample-II event universe rather than duplicated as a second row. The legacy `EDEP_CAP=600000` prefix retention is absent from the replacement product.
- **Implemented contract:** new `truth/event_stave.py` + `scripts/mc01_event_stave_truth.py` produce schema `mc_event_stave_edep_v1`, stable source-content event IDs, one PrimaryWeight/event, Sample-I/Sample-II bits, eight B-stave all-particle EDep totals, charged-only diagnostics, source SHA/descriptor identity and ESS. Source hashing and Uproot consumption use one opened regular file with a post-consumer stability gate.
- **Tests/falsifiers:** step splitting, multi-record aggregation, neutral-vs-charged deposit, A-arm exclusion, malformed EDep/layers, invalid weights, duplicate IDs, broken trigger nesting, source mutation, and a mocked Uproot file-like integration. Private isolated aggregation harness: 16 passed with builder integration excluded; this is not repository validation.
- **Expert votes:** detector/Geant4 `ACCEPT H3 / BLOCK detector closure`; adversarial `ACCEPT bounded contract / REVISE production-scale execution`; statistics `ACCEPT statistical unit / BLOCK p-value`; claims/provenance `ACCEPT nonauthorising provenance / BLOCK promotion`.
- **Scientific boundary:** schema is `NONAUTHORISING_TRUTH_DIAGNOSTIC`; quenching, optical/WLS, SiPM, electronics, digitizer sampling and identical DATA-like reconstruction are absent. No production ROOT/Geant4 result or detector metric was generated.
- **Current gate:** require exact-head/current-base MC Validation CI for PR #1169 before merge. #1052/#1164 remain open even after H3 because H4/H5 and real-product validation remain.
- **Next:** after CI/merge, run the producer on immutable production MC bytes and record exact hashes/counts/weights/ESS/resource use; compare H1 vs H3 only as a mechanism diagnostic; then implement stepwise quenching/visible-energy H4 before optical/digitized H5 and any return to #1049 inference.
- **Status:** `ACTIVE / PARTIAL`
