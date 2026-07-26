# Latest Handoff

## Session

- **Task:** `AUD-DELTAE-005`
- **Stamp:** `2026-07-26T030223Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `f1a615d5b591b63c91b03124d243daf8372b61cd`
- **Validated delivery/handoff commit:** `47a1c69656eb4045f835492b5e0c4db6752d4f3a`
- **Remote-main confirmation:** post-write history confirmed the delivery commit and its complete
  focused ancestry consecutively on remote `main`.
- **Destination:** direct commits to `main`; no task branch, force-push, history rewrite, or PR.
- **Focused acceptance:** audit implementation, tests, JSON, SVG, report, and archive `VALIDATED`.
- **Production reader state:** `FLAWED / PARTIAL`; the canonical reader was not modified in this unit.

## Start-of-run review

Fetched current `main`, recent history, combined status, open PR #933, closed PR #868, the
mandatory `chatgpt_todo/` records, DeltaE scripts/tests/contracts, and downstream consumers. PR
#933 remained draft, open, unmergeable, and unmerged. PR #868 remained closed, unmerged,
non-mergeable, and untouched. No status checks were attached to the initial main commit.

## Confirmed defect

The canonical source blob `fe5dd5e4673f32fa5a4b94776531f2b392e12414` declares the event key
`(source_file_id, run_id, event_id)` but its CSV branch calls default `pandas.read_csv(path)` with
no text dtype for the key and no single-read strict-UTF-8 snapshot.

A deterministic two-row control used exact source identifiers `001` and `1` with equal run/event
values. Under pandas 2.2.3 default inference:

- parsed identifiers became `1` and `1`;
- two exact composite keys collapsed to one parsed key;
- one false data/MC inner-join match was created.

With all three key columns parsed as text, two exact keys remained and the false-match count was
zero. This can change event cardinality or cross-contaminate rows before stopping or DeltaE-E
statistics are calculated.

Policy:

`DELTAE_CSV_COMPOSITE_KEYS_MUST_BE_READ_AS_LOSSLESS_TEXT`

## Downstream review

The strict bundle test introduced by `AUD-DELTAE-004` applies an explicit text contract to
provenance columns. `scripts/studies/clusterA_data_side.py` reads one strict-UTF-8 byte snapshot
with `csv.DictReader` and preserves `source_file_id` as text. The vulnerable boundary identified
here is the generic canonical `scripts/single_stave/deltaE_E.py` CSV input path.

## Better-method comparison

- Post-read string casting was rejected because it cannot restore leading zeros or undo a false
  match already created by inference.
- Protecting only `source_file_id` was rejected as an incomplete composite-key contract.
- Parquet-only input would strengthen typing but remove the supported CSV workflow.
- Required remediation is one strict-UTF-8 byte snapshot plus text dtypes for all three key columns;
  numeric physics fields remain independently coercible and validated.

## Files added

- `tools/audit/audit_deltae_csv_key_identity.py`
- `tests/test_audit_deltae_csv_key_identity.py`
- `tools/audit/render_deltae_csv_key_identity_evidence.py`
- `docs/validation/deltae_csv_key_identity_validation.json`
- `docs/validation/deltae_csv_key_identity.svg`
- `docs/validation/deltae_csv_key_identity_audit.md`
- `chatgpt_todo/archive/2026-07-26T030223Z_AUD-DELTAE-005_CSV_KEY_IDENTITY.md`

Updated `chatgpt_todo/ACTIVE_TASK.md` and this handoff.

## Validation

Executed in the available local environment:

```text
python -m py_compile \
  tools/audit/audit_deltae_csv_key_identity.py \
  tests/test_audit_deltae_csv_key_identity.py \
  tools/audit/render_deltae_csv_key_identity_evidence.py

pytest -q tests/test_audit_deltae_csv_key_identity.py
6 passed in 0.09s
```

Environment:

- Python `3.13.5`
- pandas `2.2.3`

The current-like executable contract returned `FLAWED` with five findings. A corrected fixture
returned `VALIDATED` with zero findings. Invalid UTF-8, missing reader definitions, and destructive
output aliasing failed closed. Atomic JSON publication passed. The JSON parsed, the SVG parsed as
XML, and changed Python lines are at most 100 characters.

The execution container could not clone GitHub. The exact current source was inspected through the
GitHub connector and bound by its Git blob; the executable control used the exact relevant reader
behavior excerpt. Full-source execution is not claimed.

## Findings

- `CSV_KEY_DTYPE_MISSING`
- `CSV_NOT_SINGLE_READ_STRICT_UTF8`
- `CSV_KEY_POLICY_MISSING`
- `DISTINCT_COMPOSITE_KEYS_COLLAPSE`
- `FALSE_CROSS_FILE_MATCH`

## Direct-main commits

- `7c9b9a063cf5115e4dee9c6c9c8797b6a7577ffc` — task claim
- `0e05c2cfeda5d46c35f0a31d7b01fe4f769ca51a` — fail-closed auditor
- `22c312c58a3b5d6339113dc31b5774f4d76102a7` — focused regressions
- `171e3506f2b274548d63be299cab7cec9bd83d5c` — evidence renderer
- `2173af69f7d1a564695c5c696da8e5accbfc3907` — validation JSON
- `29a2229361b174ba2a34da92ee668837b448de75` — visual evidence
- `0b542e6c8844f3aaf1e3469c808620bf3a3d0d38` — audit report
- `8f706d05b97e2e032bef7813cb34b48dd4bcdea7` — immutable archive
- `f3ecace79fbb1c8f68c380af604ce59f218aacd5` — active-task completion
- `47a1c69656eb4045f835492b5e0c4db6752d4f3a` — delivery handoff

GitHub contents writes returned commit SHAs rather than terminal `git push` stdout. Post-write
history confirmed the delivery handoff and all focused ancestors on remote `main`.

## Required next action

Modify `deltaE_E.py` to read CSV bytes once, decode strict UTF-8, parse all composite-key columns as
text, record input byte/hash provenance from that same snapshot, add direct reader/CLI integration
regressions, and require the exact current-source audit to return zero findings before a CSV-backed
production rerun.

## Scientific boundary

No exact A-002 pulse table was processed. No amplitude convention, pulse polarity, stopping
fraction, DeltaE-E PID result, uncertainty budget, calibration, or detector performance is
established. `AUD-DELTAE-001`, `AUD-DELTAE-002`, and `BLK-AMP-001` remain open.

Repository-wide pytest/ruff, ROOT processing, full link inventory, and GitHub Actions were not run.
No broad CI success is claimed.

## Coordination limitation

`SESSION_LOG.md` was not appended. The connector only supports whole-file replacement while the
complete append-only file is exposed through paged or truncated responses. Replacing a partial
reconstruction could erase unrelated provenance. The immutable archive and this handoff preserve
the append-equivalent session, and the unmet mandatory append is reported explicitly.
