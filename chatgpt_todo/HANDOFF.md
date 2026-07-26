# Latest Handoff

## Session

- **Task ID:** `AUD-FIG-002-R1`
- **Stamp:** `2026-07-26T100542Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `8b460728fce2f550d63bed078f17c2285e0c2b2a`
- **Validated delivery/handoff commit:** `92c453723c3014621a63c00f0b4242d0b24a0ef9`
- **Remote main after validated delivery:** `92c453723c3014621a63c00f0b4242d0b24a0ef9`
- **Destination:** direct sequential commits to `main`; no task branch, pull-request transport, force-push, or history rewrite.
- **Push result:** GitHub contents API returned a successful direct-main commit SHA for every write. The connector does not return a conventional terminal `git push` transcript, and none is claimed.
- **Focused acceptance:** implementation, tests, replacement controls, JSON, SVG, report, active-task completion, immutable archive, and handoff `VALIDATED / COMPLETE`.
- **Scientific acceptance:** no scientific paper value, uncertainty, or detector-performance claim was authorized or changed.

## Finding and correction

Policy:

`FIGURE_ARTIFACT_PROVENANCE_MUST_BIND_TO_SINGLE_READ_EXACT_BYTES`

Former builder blob `ef6e11cfac3e9eacdabfb146ec7586e8764fceb1` had two split-snapshot paths:

1. result JSON was parsed from one path read and later rehashed from `entry.result` after rendering;
2. source artifacts were copied before the source path was rehashed and statted.

A path replacement could therefore make provenance describe different bytes from those used. The final builder blob `cc56e548b54fd8f2692182de6114ee3bcfe196c4` now:

- retains result and source bytes once as immutable snapshots;
- parses strict-UTF-8 JSON from retained bytes;
- derives source hash and byte count from those same bytes;
- publishes source artifacts atomically from the retained snapshot;
- verifies the final target's SHA-256 and byte count independently;
- records source and target identities;
- publishes source-data CSV atomically;
- rejects aliases;
- cleans temporary files and reports publication errors through controlled `FigureRegistryError` failures.

## Independent replacement controls

### Result JSON

- retained bytes: `45`;
- retained SHA-256: `880e5b3a422a0504eb35bf2918bd674cea0b38ae82805a60d6b48f5a248f4805`;
- retained value: `0.68`;
- later replacement bytes: `46`;
- replacement SHA-256: `3b6204ea9a2aad1f6c90d59f42f6484bb9ec9e766094bdae23981c70306988d7`;
- generated source data retained value `0.68`, original byte count, and original digest.

### Source artifact

- retained bytes: `18`;
- retained SHA-256: `baabbed7db11b99073870ca9517ea3caf20541d33848bfbde0830d77be6d2eb3`;
- later replacement bytes: `38`;
- replacement SHA-256: `5846f2f03f5bfc0b295fccb71360798c49e95c1b1528964a82db0f17c92f7cb7`;
- published target remained the original 18 bytes with the original digest.

Injected `os.replace` failure produced a controlled error, preserved the previous target, and left zero temporary files. Source/output aliasing was rejected without modifying source bytes.

## Work delivered

- `tools/figure_registry/builder.py`
- `tests/test_figure_registry_snapshot_remediation.py`
- `tools/audit/render_figure_registry_snapshot_provenance_evidence.py`
- `docs/validation/figure_registry_snapshot_provenance_validation.json`
- `docs/validation/figure_registry_snapshot_provenance.svg`
- `docs/validation/figure_registry_snapshot_provenance_audit.md`
- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/archive/2026-07-26T100542Z_AUD-FIG-002-R1_SNAPSHOT_REMEDIATION.md`
- this handoff.

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

Additional results:

- existing exact-source auditor: `VALIDATED`, zero findings;
- validation JSON parsed;
- SVG parsed as XML;
- maximum changed Python line length: 95;
- environment: Python 3.13.5, pytest 9.0.2, matplotlib 3.10.8, PyYAML 6.0.3.

Validated identities:

| Artifact | Git blob | Bytes | SHA-256 |
|---|---|---:|---|
| builder | `cc56e548b54fd8f2692182de6114ee3bcfe196c4` | 16683 | `1a280ff20d54ae74ef4eda9e1b33065f3dc46a6d3bfffd777149b9eb4a63ce21` |
| focused tests | `8550b37469278b708237d2a9ef181e24f608fda3` | 5993 | `eea7b91afd0f28cde7f128e0fdb5b2df092d73c34af368667c47b9017424d31a` |
| renderer | `15f29bfac9cc16265464bcb8ea0cd1e205cdaafa` | 4372 | `5780a78ab354e2c57fa19fb460787858f94bdff786b6f65b0315e377ad79300d` |
| validation JSON | `c9b543797b620385c4599dcb245ef61f3eb512cd` | 4134 | `516146d2101ce422fb66c22b5198e25320ae9ea361339b56423ffcdce30c8976` |
| SVG | `80f566fdb19924c7967ca4ee4d07b50c76ed2f19` | 2466 | `e09c040c6dde91caaf67a7b535a296f5a9ae33df5383bf5427130847dc4bf1d9` |

## Direct-main sequence

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
- `4858b5aa105927855ac4a59bd5e06038910b02aa` — finalized audit report;
- `605866376ef1ac783da226d126df55ca2e082a50` — immutable archive;
- `f3116cc6d21fbb714ffb4ad4d79cdf09cd073bf0` — active-task completion;
- `92c453723c3014621a63c00f0b4242d0b24a0ef9` — validated delivery handoff.

## Unrun checks and unresolved coordination

Repository-wide pytest, ruff, the complete paper build, the repository-wide link inventory, and GitHub Actions were not run and are not claimed as passing.

The execution container could not resolve `github.com`; repository reads and writes used the authenticated connector. Focused tests ran against the exact committed builder/test bytes reconstructed in the local validation subset, with Git blob identities confirmed after publication.

`SESSION_LOG.md` was not safely appended. The connector exposes whole-file replacement while the complete append-only file was available only through paged reads; reconstructing it by transcription risked corrupting historical provenance. The immutable archive and this handoff provide the complete append-equivalent record. Shared backlog/index/matrix files were not partially replaced for the same preservation reason.

PR #939 remained open and unmerged. PR #868 remained closed and unmerged. Neither was modified.

## Scientific boundary and next action

No paper scientific value, uncertainty, calibration, PID result, timing result, stopping profile, pile-up rate, or detector-performance claim was validated or changed.

The focused split-snapshot remediation is complete. The next paper-figure unit should run the complete shipped registry and inspect all generated artifact identities before using those artifacts as scientific evidence.
