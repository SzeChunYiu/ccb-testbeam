# Immutable session record — executive-summary claim consistency

## Identity

- UTC stamp: `2026-07-24T090650Z`
- Primary task: `AUD-WIKI-001`
- Unit: academic executive-summary alignment with exact-width canonical claims
- Repository: `SzeChunYiu/ccb-testbeam`
- First observed remote `main`: `0f0e79031777faa203c086860d6a163d10c838ae`
- Concurrent P07e completion incorporated before writes: `5e7f9c96ac604eef63be356da0131fc492b5173d`
- Destination: direct sequential commits to `main`; no task branch, PR, force-push, or history rewrite

## Start-of-run review

Authenticated GitHub reads inspected repository metadata and permissions, recent main history, current commit status, PR #868, mandatory `chatgpt_todo/` state, `WIKI.md`, the academic executive summary, the claim ledger, the current WIKI validator/tests, and the newly completed P04p/P07e source-backed claim records. A direct clone was attempted and failed because the runtime could not resolve `github.com`; exact repository facts came from authenticated GitHub file/blob/commit reads.

PR #868 was confirmed closed, unmerged, and non-mergeable. It was not modified. No status checks were attached to the reviewed current-main head.

## Confirmed documentation defects

The pre-change academic executive summary blob `eb8c2f5d287ff227a15522754f48a0c75c1336ca` contradicted canonical or already-audited state:

1. Rmax was presented as `3.044–3.05 MHz` and `VALIDATED`, while exact-width `CL-010` is `BLOCKED` and withholds the value; `CL-012` retains 3.044 MHz only as superseded history.
2. Effective live-time used truth type `data_only`; exact-width `CL-011` records `data_mc_self_consistent`.
3. MV4 raw timing used `PASS`, outside the canonical vocabulary; exact-width `CL-007` records `VALIDATED`.
4. Duplicate readout and saturation recovery were combined as `ML wins (confirmed)`. Exact-width `CL-015` has no canonical winner because the P04p coverage interval crosses its eligibility gate. Exact-width `CL-016` withholds P07e because held-out external duplicate closure is worse than raw.
5. The C12-like 0.32% fraction was presented as an established empirical result rather than a truth-labelled MC-only result.

## Quantitative claim state preserved

- P04p reported GBT accepted coverage: `0.5016432417313474`.
- P04p run-bootstrap 95% coverage interval: `[0.4781032287979763,0.5382552094265317]`.
- P07e external ML charge res68: `0.1763577793605039` with `[0.17304334869529975,0.18060166173702746]`.
- P07e external raw charge res68: `0.12079374117700271` with `[0.11700387021774719,0.12536373643016782]`.
- P07e ML-minus-raw degradation: `+0.05556403818350119`.

No new calculation is represented as detector data. These values were already recorded by the exact source-backed P04p/P07e audits.

## Correction delivered

Updated `docs/academic_chapters/01_executive_summary.md` to:

- withhold Rmax pending S-STAT-003;
- use canonical status vocabulary;
- restore the effective-live-time truth type;
- label the C12 fraction as truth-labelled MC only;
- split the former combined ML-win row into separate P04p and P07e gated claims;
- state that no production duplicate-readout or saturation correction is authorized;
- propagate the same boundaries into historical corrections, excluded claims, established results, open issues, and next studies;
- fix chapter-relative links to the claim ledger, figure registry, and checklist.

Added:

- `tools/audit/validate_executive_summary_claims.py` v1.0.0;
- `tests/test_validate_executive_summary_claims.py`;
- `docs/validation/executive_summary_claim_consistency_audit.md`;
- `docs/validation/executive_summary_claims_validation.json`;
- `docs/validation/executive_summary_claim_consistency.svg`.

Policy:

```text
EXECUTIVE_SUMMARY_MUST_MATCH_EXACT_WIDTH_CANONICAL_CLAIMS
```

The validator refuses to authorize the chapter unless `CL-007`, `CL-010`, `CL-011`, `CL-015`, and `CL-016` are all exactly 43 columns. It checks required rows, statuses, value caveats, truth-language, and former unsupported statements.

## Validation

Executed locally on the exact committed source/test/chapter reconstructions:

```text
PYTHONPATH=. python -m py_compile \
  tools/audit/validate_executive_summary_claims.py \
  tests/test_validate_executive_summary_claims.py

PYTHONPATH=. python -m pytest \
  tests/test_validate_executive_summary_claims.py -q

5 passed in 0.03s
```

Additional checks:

- stale pre-change-like fixture returned `FLAWED` with controlled status, missing-row, unsupported-statement, and C12 truth-scope findings;
- corrected fixture returned `VALIDATED` with zero issues;
- a required 42-column `CL-016` fixture failed closed;
- invalid UTF-8 returned controlled status 2;
- the corrected chapter validated with zero issues against an exact 43-column extraction of the five current ledger rows;
- corrected chapter SHA-256: `af76aa164cc5a7f994a135acaf4f15961d30e53d4d27346ec21443444b2f15d1`;
- validation JSON parsed;
- SVG parsed as XML;
- maximum changed Python line length: 96;
- committed chapter blob `c3205e4ffe5eacbdf24191aba7f0a130ab0bca88` matches locally validated bytes;
- committed validator blob `7cf0ca76f14c071192d28bd340024c929efa3277` matches locally validated bytes;
- committed test blob `3e2880209625db0292701d06ebf6a39837e5c5d0` matches locally validated bytes.

## Direct-main commits before coordination closeout

- `ba24773be4ff465ae57f2255dcb7ef4391d2ee91` — `fix(docs): align executive summary with canonical claims`
- `1530cfcff6ae82318cceea36a54caa0af0c82202` — `feat(audit): validate executive summary claim alignment`
- `7f7a2dabefa183d14c24d494ba2f3c32a870110a` — `test(audit): cover executive claim consistency`
- `a962ae9e1bc45b6ff750ee3840bde97843a3a1c0` — `docs(validation): record executive claim consistency audit`
- `c25c0783beac66270160cbc99ebd0b37f9f74e94` — `docs(validation): add executive claim validation record`
- `e01e5c96cf4aa633fc155b465ad851b866bc18a1` — `docs(validation): visualize executive claim correction`
- `130bffa265c2a025bd83bb1935631465318226de` — `docs(audit): track executive claim remediation`

All writes returned successful direct-main commit results.

## Unrun checks and scientific boundary

Not run or unavailable:

- full repository pytest;
- ruff;
- complete broken-link scan;
- raw ROOT processing;
- model training or bootstrap regeneration;
- Rmax physics derivation;
- cross-stave/new-run P04p/P07e validation;
- GitHub Actions for this commit sequence.

No raw data, simulation result, calibration constant, or detector-performance result was changed. This unit does not resolve S-STAT-003, establish a P04p production winner, authorize P07e saturation recovery, identify C12 in real data, or repair the remaining 19 malformed ledger rows.

## Remaining work

1. Apply the same Rmax and P04p/P07e corrections to root `WIKI.md` and extend its validator bindings.
2. Continue source-backed reconstruction of the 19 malformed ledger rows.
3. Resolve S-STAT-003 before publishing an Rmax value.
4. Resolve P04p/P07e uncertainty, provenance, and independent-transfer blockers before production use.

`SESSION_LOG.md` was not replaced because the connector exposes complete-file replacement and only truncated reads of the long append-only file were available. Reconstructing it manually would risk deleting prior provenance. This archive is the complete immutable session entry; no append is fabricated.
