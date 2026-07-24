# Executive-summary claim consistency audit

## Scope

This audit reviews the public academic front door at
`docs/academic_chapters/01_executive_summary.md` against the exact-width
canonical claim rows currently available in `docs/claim_ledger.csv`.

Repository blobs inspected before the change:

- executive summary: `eb8c2f5d287ff227a15522754f48a0c75c1336ca`;
- claim ledger: `853d955f449268ec614ac61f33f243d30cf473e0`.

The evidence is repository documentation and source-backed ledger state. No new
beam-data, simulation, calibration, or detector-performance result is created.

## Confirmed inconsistencies

The pre-change executive summary contradicted canonical or already-audited
claim state in several high-visibility statements:

1. Rmax was shown as `3.044–3.05 MHz` and `VALIDATED`, while exact-width
   `CL-010` withholds the value as `BLOCKED`; `CL-012` retains 3.044 MHz only
   as superseded correction history.
2. Effective live-time used truth type `data_only`, while exact-width `CL-011`
   records `data_mc_self_consistent`.
3. MV4 raw timing used status `PASS`, which is outside the canonical status
   vocabulary; exact-width `CL-007` records `VALIDATED`.
4. The chapter called duplicate-readout and saturation recovery “ML wins
   (confirmed)”. Exact-width `CL-015` has no robust production winner because
   the P04p coverage interval crosses the eligibility gate. Exact-width
   `CL-016` withholds P07e because held-out external duplicate closure is worse
   than raw: ML res68 `0.176358 [0.173043,0.180602]` versus raw `0.120794
   [0.117004,0.125364]`.
5. The C12-like fraction was presented as an established empirical result,
   despite being truth-labelled MC only.

## Correction

The chapter now:

- withholds Rmax pending S-STAT-003;
- uses canonical status vocabulary and the corrected tau truth type;
- labels the C12-like fraction as truth-labelled MC only;
- replaces the combined “ML wins” row with separate P04p and P07e gated rows;
- states that no production duplicate-readout or saturation correction is
  authorized;
- carries the same boundaries into established results, open issues, and next
  studies.

## Fail-closed validator

`tools/audit/validate_executive_summary_claims.py` v1.0.0 requires the five
ledger rows used for authorization (`CL-007`, `CL-010`, `CL-011`, `CL-015`,
`CL-016`) to have exactly 43 fields. It then checks chapter row presence,
status, required value caveats, and truth-type language. It also rejects the
former unsupported Rmax, C12, and “ML wins (confirmed)” statements.

Policy:

```text
EXECUTIVE_SUMMARY_MUST_MATCH_EXACT_WIDTH_CANONICAL_CLAIMS
```

## Validation

Commands:

```text
PYTHONPATH=. python -m py_compile \
  tools/audit/validate_executive_summary_claims.py \
  tests/test_validate_executive_summary_claims.py

PYTHONPATH=. python -m pytest \
  tests/test_validate_executive_summary_claims.py -q

5 passed in 0.03s
```

The corrected chapter was also run through the validator against an exact
43-column extraction of the five current ledger rows. Result: `VALIDATED`,
zero issues. The extraction is validation support only; the canonical runtime
command uses `docs/claim_ledger.csv` directly.

Additional checks:

- corrected chapter SHA-256:
  `af76aa164cc5a7f994a135acaf4f15961d30e53d4d27346ec21443444b2f15d1`;
- focused ledger extraction: 43 columns for header and all five rows;
- validation JSON parsed;
- SVG parsed as XML;
- changed Python lines are at most 96 characters.

## Scientific boundary

This is a documentation-governance correction. It does not resolve the Rmax
physics criterion, establish a P04p winner, authorize P07e saturation recovery,
identify C12 in real data, or complete the remaining malformed ledger rows.
The root WIKI still requires the same Rmax and P04p/P07e wording audit under
`AUD-WIKI-001`.
