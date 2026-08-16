# AUD-FIG-002-R1 — Figure snapshot-provenance remediation

## Session

- **Stamp:** `2026-07-26T100542Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `8b460728fce2f550d63bed078f17c2285e0c2b2a`
- **Delivery head before archive:** `4858b5aa105927855ac4a59bd5e06038910b02aa`
- **Destination:** direct sequential commits to `main`; no task branch, pull-request transport, force-push, or history rewrite.
- **Policy:** `FIGURE_ARTIFACT_PROVENANCE_MUST_BIND_TO_SINGLE_READ_EXACT_BYTES`
- **Acceptance:** focused software/provenance remediation `VALIDATED / COMPLETE`.

## Reviewed area

- `tools/figure_registry/builder.py`
- `tools/figure_registry/registry.py`
- `tools/figure_registry/__init__.py`
- `tests/test_figure_registry.py`
- `tools/audit/audit_figure_registry_snapshot_provenance.py`
- `tests/test_audit_figure_registry_snapshot_provenance.py`
- existing validation JSON, SVG, audit report, active task, handoff, and recent repository history.

The former builder blob was `ef6e11cfac3e9eacdabfb146ec7586e8764fceb1`.

## Confirmed defects

1. Result JSON was parsed from one path read, while `_emit_quantitative` later reopened `entry.result` for SHA-256. A replacement could pair plotted values with another object's digest.
2. Source artifacts were copied from the path, then the path was hashed and statted afterward. A replacement could make metadata disagree with the copied artifact.
3. Publication initially needed an additional fail-closed correction so `os.replace` or related publication errors were converted into controlled `FigureRegistryError` failures after temporary-file cleanup.

## Implementation

Final builder blob: `cc56e548b54fd8f2692182de6114ee3bcfe196c4`.

The builder now:

- represents retained input bytes with immutable `ByteSnapshot` objects;
- decodes and parses result JSON from one strict-UTF-8 byte snapshot;
- derives result byte count and SHA-256 from that same snapshot;
- reads source artifacts once as bytes;
- publishes source targets atomically from the retained bytes using a same-directory temporary file, flush, `fsync`, and `os.replace`;
- independently re-reads the final target and verifies SHA-256 and byte count;
- records both source-snapshot and published-target identities;
- publishes source-data CSV files atomically from retained encoded bytes;
- rejects source/output aliases;
- removes temporary files and raises a controlled `FigureRegistryError` on publication failure.

## Deterministic controls

### Result-path replacement

Original retained JSON:

- bytes: `45`
- SHA-256: `880e5b3a422a0504eb35bf2918bd674cea0b38ae82805a60d6b48f5a248f4805`
- value: `0.68`

Replacement JSON after snapshot acquisition:

- bytes: `46`
- SHA-256: `3b6204ea9a2aad1f6c90d59f42f6484bb9ec9e766094bdae23981c70306988d7`
- value: `99.0`

The generated source data retained central value `0.68`, the original 45-byte size, and the original digest.

### Source-artifact replacement

Original retained source:

- bytes: `18`
- SHA-256: `baabbed7db11b99073870ca9517ea3caf20541d33848bfbde0830d77be6d2eb3`

Replacement source after snapshot acquisition:

- bytes: `38`
- SHA-256: `5846f2f03f5bfc0b295fccb71360798c49e95c1b1528964a82db0f17c92f7cb7`

The published target remained the exact original 18 bytes, and metadata recorded the matching source and target digest.

### Failure and alias controls

- injected `os.replace` failure: controlled `FigureRegistryError`;
- previous target preserved: yes;
- temporary files remaining: zero;
- source/output alias rejected: yes;
- aliased source bytes preserved: yes.

## Validation

```text
python -m py_compile \
  tools/figure_registry/builder.py \
  tests/test_figure_registry_snapshot_remediation.py \
  tools/audit/render_figure_registry_snapshot_provenance_evidence.py

PYTHONPATH=. pytest -q \
  tests/test_figure_registry_snapshot_remediation.py

