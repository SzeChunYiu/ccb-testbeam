# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-24T192915Z`
- **Task:** `AUD-AMP-011`
- **Unit:** exact-content validation for hash-bound amplitude-evidence line fragments
- **Initial remote `main`:** `e215a4cd44ca6ed2eff3ec45921fcc72faa1e115`
- **Remote `main` observed before this handoff write:** `3fdc70cec7ef56c067cfe67bffb98b8b6437f436`
- **Destination:** direct sequential commits to `main`
- **Acceptance:** focused implementation, regression, and evidence are `VALIDATED`; real A-002 physics use remains `BLOCKED`

## Start-of-run and concurrency review

Authenticated GitHub reads inspected current `main`, recent commits, PR #868, the amplitude-convention auditor, the shared evidence-map validator, focused tests, validation records, and the mandatory `chatgpt_todo/` coordination files. `AUD-REPO-001` remained owned by another active session and was not duplicated.

The run preserved concurrent WIKI and claim-ledger work. Every repository write used the current blob SHA and direct contents-API commits to `main`; no force push, history rewrite, task branch, draft PR, or unrelated deletion was used. PR #868 remains closed, unmerged, and non-mergeable and was not modified.

A direct clone remained unavailable because this runtime could not resolve `github.com`. Exact source/test files were reconstructed locally from authenticated repository bytes for execution.

## Confirmed defect

`tools/audit/validate_amplitude_evidence_map.py` v1.3.0 required canonical `#L<start>` or `#L<start>-L<end>` syntax, verified the complete supporting-file SHA-256, and required the selected line numbers to exist. It nevertheless accepted a selected range containing only spaces or tabs.

That allowed a byte-verified file plus a semantically empty line citation to set `evidence_reference_fragment_verified=true`, after which the amplitude convention auditor could authorize `ABSOLUTE` or `NET` physics use. The validator also retained no SHA-256 or byte count for the exact selected fragment, so the line-level supporting bytes were not independently identifiable from the whole-file digest.

The exact v1.3.0 source was executed against the new regression and returned:

```text
2 failed, 6 passed in 0.10s
```

The failures demonstrated both former behaviors: whitespace-only line acceptance and missing exact-fragment provenance.

## Correction delivered

`tools/audit/validate_amplitude_evidence_map.py` is now version `1.4.0`.

For line-range references it now:

1. reads the supporting artifact bytes;
2. selects the exact requested line bytes with original line endings retained;
3. counts selected nonblank lines;
4. rejects the fragment when that count is zero;
5. records the selected byte count;
6. records the selected nonblank-line count;
7. records SHA-256 of the exact selected bytes;
8. sets `evidence_reference_fragment_verified=true` only after these checks pass.

Whole-file evidence references remain supported and unchanged. The registered policy is:

`EVIDENCE_LINE_FRAGMENT_MUST_CONTAIN_NONWHITESPACE_CONTENT`

## Regression and quantitative validation

Updated `tests/test_amplitude_evidence_reference_fragments.py` now verifies:

- an accepted `#L2-L3` selection retains exact line bounds and complete-file line count;
- the exact selected fragment is 29 bytes;
- it contains two nonblank lines;
- its SHA-256 is `2574a91c9368c20f6ae926794a5a37285b264197d248084c3b63306f8cadfa5a`;
- a whitespace-only `#L2` selection fails closed;
- malformed, semantic-only, zero, reversed, and out-of-range fragments remain rejected.

Executed against exact local reconstructions:

```text
python -m py_compile \
  tools/audit/validate_amplitude_evidence_map.py \
  tests/test_validate_amplitude_evidence_map.py \
  tests/test_amplitude_evidence_reference_fragments.py

python -m pytest \
  tests/test_validate_amplitude_evidence_map.py \
  tests/test_amplitude_evidence_reference_fragments.py -q

23 passed in 0.05s
```

Changed Python lines are no longer than 100 characters.

Exact validated local files:

- validator: 10,102 bytes; SHA-256 `a1f547c8ee7d52c1a71dbaa16c031f2a06ea68d63e9269f51c39ba11a37dd095`;
- fragment regression: 3,292 bytes; SHA-256 `d2c78c6fc4044ae84b5828efa590ee92184e6a84b4690c85b1de73a32ffff699`.

## Version-controlled evidence

Added:

- `docs/validation/amplitude_evidence_fragment_content_audit.md`;
- `docs/validation/amplitude_evidence_fragment_content_validation.json`;
- `docs/validation/amplitude_evidence_fragment_content.svg`;
- `chatgpt_todo/archive/2026-07-24T192915Z_AUD-AMP-011_NONBLANK_FRAGMENT_CONTENT.md`.

Updated:

- `tools/audit/validate_amplitude_evidence_map.py`;
- `tests/test_amplitude_evidence_reference_fragments.py`;
- `chatgpt_todo/ACTIVE_TASK.md`;
- this handoff.

The SVG is explicitly labelled synthetic software/provenance evidence, not detector data.

## Direct-main commit sequence

- `8df26b33253b7364a8caf9afa6dab35148260f12` — `fix(audit): reject blank amplitude evidence fragments`
- `7abe8871c6fa5f782d2bbbf009ab0aa0d69ee716` — `test(audit): cover blank amplitude evidence fragments`
- `20f65542e203ab4161b4e0ffe8834ac8baaa7932` — `docs(validation): record amplitude fragment content gate`
- `a9fe61ddd66c8e5666d9e4fcf98e13939d8ccd2e` — `docs(validation): audit amplitude fragment content verification`
- `29369505632cf707be7cd0d9d1fdcb16c05aa3df` — `docs(validation): visualize amplitude fragment content gate`
- `ca69c2f8e9cc705777000d09a8e3e4e76bb497d3` — `docs(audit): complete blank fragment content gate`
- `03a4ad101f961650e4a53cc3819e344903fe335a` — `docs(audit): archive nonblank fragment validation`
- `ae205ce9d911bb083384ef7ea4eaef6ff90672c1` — `ci(audit): finalize amplitude fragment coordination`
- `ca12b41d9ef27a74ed1f353b5c171a8a6cf12525` — `ci(audit): retry amplitude fragment coordination`

The authenticated contents API returned successful commit SHAs instead of conventional textual `git push` output. Recent-history reads confirmed the implementation, tests, evidence, active-task update, archive, and coordination-workflow commits on remote `main` while concurrent non-overlapping work was preserved.

## Coordination state

`AUD-AMP-011` is `COMPLETE` for the focused synthetic gate. `AUD-AMP-010` line syntax and existence validation is also complete at the tooling level. A one-time exact-checkout coordination workflow was committed to append the full session record safely and synchronize stale aggregate backlog rows without replacing partially retrieved shared-file bytes; it deletes itself after a successful append/push.

The final coordination commit and deletion must be confirmed in recent remote history before claiming those aggregate files synchronized. The immutable archive and this handoff already contain the complete reproducible session without hidden chat context.

## Scientific boundary and unresolved blockers

This work validates only software and provenance behavior. It does not determine whether the real A-002 `amplitude_adc` field is absolute or net, establish pulse polarity, validate a pedestal distribution, repair physical-event cardinality, regenerate a stopping profile or DeltaE-E figure, or establish a calibration or detector-performance result.

Real-data progress remains blocked under `AUD-AMP-009`, `AUD-DELTAE-001`, and `AUD-DELTAE-002` until exact A-002 table bytes and exact supporting schema/producer/pedestal/polarity evidence are hash-bound and accepted. Full repository pytest, ruff, ROOT processing, real-data regeneration, and broad GitHub Actions CI were not run; no such success is claimed.
