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

## 5. Falsification (mandatory — guards against p-hacking)
- **Pre-registration:** state the metric and significance level you committed to **before**
  looking at the result (copy it from the ticket — it must predate the analysis).
- **Falsification test:** the one explicit test that would have shown your claim is wrong.
- **Result:** p-value / e-value **with multiple-comparison correction**. If you tried N cuts/
  models, say N and correct for it. A metric chosen *after* seeing the data is rejected.

## 6. Threats to validity (mandatory — the four classic failure modes)
Address each explicitly, even if to say "not applicable, because…":
- **Benchmark/selection:** is the comparison fair, the baseline strong (not a strawman)?
- **Data leakage:** split by **run** (never event-level shuffle); no label-defining variable in
  the features; calibration built only on calibration runs.
- **Metric misuse:** is the metric the right one; are you reporting full distributions, not just
  a core σ; χ²/ndf shown?
- **Post-hoc selection:** were cuts/bins/models chosen before or after seeing the outcome?

## 7. Provenance manifest (mandatory)
Commit a machine-readable `manifest.json` next to this report containing: input file sha256s,
git commit, container/env id, **every command run**, random seeds, and output file sha256s. The
orchestrator's acceptance check re-runs the manifest to confirm the headline number reproduces.

## 8. Findings & next steps (think like a scientist)
Quantitative conclusions. A hypothesis this suggests. For each queued follow-up ticket, give an
**expected-information-gain** justification (which open question it resolves and why this is the
most informative next step), not just "do more".

## 9. Reproducibility
Exact commands to regenerate every number/figure. List output artifacts written.

---
*A study is accepted only after a passing **Scientific Critic** review (see
[fleet/CRITIC_PROTOCOL.md](../fleet/CRITIC_PROTOCOL.md)). Check [fleet/LESSONS.md](../fleet/LESSONS.md)
before you start — it lists recurring mistakes to avoid.*
