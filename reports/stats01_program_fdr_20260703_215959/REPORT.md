# STATS01 — Program-level FDR pass over all delta-CI claims

- **Date:** 2026-07-03 21:59:59
- **Input:** 443 `reports/*/result.json` artifacts
- **Procedure:** Benjamini-Hochberg at q = 0.05 within claim family; p-values from a normal approximation of each bootstrap CI (`se = (hi - lo) / (2 x 1.96)`, two-sided).
- **Motivation:** External Review 2026-07-02 section 4 — ~238 adaptive studies on one dataset, no multiplicity control; ~12+ chance wins expected among thousands of CIs.

## Caveats (read first)

- The normal approximation understates tail p-values for skewed percentile bootstrap CIs, and most underlying bootstraps iid-resampled dependent residuals (CIs ~ sqrt(1.5) too narrow per the review), so **the BH survivor counts below are an upper bound on trustworthy wins**.
- Claims are *every* delta-with-CI in the artifacts (method deltas, ablations, strata), not only headline claims; the per-family BH is therefore stricter than a headline-only correction, which is the intended posture after an adaptive program.
- Four extraction patterns are used (column `pattern` in `claims.csv`): A = delta-named `*_ci` key; B = delta-named scalar with a CI sibling; C = `{value, ci_low, ci_high}` rows whose metric name is delta-like (delta/minus/excess/shift); D = **derived unpaired** ML-vs-traditional delta from two independent per-method CIs (`se = hypot(se_ml, se_trad)`) — pattern D ignores the positive correlation of paired evaluation, so it is conservative (too wide), whereas patterns A-C inherit the underlying (often too-narrow) bootstrap.
- This census supersedes the 137-row `reports/SUMMARY.md` sample as the claim-level record.

## Parse accounting (no silent drops)

- Artifacts found: **443**
- Artifacts no delta ci claims: **244**
- Artifacts with claims: **199**
- Claims parsed: **1925**
- Claim-level `ci_key_not_2list`: 53
- Claim-level `ci_zero_width`: 180
- Claim-level `delta_metric_value_without_ci`: 4
- Claim-level `derived_unpaired_ml_vs_traditional`: 83
- Claim-level `ml_traditional_values_without_both_cis`: 14
- Claim-level `point_estimate_from_midpoint`: 157
- Claim-level `study_id_from_dirname_or_unknown`: 4
- Artifacts with zero extractable delta-CI claims are listed in `artifacts_without_claims.txt` (244 files); these include verdict-only, count-only, and classifier-metric-only artifacts.

## Family summary (BH at q = 0.05 within family)

| Family | Studies | Claims | Nominal CI-excludes-zero | Survive BH | Survival rate of nominal |
|---|---|---|---|---|---|
| amplitude-charge | 25 | 738 | 462 | 419 | 91% |
| pedestal | 14 | 272 | 227 | 222 | 98% |
| pid | 5 | 30 | 18 | 17 | 94% |
| pileup | 31 | 183 | 123 | 121 | 98% |
| representation | 27 | 409 | 372 | 372 | 100% |
| timing | 46 | 293 | 217 | 196 | 90% |
| **total** | 148 | **1925** | **1419** | **1347** | 95% |

## Scoreboard bold wins vs BH

The rolling scoreboard (`reports/SUMMARY.md`) marks 17 rows as bold ML wins. Per-study verdicts against the family-level BH pass:

| Win study | Family | Parsed claims | Nominal wins | BH survivors | Verdict |
|---|---|---|---|---|---|
| S01 | representation | 2 | 2 | 2 | survives BH (at least one claim) |
| S02 | timing | 1 | 1 | 1 | survives BH (at least one claim) |
| S03b | timing | 3 | 1 | 1 | survives BH (at least one claim) |
| S03e | timing | 5 | 2 | 1 | survives BH (at least one claim) |
| S07 | pileup | 3 | 3 | 3 | survives BH (at least one claim) |
| S07c | pileup | 0 | 0 | 0 | NO PARSED DELTA-CI ARTIFACT (cannot be FDR-assessed) |
| S07f | pileup | 0 | 0 | 0 | NO PARSED DELTA-CI ARTIFACT (cannot be FDR-assessed) |
| S10d | pileup | 2 | 2 | 2 | survives BH (at least one claim) |
| S11a | pileup | 1 | 1 | 1 | survives BH (at least one claim) |
| S11c | pileup | 1 | 1 | 1 | survives BH (at least one claim) |
| S16 | pedestal | 1 | 1 | 1 | survives BH (at least one claim) |
| P04 | amplitude-charge | 0 | 0 | 0 | NO PARSED DELTA-CI ARTIFACT (cannot be FDR-assessed) |
| P04c | amplitude-charge | 0 | 0 | 0 | NO PARSED DELTA-CI ARTIFACT (cannot be FDR-assessed) |
| P04d | amplitude-charge | 0 | 0 | 0 | NO PARSED DELTA-CI ARTIFACT (cannot be FDR-assessed) |
| P04e | amplitude-charge | 0 | 0 | 0 | NO PARSED DELTA-CI ARTIFACT (cannot be FDR-assessed) |
| P05b | pileup | 2 | 1 | 1 | survives BH (at least one claim) |
| P07 | amplitude-charge | 0 | 0 | 0 | NO PARSED DELTA-CI ARTIFACT (cannot be FDR-assessed) |

**Headline:** of 17 scoreboard bold wins, **10 survive BH** (at least one delta-CI claim), **0 fail BH**, and **7 have no machine-readable delta CI at all** (win asserted in prose/derived numbers only).

A BH-surviving claim is *necessary, not sufficient*: it does not repair dependent-residual iid bootstraps, leakage, or unfair baselines. Studies whose wins fail BH here (or have no parsable delta CI) must not be cited as wins pending confirmation on the reserved partition (`docs/CONFIRMATION_PARTITION.md`).

Worked cautionary example: **S03k** (withdrawn from the bold wins on 2026-07-03) has delta-CI claims that *survive* BH here (e.g. delta = -0.44 ns, CI [-0.84, -0.24] vs the analytic comparator), yet its gain was falsified by the S03p/S03r feature-leakage null grids — multiplicity control cannot detect leakage.

## Reproduce

```bash
/home/billy/anaconda3/envs/nnbar_env/bin/python scripts/stats01_program_fdr.py
```

Artifacts: `claims.csv` (one row per delta-CI claim, with family, z, p, BH-adjusted p, pass flag), `artifacts_without_claims.txt`.
