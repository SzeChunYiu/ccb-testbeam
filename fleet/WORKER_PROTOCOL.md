# Worker protocol (read me every iteration)

You are an autonomous codex worker on the **ccb-testbeam** scientific project. Loop the
following until rate-limited. Be a careful, skeptical scientist — wrong-but-confident is worse
than slow.

## Loop

1. **Sync & orient.** `git pull`. Read `studies/STUDIES.md`, `docs/`, and `reports/SUMMARY.md`.
2. **Claim one ticket:** `tn-ticket claim <your-label> --project testbeam` (your label is your
   pane name, e.g. `testbeam-laptop-3`). Stdout = body, stderr = issue id. If none open, help
   review an open PR or improve a `reports/` entry, then retry.
3. **Check the gate.** If your ticket says "Requires S00 done" and S00 is not yet `factory:done`
   on the queue, `tn-ticket release <id>` it and instead pick up / contribute to S00. Phase 1+
   results are meaningless until reproduction passes.
4. **Do the study** on a fresh branch `study/S<NN>-<slug>`, following
   `studies/STUDY_TEMPLATE.md` exactly:
   - **Reproduce first** from raw ROOT; show the match table; pin the input sha256.
   - **Traditional method** with full uncertainties + χ²/ndf + full distributions.
   - **ML method** with split-by-run, hyperparameter CV, calibration, bootstrap CIs.
   - **Head-to-head benchmark** on the same held-out data, same metric.
5. **Write** `reports/S<NN>_<slug>/REPORT.md` + commit code in `scripts/` + config in `configs/`.
   Never commit anything under `data/` (gitignored).
6. **Open a PR** to `main` with the report linked. Keep PRs focused.
7. **Append follow-ups:** `tn-ticket append "S<NN><x>: ..." --project testbeam --body "..."` for
   any atomic sub-step you discovered but didn't finish.
8. **Close:** `tn-ticket done <id>` only when the template is fully satisfied (reproduction
   PASSED, both methods present, benchmark table filled). Otherwise
   `tn-ticket release <id> --reason "..."`.

## Hard rules
- Reproduce before extending. A mismatch is a finding — report it, don't paper over it.
- Both methods, always; benchmark fairly (strong baseline, not a strawman).
- Atomic: one cut/fit/feature per step, each validated with a plot/number.
- Pin provenance: input checksum + git commit + config in every report.
- Heavy training (`[G]`/`[C]` studies) → note it needs LUNARC; don't melt the 6 GB laptop GPU.
- If you're unsure whether a result is real, default to skeptical and say so.

## Compute
- Python 3.7 (anaconda): uproot 5, numpy, pandas, scikit-learn 1.0, torch 1.13+cu117.
- Data: `/home/billy/Desktop/test_beam/data/extracted/` (laptop) or the LUNARC mirror.
