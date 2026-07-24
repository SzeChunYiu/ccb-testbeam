# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-24T192915Z`
- **Task:** `AUD-AMP-011`
- **Unit:** exact-content validation for hash-bound amplitude-evidence line fragments
- **Initial remote `main`:** `e215a4cd44ca6ed2eff3ec45921fcc72faa1e115`
- **Remote `main` before final handoff update:** `33aff10959a2e491942624883f7d0862d3547b27`
- **Destination:** direct sequential commits to `main`
- **Acceptance:** focused implementation, tests, and evidence are `VALIDATED`; real A-002 physics use remains `BLOCKED`

## Start-of-run and concurrency review

Authenticated GitHub reads inspected current `main`, recent commits, PR #868, the amplitude-convention auditor, the shared evidence-map validator, focused tests, validation records, and the mandatory `chatgpt_todo/` files. `AUD-REPO-001` remained owned by another active session and was not duplicated.

Concurrent WIKI and claim-ledger work advanced non-overlapping files and was preserved. Every write used current blob SHAs and direct contents-API commits to `main`; no force push, history rewrite, task branch, PR transport, or unrelated deletion was used. PR #868 remains closed, unmerged, and non-mergeable and was not modified.

A direct clone remained unavailable because this runtime could not resolve `github.com`. Exact source and test bytes were reconstructed locally from authenticated repository reads for execution.

## Confirmed defect

`tools/audit/validate_amplitude_evidence_map.py` v1.3.0 required canonical `#L<start>` or `#L<start>-L<end>` syntax, verified the complete supporting-file SHA-256, and required the selected line numbers to exist. It nevertheless accepted a selected range containing only spaces or tabs.

That allowed a byte-verified file plus a semantically empty citation to set `evidence_reference_fragment_verified=true`, after which the amplitude auditor could authorize an `ABSOLUTE` or `NET` convention. The validator also retained no byte count or SHA-256 for the exact selected fragment.

The exact v1.3.0 source was run against the new regression:

```text
2 failed, 6 passed in 0.10s
```

The failures demonstrated whitespace-only acceptance and absent exact-fragment provenance.

## Correction delivered

`tools/audit/validate_amplitude_evidence_map.py` is now version `1.4.0`. For line-range references it:

1. reads the supporting artifact bytes;
2. selects the exact requested line bytes with line endings retained;
3. counts selected nonblank lines;
4. rejects the fragment when that count is zero;
5. records selected byte count, nonblank-line count, and SHA-256;
6. sets `evidence_reference_fragment_verified=true` only after all checks pass.

Whole-file references remain supported and unchanged.

Policy: `EVIDENCE_LINE_FRAGMENT_MUST_CONTAIN_NONWHITESPACE_CONTENT`.

## Regression and quantitative validation

The updated fragment regression verifies exact line bounds, complete-file line count, exact selected bytes, digest, and whitespace-only rejection. The accepted example is 29 bytes, contains two nonblank lines, and has SHA-256 `2574a91c9368c20f6ae926794a5a37285b264197d248084c3b63306f8cadfa5a`.

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
- test: 3,292 bytes; SHA-256 `d2c78c6fc4044ae84b5828efa590ee92184e6a84b4690c85b1de73a32ffff699`.

## Evidence and files

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

- `8df26b33253b7364a8caf9afa6dab35148260f12` — implementation
- `7abe8871c6fa5f782d2bbbf009ab0aa0d69ee716` — regression tests
- `20f65542e203ab4161b4e0ffe8834ac8baaa7932` — validation JSON
- `a9fe61ddd66c8e5666d9e4fcf98e13939d8ccd2e` — audit report
- `29369505632cf707be7cd0d9d1fdcb16c05aa3df` — visual evidence
- `ca69c2f8e9cc705777000d09a8e3e4e76bb497d3` — active-task completion
- `03a4ad101f961650e4a53cc3819e344903fe335a` — immutable archive
- `ae205ce9d911bb083384ef7ea4eaef6ff90672c1` — first coordination workflow attempt
- `ca12b41d9ef27a74ed1f353b5c171a8a6cf12525` — coordination retry attempt
- `cb5d966c901a3aa41e8d01637725083992eec925` — initial handoff
- `1689a1b9a93eaa98bb874a883daba6243c941429` — remove unused workflow
- `33aff10959a2e491942624883f7d0862d3547b27` — remove unused retry

The contents API returned successful direct-main commit SHAs rather than conventional textual `git push` stdout. Post-write recent-history reads confirmed these commits on remote `main` while concurrent work was preserved.

## Coordination limitation

`ACTIVE_TASK.md`, the immutable archive, validation artifacts, and this handoff contain the complete session. `SESSION_LOG.md` and `BACKLOG.md` were not replaced: this connector exposes complete-file replacement rather than an append/line-patch operation, and the available current responses were ranged or truncated. Replacing long shared files from reconstructed partial text could erase unrelated provenance. Two one-time workflow attempts did not produce a remote coordination commit and were removed rather than left as repository debris.

Therefore the focused gate is delivered and reproducible, but aggregate `SESSION_LOG.md` and `BACKLOG.md` synchronization remains explicitly incomplete. No claim is made that those two files contain this run.

## Scientific boundary and next action

This work validates only software and provenance behavior. It does not determine whether the real A-002 `amplitude_adc` field is absolute or net, establish pulse polarity, validate a pedestal distribution, repair event cardinality, regenerate a stopping profile or DeltaE-E figure, or establish calibration or detector performance.

Real-data progress remains blocked under `AUD-AMP-009`, `AUD-DELTAE-001`, and `AUD-DELTAE-002` until exact A-002 table bytes and exact schema/producer/pedestal/polarity evidence are hash-bound and accepted. Full repository pytest, ruff, ROOT processing, real-data regeneration, and broad GitHub Actions CI were not run; no such success is claimed.
