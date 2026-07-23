# Latest Handoff

## Session

- **UTC:** 2026-07-23T09:06:39Z
- **Task:** AUD-CI-002 (COMPLETE; concurrent coordination reconciliation PARTIAL)
- **Initial remote main:** `345d82d1daccbe1d8eafcf525ab51fd19ab20832`
- **Validated amplitude CI fix on remote main:** `4f857f508160bbbe059d936866b426a45788c9bd`
- **Remote main after mandatory-ledger restoration, blocker update, and append-only reconciliation log and before this handoff write:** `5a032f77ed4fc6ae2271d240877dce4a6bc3bc5f`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Canonical destination:** `main`

## Start-of-run review

- Confirmed repository admin/push permission and default branch `main`.
- Inspected current main history, current-main commit status, PR #868, all open pull requests returned by repository search, PR #884 metadata and exact patch, Actions run `29993563323`, job `89161772967`, the affected auditor/tests, and required `chatgpt_todo/` records.
- PR #868 is closed and not merged. It was not reopened or merged.
- A direct clone was attempted and failed with `Could not resolve host: github.com`; authenticated GitHub connector reads/writes were used.

## Confirmed defects

### Stale warning assertion

Production code emits:

```text
AMPLITUDE_CONVENTION_WITHOUT_BASELINE_LEVEL
```

but `tests/test_amplitude_convention_audit.py` still asserted the superseded `ABSOLUTE_WITHOUT_BASELINE_LEVEL` name. This was a deterministic current-main test failure, not a scientific-data discrepancy.

### Invalid-baseline aggregate undercount

`n_invalid_baseline_data_tables` inspected evidence-gated `physics_acceptance`. A table without accepted evidence can still have incomplete pedestal values and the unconditional state:

```text
convention_acceptance = BASELINE_DATA_INVALID
```

The old aggregate therefore omitted a no-evidence heuristic ABSOLUTE table that the dedicated baseline-quality regression expected to count. The repaired expression counts non-NET convention rows with the unconditional invalid-baseline state. The NET exclusion preserves the convention-specific rule that hash-authorized NET input does not require optional pedestal diagnostics.

## Validated transport and merge

- **PR:** #884 — `fix(audit): repair red main CI — amplitude convention audit (P0)`
- **PR base:** `345d82d1daccbe1d8eafcf525ab51fd19ab20832`
- **PR head:** `9750d0fddc626a76f0c954fa09065db05ac83f32`
- **Changed files:** exactly two
  - `tools/audit/amplitude_convention_audit.py`
  - `tests/test_amplitude_convention_audit.py`
- **Patch size:** four additions, two deletions.
- **Validation:** MC Validation CI run `29993563323`, job `89161772967`, completed successfully.
- **Merge method:** squash.
- **GitHub merge output:** `merged=true`; `message="Pull Request successfully merged"`.
- **Resulting remote-main commit:** `4f857f508160bbbe059d936866b426a45788c9bd` — `fix(audit): repair red main CI (amplitude convention audit) (#884)`.
- Post-merge reads confirmed both reviewed changes in the `main` files, and a recent-commit query confirmed the merge commit at remote-main head before coordination writes.

## Concurrent-main reconciliation

Two unrelated pull requests merged while this run was writing coordination records:

- PR #886 merged as `98f74d1c9a79abbedfcc9d4e934deb9e40ee3e97` and intentionally deleted factory/fleet/ticket infrastructure **and the entire pre-existing `chatgpt_todo/` tree**.
- PR #888 merged as `35009240aa156a70c57d0f1b0ff38706ccf14a63`. Its head workflow `29994419166` succeeded, but this session did not independently review its 71-file scientific implementation or claim Geant4 runtime validation from that Python workflow.

The active scheduled scientific-review requirement still mandates `chatgpt_todo/`. The minimum scientific-review protocol and mandatory ledgers were recreated separately from the removed factory/fleet/ticket system:

- `b752bd42b88798969e89e24df1adc1d6f66cd8c8` — `docs(audit): restore required scientific review protocol`
- `2aa0675e2760e3dae4f87ef82e9804118cb1d674` — `docs(audit): restore claim evidence matrix`
- `e1cd9900dc772c1c8221db4db10823e55e38fada` — `docs(audit): restore study review ledger`
- `ce2d10549a0680f47c51667dc03dc1c846a05593` — `docs(audit): restore visualization matrix`

Older archive files removed by PR #886 were not blindly restored. They remain recoverable from Git history but require deliberate provenance review before returning to the current tree. This limitation is recorded as `BLK-COORD-001`.

