# AI / reviewer pickup guide — global scientific audit

**Start here before initiating any new CCB analysis study.** Parent coordination issue: #1594. Draft implementation PR: #1595.

## Required startup sequence

1. Read #1594 and identify the earliest unblocked scientific layer.
2. Read `chatgpt_todo/REDO_QUEUE.csv`; work P0 before P1/P2 unless a documented independent task does not depend on the blocked primitive.
3. Read `chatgpt_todo/NUMBER_AUDIT_LEDGER.csv`, `PHYSICS_JUSTIFICATION_LEDGER.csv`, `FIGURE_AUDIT_LEDGER.csv`, `CLAIM_EVIDENCE_MATRIX.md`, and `CODE_RESULT_MAP.md`.
4. Read `SCIENTIFIC_REVIEW_PROTOCOL.md` and assign four adversarial roles: detector/data, statistics/ML, simulation/physics, provenance/reproducibility.
5. Check the relevant domain issue: raw #1603, calibration #1604, timing #1605, energy/PID #1606, rate/saturation #1607, simulation #1608, statistics/ML #1609, census #1610, publication gate #1611, references #1612, WIKI figures #1613, study supersession #1614, reviewer protocol #1615.
6. Do not start downstream reruns while an upstream primitive is FLAWED/UNJUSTIFIED/BLOCKED unless the work is explicitly a diagnostic falsifier.

## Evidence rule

A result is not accepted because it reproduces, has a small error bar, high AUC/R², good-looking figure, or agrees with the same MC model used to construct the method. Every promoted result needs exact provenance, defensible physical/statistical formulation, uncertainty/systematics, hostile falsification and independent transfer/anchor where applicable.

## LLM rule

Treat all prior LLM-authored physical explanations, equations, causal mechanisms, parameter choices and citations as hypotheses until independently derived or verified against primary/authoritative sources and the detector configuration. Plausible prose is not evidence.

## How to close a checkbox

A checkbox may be changed to `[x]` only when:

- evidence is committed or linked immutably;
- the corresponding ledger row is updated;
- relevant dependencies are not unresolved;
- the evidence class and limitations are explicit;
- required reviewer verdicts are recorded for claim-authorizing results.

## Required output of each audit atom

- exact input identities/hashes;
- code/config/commit and command/environment where relevant;
- machine-readable sufficient statistics/result;
- physical/statistical derivation or primary reference;
- assumptions, units and validity domain;
- uncertainty/nuisance treatment;
- hostile falsifier(s) and result;
- dependency/supersession impact;
- updated issue checkbox + ledger status;
- figure/documentation changes only after the underlying atom is scientifically resolved.

## Recursive failure propagation

If an upstream primitive changes, do not ask whether downstream numbers remain visually similar. Reopen every dependent claim/study/figure/documentation item and prove either non-dependence or corrected recomputation.