5 passed in 0.39s
```

Additional checks:

- existing exact-source snapshot auditor: `VALIDATED`, zero findings;
- validation JSON parsed;
- SVG parsed as XML;
- maximum changed Python line length: 95.

Environment:

- Python `3.13.5`
- pytest `9.0.2`
- matplotlib `3.10.8`
- PyYAML `6.0.3`
- Linux `6.12.13`, x86_64, glibc `2.41`

## Validated identities

| Artifact | Git blob | Bytes | SHA-256 |
|---|---|---:|---|
| builder | `cc56e548b54fd8f2692182de6114ee3bcfe196c4` | 16683 | `1a280ff20d54ae74ef4eda9e1b33065f3dc46a6d3bfffd777149b9eb4a63ce21` |
| focused tests | `8550b37469278b708237d2a9ef181e24f608fda3` | 5993 | `eea7b91afd0f28cde7f128e0fdb5b2df092d73c34af368667c47b9017424d31a` |
| renderer | `15f29bfac9cc16265464bcb8ea0cd1e205cdaafa` | 4372 | `5780a78ab354e2c57fa19fb460787858f94bdff786b6f65b0315e377ad79300d` |
| validation JSON | `c9b543797b620385c4599dcb245ef61f3eb512cd` | 4134 | `516146d2101ce422fb66c22b5198e25320ae9ea361339b56423ffcdce30c8976` |
| SVG | `80f566fdb19924c7967ca4ee4d07b50c76ed2f19` | 2466 | `e09c040c6dde91caaf67a7b535a296f5a9ae33df5383bf5427130847dc4bf1d9` |

## Files changed

- `tools/figure_registry/builder.py`
- `tests/test_figure_registry_snapshot_remediation.py`
- `tools/audit/render_figure_registry_snapshot_provenance_evidence.py`
- `docs/validation/figure_registry_snapshot_provenance_validation.json`
- `docs/validation/figure_registry_snapshot_provenance.svg`
- `docs/validation/figure_registry_snapshot_provenance_audit.md`
- `chatgpt_todo/ACTIVE_TASK.md`
- this immutable archive
- `chatgpt_todo/HANDOFF.md` during final delivery.

## Direct-main sequence through archive

- `bd1b34493f98dfa6b6cefedb736ce9a10f207538` — task claim;
- `bde3641d03a5a8f1d36b6e226d8914b7fdb0c62f` — exact-byte snapshot implementation;
- `5acba6b08620b587d0bd5b18229a032141d173ad` — replacement-race tests;
- `dee2eac70bda7e9fb3f0a8e9d4aa10c53041b19c` — evidence renderer;
- `025efd86f9585801a7a92f0f3fd28eb9e211f2a0` — initial remediation record;
- `c7086b77a38c1aed94c609d156ab70620ca2eae8` — visual evidence;
- `592c310512d7009ab68ac832b23971c1ee7d2e04` — initial remediation report;
- `8f8f87ee669f7156231b6290b9366dd5969cda43` — controlled publication failure;
- `79a1064ccc6e0e1786a09d0283405ea91d01f496` — controlled-failure regression;
- `2033c983de88c026b27e1b3e00b121bb9628e333` — synchronized final evidence;
- `4858b5aa105927855ac4a59bd5e06038910b02aa` — finalized audit report.

GitHub contents writes returned successful direct-main commit SHAs rather than a conventional terminal `git push` transcript. No terminal transcript is claimed.

## Unrun checks and limitations

Not run:

- repository-wide pytest;
- ruff;
- complete paper build;
- repository-wide link inventory;
- GitHub Actions.

The execution container could not resolve `github.com`; repository reads and writes used the authenticated GitHub connector. Focused tests executed against the exact committed builder/test bytes reconstructed in the local validation subset, with Git blob identities checked after publication.

`SESSION_LOG.md` was not safely appended. The connector exposes whole-file replacement while the complete append-only file was only available through paged reads; reconstructing the historical file by transcription risked corrupting provenance. This archive and the latest handoff retain the complete append-equivalent record. Shared backlog/index/matrix files were likewise not partially replaced.

## Scientific boundary

This unit validates software and artifact provenance only. No paper scientific value, uncertainty, calibration, PID result, timing result, stopping profile, pile-up rate, or detector-performance claim was validated, regenerated, or changed.

## Acceptance and next action

`AUD-FIG-002-R1` is `COMPLETE` for the focused split-snapshot remediation. A later paper-build unit should execute the complete shipped registry and review generated output identities before using those artifacts as scientific evidence.