## Coordination and provenance writes

Authenticated GitHub writes returned these direct-to-`main` commits in order around the concurrent merges:

- `f95b28c9ec764ebfe0a9c3983d69b5aa138a6ebb` — `docs(audit): record amplitude CI restoration task`
- `92cb21bfe54ad0fb165eac3d5265559dc2137a7e` — `docs(audit): close amplitude CI restoration backlog item`
- `a1b83fd8ea275b369830d36c2b39f84af3fb5166` — `docs(audit): index restored amplitude CI gate`
- `8d7e741eb4312af216dbf034b061b74fc7d8374c` — `docs(audit): map amplitude CI repair to audit outputs`
- `05b9f00430827e8c06220d3560014b86154ccd59` — `docs(audit): record resolved amplitude CI blocker`
- `79f333215272622c6a44a15e25c0ed9e6539702e` — `docs(audit): archive amplitude CI restoration`
- `21a0dd7d8c54cf4701cce1d1e113dd2aa9950f9f` — `docs(audit): append amplitude CI restoration session`
- `c3338eae46f3fc22e7498a10415e8e5e7b1a1e0a` — `docs(audit): hand off amplitude CI restoration`
- `b752bd42b88798969e89e24df1adc1d6f66cd8c8` — `docs(audit): restore required scientific review protocol`
- `2aa0675e2760e3dae4f87ef82e9804118cb1d674` — `docs(audit): restore claim evidence matrix`
- `e1cd9900dc772c1c8221db4db10823e55e38fada` — `docs(audit): restore study review ledger`
- `ce2d10549a0680f47c51667dc03dc1c846a05593` — `docs(audit): restore visualization matrix`
- `e5af76b8f56c2fb8fc59585ac908764b9847ec0c` — `docs(audit): record concurrent coordination deletion`
- `5a032f77ed4fc6ae2271d240877dce4a6bc3bc5f` — `docs(audit): append concurrent main reconciliation`

No force push, history rewrite, or unrelated-file deletion was used by this session.

## Repository-local records present or updated

- `chatgpt_todo/README.md`
- `chatgpt_todo/MASTER_INDEX.md`
- `chatgpt_todo/BACKLOG.md`
- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/HANDOFF.md`
- `chatgpt_todo/BLOCKERS.md`
- `chatgpt_todo/SESSION_LOG.md`
- `chatgpt_todo/STUDY_REVIEW_LEDGER.md`
- `chatgpt_todo/CLAIM_EVIDENCE_MATRIX.md`
- `chatgpt_todo/CODE_RESULT_MAP.md`
- `chatgpt_todo/VISUALIZATION_MATRIX.md`

Current immutable session record:

- `chatgpt_todo/archive/2026-07-23T090639Z_AUD-CI-002_AMPLITUDE_CI_RESTORATION.md`

## Validation and scientific boundary

- The successful workflow validates the Python unit-test gate exercised by MC Validation CI on the reviewed PR merge ref.
- The two-file patch was independently inspected and the resulting main files were re-read after merge.
- No post-merge push workflow or status check is claimed; no status context was attached to the merge commit when checked immediately after merge.
- No raw data, pulse table, ROOT file, Geant4 run, plot, table, simulation output, calibration, stopping distribution, or detector-performance result changed.
- This CI repair does not authorize any real `amplitude_adc` convention, pedestal subtraction, or pulse polarity.
- `BLK-AMP-001` remains open and historical A-002 outputs remain quarantined.
- `BLK-COORD-001` remains PARTIAL because the prior archive tree was not fully restored after the concurrent deletion.

## Acceptance status

- Stale warning regression: COMPLETE.
- Invalid-baseline aggregate accounting for non-NET convention rows: COMPLETE.
- PR #884 CI: SUCCESS.
- Validated fix present on remote `main`: CONFIRMED at `4f857f508160bbbe059d936866b426a45788c9bd`.
- Mandatory current scientific-review coordination files: RESTORED.
- Historical archive-tree reconstruction: PARTIAL / deliberately not blind-restored.
- PR #868: closed and unmerged.
- Real A-002 amplitude authorization and output regeneration: BLOCKED.

## Next action

Resume item-level scientific review without weakening the fail-closed amplitude gates. For A-002, obtain the exact pulse-table bytes and immutable convention/polarity evidence before running the full-table auditor or regenerating the quarantined JSON, CSV, stopping fractions, and ΔE–E figure. Independently review the concurrently merged PR #888 before promoting its scientific claims or marking its runtime acceptance complete.
