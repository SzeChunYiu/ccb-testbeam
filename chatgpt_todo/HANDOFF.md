# Latest Handoff

## Session

- **Task ID:** `AUD-FIG-002`
- **Stamp:** `2026-07-26T092835Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `770fa6e8ba305b29c539e64f1f151c4cf5dc1053`
- **Validated delivery/handoff commit:** `3b1de01862a68f15a8adfa8d31bf1c2a20580e4a`
- **Remote main after validated delivery:** `72458c33e79df28a3f6684826a3dbaed77c37d72`
- **Destination:** direct sequential commits to `main`; no task branch, pull-request transport, force-push, or history rewrite.
- **Push result:** GitHub contents API returned a successful direct-main commit SHA for every write. The connector does not return a conventional terminal `git push` transcript, and none is claimed.
- **Focused acceptance:** audit implementation, tests, calculations, JSON, SVG, report, archive, and hash-correction addendum `VALIDATED`.
- **Production acceptance:** paper-figure builder remains `FLAWED / PARTIAL` pending a single-read exact-byte remediation.

## Finding

Policy:

`FIGURE_ARTIFACT_PROVENANCE_MUST_BIND_TO_SINGLE_READ_EXACT_BYTES`

Current `tools/figure_registry/builder.py`, Git blob
`ef6e11cfac3e9eacdabfb146ec7586e8764fceb1`, has two split-snapshot paths:

1. `_load_result` parses JSON through `path.read_text(...)`, while `_emit_quantitative` later calls `sha256_file(entry.result)` after rendering.
2. `_emit_existing_artifact` calls `shutil.copy2(source, target)`, then later calls `sha256_file(source)` and `source.stat().st_size`.

A concurrent replacement of either input path can therefore make source-data metadata describe bytes different from those used to render or copy the published artifact.

## Independent controls

### Result JSON replacement

- bytes used SHA-256: `33066bb044c6d3dc3c6afe6ca68d0104cf7f29a9735659cccf650018f5b24c78`;
- later path SHA-256: `3b6204ea9a2aad1f6c90d59f42f6484bb9ec9e766094bdae23981c70306988d7`;
- figure-side numeric value remained `1.0` from the first snapshot;
- later provenance digest described the replacement JSON.

### Source-artifact replacement

- copied target SHA-256: `baabbed7db11b99073870ca9517ea3caf20541d33848bfbde0830d77be6d2eb3`;
- later source-path SHA-256: `5846f2f03f5bfc0b295fccb71360798c49e95c1b1528964a82db0f17c92f7cb7`;
- later source size: 38 bytes;
- later metadata did not match the copied target.

Corrected controls retained one byte snapshot for parse/copy, hashing, and sizing and matched exactly.

## Work delivered

Added:

- `tools/audit/audit_figure_registry_snapshot_provenance.py`
- `tests/test_audit_figure_registry_snapshot_provenance.py`
- `tools/audit/render_figure_registry_snapshot_provenance_evidence.py`
- `docs/validation/figure_registry_snapshot_provenance_validation.json`
- `docs/validation/figure_registry_snapshot_provenance.svg`
- `docs/validation/figure_registry_snapshot_provenance_audit.md`
- `chatgpt_todo/archive/2026-07-26T092835Z_AUD-FIG-002_SNAPSHOT_PROVENANCE.md`
- `chatgpt_todo/archive/2026-07-26T092835Z_AUD-FIG-002_HASH_CORRECTION.md`

Updated:

- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/HANDOFF.md`

## Validation

```text
python -m py_compile \
  tools/audit/audit_figure_registry_snapshot_provenance.py \
  tests/test_audit_figure_registry_snapshot_provenance.py \
  tools/audit/render_figure_registry_snapshot_provenance_evidence.py

PYTHONPATH=. pytest -q tests/test_audit_figure_registry_snapshot_provenance.py

5 passed in 0.04s
```

Additional results:

