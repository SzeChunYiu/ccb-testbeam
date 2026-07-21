# Latest Handoff

## Session

- **UTC:** 2026-07-21T22:09:00Z
- **Task:** AUD-ANOM-001 (PARTIAL)
- **Initial remote main:** `88c7d61ea7b59ad293956a93f06cab132f91b832`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Concurrent task avoided:** AUD-REPO-001, claimed by a LUNARC session at 2026-07-21T19:59:15Z

## Files and evidence inspected

- `WIKI.md`
- `docs/academic_chapters/09_anomaly_id.md`
- `docs/claim_ledger.csv`
- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/BACKLOG.md`
- previous `chatgpt_todo/HANDOFF.md` and `SESSION_LOG.md`
- current `main` history

## Confirmed scientific gap

The authoritative claim ledger now correctly classifies the 0.32% C12-dominated anomaly as truth-labelled MC evidence only, but the public narrative still overstates transfer to real data. The inspected repository evidence establishes:

- 283 early-peak tracks among 87,555 truth-labelled MC tracks, approximately 0.32%;
- an approximately 55% C12 fraction within that MC-selected anomaly class;
- a related real-data anomaly reported near 4%, more than an order of magnitude larger;
- no event-level species truth for the real-data anomaly in the inspected evidence.

Thus C12 is a candidate MC mechanism, not an empirically established data species assignment.

## Work pushed directly to main

1. Added `docs/validation/C12_DATA_MC_CLOSURE_SPEC.md`.
   - freezes data/MC populations, preprocessing, PCA/GMM configuration, random seeds, and the cross-domain classifier contract before final plots;
   - requires counts and two-sided 95% Wilson intervals for data and MC;
   - requires explicit data/MC rate effect size and goodness-of-fit testing;
   - requires matched morphology closure with identical binning and uncertainty panels;
   - separates MC C12 purity from efficiency;
   - defines preprocessing, model-choice, detector, run, and seed sensitivity studies;
   - defines negative controls, detector/run holdouts, required JSON/PDF artifacts, and explicit wording gates;
   - states that `C12 identified in data` requires an independent event-level tag or separately validated proxy with a measured confusion matrix.
2. Updated `chatgpt_todo/BACKLOG.md`.
   - changed `AUD-ANOM-001` from READY to PARTIAL;
   - linked acceptance to the new closure specification.
3. Appended the complete run record to `chatgpt_todo/SESSION_LOG.md`.

## Commits and main progression

- `4923f099be13bb3c85dec4c2e484f0fafb5eaaf7` — `docs(validation): specify matched C12 data-MC closure`
- `89d88e857850c8653e25fe7a0d664557ae663b98` — `docs(audit): link C12 closure acceptance contract`
- `a5d200ddd30e0fb9f09e1af1baf6a31e4dde2728` — `docs(audit): record C12 closure specification session`
- This handoff commit is the final remote-main commit for the session and must be confirmed after write.

## Validation

- The specification uses only already observed repository counts and evidence boundaries; it introduces no new measured or simulated result.
- Statistical requirements distinguish binomial interval estimation from a data/MC compatibility test.
- The method explicitly prevents independently fitted data and MC clusterers from masquerading as a primary closure test.
- No raw data, MC outputs, figures, cached tables, or generated binaries were modified.
- A direct local clone was attempted and failed with `Could not resolve host: github.com`; authenticated GitHub connector reads and writes were used instead.
- No Python, ROOT, Geant4, or data-analysis runtime result is claimed.

## Acceptance status

- **Closure study design:** COMPLETE.
- **Matched data/MC execution:** NOT_STARTED/BLOCKED on traceable inputs and compute.
- **Public wiki synchronization:** PARTIAL and still required.
- **Empirical C12 identification in data:** BLOCKED.

## Next action

Implement the frozen study contract using traceable data and MC inputs. First produce a cut-flow/provenance inventory and exact data anomaly count/denominator. Then run the frozen cross-domain morphology classifier, calculate Wilson intervals and data/MC rate effect size, generate the three required PDF artifacts and JSON summary, and update `WIKI.md` plus Chapter 9 only to the level supported by the resulting closure. Until then, retain `TRUTH_LEVEL_MC_ONLY` and hypothesis wording.
