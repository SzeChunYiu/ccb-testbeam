# Study report: S<NN> — <title>

> Copy this file to `reports/S<NN>_<slug>/REPORT.md` and fill every section. A study is **not
> done** until all mandatory sections are complete. Delete these quote lines when you start.

- **Study ID:** S<NN>
- **Author (worker label):** <e.g. testbeam-laptop-1>
- **Date:** <YYYY-MM-DD>
- **Depends on:** <study IDs / reports>
- **Input checksum(s):** <sha256 of the ROOT/table files used>
- **Git commit:** <commit hash of the code that produced this>
- **Config:** <path to configs/ file>

## 0. Question
One sentence: exactly what is being measured/decided, and the atomic steps it breaks into.

## 1. Reproduction (mandatory — gate)
Reproduce the relevant number(s) from the existing notes, **from raw ROOT**, with an independent
script. Show a match table:

| Quantity | Report value | Reproduced | Δ | Tolerance | Pass? |
|---|---|---|---|---|---|

If it does **not** match, stop: the discrepancy is the finding. Document the likely cause.

## 2. Traditional (non-ML) method
Method, exact parameters, every cut/fit. Atomic validation plot/number for each step. Result
with **statistical + systematic** uncertainty, χ²/ndf where a fit is involved, and the **full
distribution** (not just a core σ).

## 3. ML method
Model, features, labels (and how defined), **split (by run)**, loss, **hyperparameter scan/CV**,
metrics. **Probability calibration** (reliability diagram) if a classifier. Bootstrap CIs for
small/imbalanced classes. State explicitly what the output *is* (e.g. "clean-timing probability,
not a truth label").

## 4. Head-to-head benchmark (mandatory)
Traditional vs ML on the **same held-out data** with the **same metric**. One table + one plot.

| Method | Metric | Value ± CI | Notes |
|---|---|---|---|

Verdict: does ML beat the strong baseline? By how much? Is it worth the complexity?

## 5. Systematics & caveats
What could bias this; what is assumed; where statistics are thin; leakage/circularity checks.

## 6. Findings & next steps
Bullet conclusions (quantitative). New tickets to cut (so the orchestrator can append them).

## 7. Reproducibility
Exact commands to regenerate every number/figure. List output artifacts written.
