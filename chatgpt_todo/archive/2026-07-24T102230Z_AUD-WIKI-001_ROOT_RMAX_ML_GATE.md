# AUD-WIKI-001 — root Rmax and ML claim gate

## Session identity

- UTC stamp: `2026-07-24T102230Z`
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote `main`: `74966884f40e6dbc8ac6243d4983eaa7dfb395ae`
- Owner: scheduled scientific-review session
- Destination: direct sequential commits to `main`
- Acceptance: validator, tests, and evidence `VALIDATED`; root-WIKI remediation `PARTIAL`

## Start-of-run review

Authenticated GitHub reads inspected repository permissions, recent main history,
PR #868, current status checks, the mandatory `chatgpt_todo/` coordination
files, `WIKI.md`, `docs/claim_ledger.csv`, the previous executive-summary
handoff, the current WIKI validator/tests, and the P04p/P07e/Rmax blockers.

PR #868 was closed, unmerged, and non-mergeable and was not modified. No status
checks were attached to the initial main head. A direct clone was attempted but
failed because the runtime could not resolve `github.com`; repository reads and
writes used the authenticated GitHub connector.

## Confirmed defect

`validate_wiki_claim_front_door.py` v1.1.0 bound only `CL-007` and `CL-011` and
used `csv.DictReader` without requiring canonical 43-column width for bound
rows. It therefore had no gate for root-WIKI Rmax, duplicate-readout, or
saturation-recovery statements.

An explicit negative control restricted v1.2 to the former bindings and disabled
the new phrase/caveat checks. A stale source-faithful fixture then returned
`VALIDATED`, demonstrating the former coverage gap.

The exact current ledger has 43 columns for `CL-007`, `CL-010`, `CL-011`,
`CL-012`, `CL-015`, and `CL-016`. The exact claim-bearing WIKI excerpt conflicts
with them:

- `CL-010` is `BLOCKED` with a blank canonical value, but the WIKI publishes
  `3.044–3.05 MHz` as `VALIDATED` in two tables and repeats `mu_max = 0.38`;
- `CL-012` is `SUPERSEDED` with a blank accepted value, but the WIKI calls
  approximately 3.05 MHz the new canonical value;
- `CL-015` is `GATED`, but duplicate readout remains labelled an ML-win or
  confirmed-win domain;
- `CL-016` is `GATED`, external ML duplicate closure is worse than raw, and
  producer bytes are unbound, but saturation recovery remains labelled an
  ML-win or promising domain.

The current excerpt returned status 1, `FLAWED`, with 21 findings:

- three `STATUS_LEDGER_MISMATCH`;
- three `VALUE_PRESENT_WHEN_LEDGER_WITHHOLDS`;
- three `UNSUPPORTED_ML_WIN_CLAIM`;
- two `MISSING_WIKI_CLAIM_ROW`;
- two `MISSING_WIKI_STATUS`;
- two `WITHHELD_RMAX_VALUE_PUBLISHED`;
- two `MISSING_REQUIRED_PUBLIC_CAVEAT`;
- one each of truth-type mismatch, unresolved Rmax threshold, unresolved Rmax
  derivation, and unsupported combined ML-win wording.

## Correction delivered

Upgraded `tools/audit/validate_wiki_claim_front_door.py` to v1.2.0 with policy:

`WIKI_FRONT_DOOR_MUST_MATCH_EXACT_WIDTH_CANONICAL_CLAIMS`

The validator now:

- requires exactly 43 unique ledger columns;
- fails closed if any required claim is absent or not exactly 43 columns;
- binds `CL-007`, `CL-010`, `CL-011`, `CL-012`, `CL-015`, and `CL-016`;
- checks status, truth type, and withheld-value handling;
- rejects stale numerical Rmax and its unresolved derivation;
- rejects combined/domain ML-win wording;
- requires public caveats withholding Rmax and production P04p/P07e use.

Added or updated:

- `tests/test_validate_wiki_claim_front_door.py`;
- `docs/validation/wiki_rmax_ml_claim_gate_audit.md`;
- `docs/validation/wiki_rmax_ml_claim_gate_validation.json`;
- `docs/validation/wiki_rmax_ml_claim_gate.svg`;
- `chatgpt_todo/ACTIVE_TASK.md`;
- this immutable archive record.

## Validation

```text
python -m py_compile \
  tools/audit/validate_wiki_claim_front_door.py \
  tests/test_validate_wiki_claim_front_door.py

python -m pytest tests/test_validate_wiki_claim_front_door.py -q

10 passed in 0.04s
```

Additional checks:

- exact current ledger bytes matched Git blob
  `853d955f449268ec614ac61f33f243d30cf473e0`;
- ledger size `12077` bytes;
- ledger SHA-256
  `c0e283e6d43a1013a9565f2697c4f99f7b47d639245b9926a8ddc83786602e19`;
- validator Git blob `6ae2df1018abde8d93a7bb04d787786ade95622a`;
- test Git blob `ecaa4acd6d46e56861c83a32b071678cf4f3960f`;
- validation JSON parsed;
- SVG parsed as XML;
- maximum changed Python line lengths: 91 and 98 characters.

## Direct-main commits before archive

1. `b088178443f68691dec285bcf4a098dc1553fd71` — `fix(audit): gate root WIKI Rmax and ML claims`
2. `c9ad71b03765f32a11d7bf82a847c780503150cc` — `test(audit): cover exact-width WIKI claim gate`
3. `f8ae60d70e8152e924e052ddc69baebeafda85c2` — `docs(validation): record root WIKI claim-gate audit`
4. `7aecb8dbd631b6eb27aaca6d364cf7dbc05ec6d7` — `docs(validation): add root WIKI claim-gate record`
5. `a13cc69c69d0119ffc93993b87d9dfe116a95eda` — `docs(validation): visualize root WIKI claim gate`
6. `a222221cac062e0f07d35fb7b3618ac59af949e1` — `docs(audit): track root WIKI claim gate`

Each connector write returned a successful direct-main commit. No task branch,
force-push, history rewrite, or pull request was used.

## Scientific and validation boundary

This unit does not determine an accepted Rmax, choose a P04p production model,
authorize a P07e saturation correction, or generate detector data, simulation,
fits, uncertainty intervals, calibration, or detector-performance results.

The executable current-state audit used an exact claim-bearing WIKI excerpt,
not a full local WIKI byte snapshot, because the checkout/download path was
unavailable. Full repository pytest, ruff, complete broken-link checking, ROOT
processing, model reruns, and GitHub Actions were not run.

## Next action

Rewrite the complete current `WIKI.md` from the latest `origin/main`, withhold
Rmax pending S-STAT-003, separate the P04p and P07e gated statements, run v1.2.0
against the exact complete WIKI and ledger, run focused tests and broken-link
checks, and require `VALIDATED` before closing `AUD-WIKI-001`.