- current-like source contract: `FLAWED`, three findings;
- corrected single-snapshot fixture: `VALIDATED`, zero findings;
- invalid UTF-8: controlled input error;
- destructive source/output alias: rejected;
- injected `os.replace` failure: previous JSON preserved and temporary file removed;
- validation JSON parsed;
- SVG parsed as XML.

Validated identities:

| Artifact | Git blob | SHA-256 |
|---|---|---|
| auditor | `bb545abbfb52bfad680dcb4fa69fa177c1b025ee` | `e00f21ed1d936d603b80b07b053dd6488b4f45095d60ae3a2cad04fa20ee8308` |
| tests | `88630c60e4fe7f5c6e16b4c52478c77969bf08e5` | `11bd9a8a07f61c4ddb8d74d87e44b448722142772dde4e73a750c70e964400bf` |
| renderer | `4302d108a045afc043d267bd69a25546ba6e4126` | `0f13ded4f9f5f80c20ecfb01229e6b9f9354fcba8e8cf2a9e98e180db2f55e5b` |
| validation JSON | `80dff731ac06cfcfd35e20623cee521ada778018` | `e42ddb438a3c97a9ef9c5fadef61e1a3563c41599a179a15b28e517eff45f9be` |
| SVG | retained on `main` | `36ada9d68a446236c02235d219f9f60c822130dd6b30a1176243f8f23543e669` |

The immutable correction addendum records that an earlier archive entry contained an incorrect validation-JSON digest; no audit conclusion changed.

## Direct-main sequence

- `f5593cbb4a06bd1301b5423e1e113c1d2894f383` — task claim;
- `50ab80d716200d1ce73fff8c008814cab84fa72f` — fail-closed audit gate;
- `48a2f9beb8335ec06ebf37e2644c6019a65a435e` — focused tests;
- `8c9de501999cdd2ec7b78e4eefdc2f5bbe79cc34` — evidence renderer;
- `99a7b9153e9a18753a1ac8777eefc189dbf9abe6` — machine-readable evidence;
- `45e8bc4297271ad7015ff0be0a2addeec54ba0be` — visual evidence;
- `1b05fedbf4ef950535a135fb0b83e2e4f6092615` — audit report;
- `ce4f35b14d479f5d3c5cd92bf013a2ed78cbd9d4` — immutable archive;
- `134670e02f2c7115af98a1fc9adb8011a1d50c0c` — active-task completion;
- `3b1de01862a68f15a8adfa8d31bf1c2a20580e4a` — validated delivery handoff;
- `72458c33e79df28a3f6684826a3dbaed77c37d72` — hash-correction addendum.

## Required remediation

1. Read each result JSON as exact bytes once.
2. Decode and parse those retained bytes.
3. Derive result byte count and SHA-256 from the same retained bytes used for numerical extraction.
4. Read each source artifact as exact bytes once.
5. Derive size and SHA-256 from that snapshot and atomically publish the target from it.
6. Record an independent final-target digest.
7. Add direct builder regressions that replace input paths after snapshot acquisition.
8. Require the exact-current-source audit to return zero findings and rerun focused figure-registry tests.

## Scientific boundary

This validates software/provenance behavior only. No paper figure was regenerated, and no scientific value, uncertainty, calibration, PID result, timing result, stopping profile, pile-up rate, or detector-performance claim was validated or changed.

Repository-wide pytest, ruff, full paper build, complete link checking, and GitHub Actions were not run and are not claimed as passing. No combined status checks were attached to the initial main head.

PR #939 remained open, non-mergeable, and unmerged. PR #868 remained closed and unmerged.

`SESSION_LOG.md` could not be safely appended in this connector-only run. The available write operation replaces the entire file, while the complete append-only bytes were exposed only through paged/truncated responses. Reconstructing a large historical log by transcription risked erasing or corrupting provenance. The immutable archive and this handoff contain the complete append-equivalent record; the mandatory log synchronization remains explicitly unresolved rather than being reported as completed.

## Next action

Remediate the production builder with single-read result/source snapshots and atomic byte publication, then execute direct builder replacement-race regressions and the shipped registry test. Do not use generated paper artifacts as evidence until their recorded provenance is bound to the bytes actually used.
