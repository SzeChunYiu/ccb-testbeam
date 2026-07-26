# Figure-registry snapshot-provenance remediation

- **Task:** `AUD-FIG-002-R1`
- **Policy:** `FIGURE_ARTIFACT_PROVENANCE_MUST_BIND_TO_SINGLE_READ_EXACT_BYTES`
- **Initial remote main:** `8b460728fce2f550d63bed078f17c2285e0c2b2a`
- **Former builder blob:** `ef6e11cfac3e9eacdabfb146ec7586e8764fceb1`
- **Corrected builder blob:** `aca5e9225247b92ca0b4011f3ec37e61197d3bfd`
- **Implementation commit:** `bde3641d03a5a8f1d36b6e226d8914b7fdb0c62f`
- **Status:** focused software/provenance remediation `VALIDATED`

## Defect remediated

The former quantitative path parsed result JSON from one path read but later reopened the path through `sha256_file(entry.result)`. A concurrent replacement could pair a plotted value with the digest of different bytes.

The former source-artifact path copied with `shutil.copy2(source, target)` and only afterward hashed and statted the source path. A replacement could make metadata disagree with the artifact copied into the paper output.

## Corrected contract

`tools/figure_registry/builder.py` now:

1. retains every result JSON as one `ByteSnapshot`;
2. decodes strict UTF-8 and parses JSON from those retained bytes;
3. records result SHA-256 and byte count from the same snapshot used for numeric extraction;
4. retains each `figure_sourced` or illustrative artifact as one byte snapshot;
5. publishes the target from those bytes using a same-directory temporary file, flush, `fsync`, and `os.replace`;
6. independently re-reads the final target and requires its SHA-256 and byte count to match the retained snapshot;
7. records source and published-target identities in the source-data CSV;
8. publishes source-data CSV files atomically from retained encoded bytes;
9. rejects resolved-path and existing-file aliases before source publication.

The generated quantitative CSV also records the rendered figure's SHA-256 and byte count. This is output provenance and does not validate the underlying scientific number.

## Deterministic replacement controls

### Result JSON

The test retained 45 original bytes containing value `0.68`, then replaced the path with 46 bytes containing value `99.0` before rendering completed.

- retained/original SHA-256: `880e5b3a422a0504eb35bf2918bd674cea0b38ae82805a60d6b48f5a248f4805`;
- replacement SHA-256: `3b6204ea9a2aad1f6c90d59f42f6484bb9ec9e766094bdae23981c70306988d7`;
- plotted/source-data central value: `0.68`;
- recorded result SHA-256: the retained/original digest.

The later path replacement therefore cannot alter provenance for the value already extracted.

### Source artifact

The test retained 18 original bytes, then replaced the source path with 38 different bytes after snapshot acquisition.

- retained/original SHA-256: `baabbed7db11b99073870ca9517ea3caf20541d33848bfbde0830d77be6d2eb3`;
- replacement SHA-256: `5846f2f03f5bfc0b295fccb71360798c49e95c1b1528964a82db0f17c92f7cb7`;
- published target SHA-256: the retained/original digest;
- published target byte count: `18`.

An injected `os.replace` failure preserved the previous target and left no temporary file. A source/output alias was rejected without modifying source bytes.

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

The existing exact-source auditor returned `VALIDATED` with zero findings. The validation JSON parsed, the SVG parsed as XML, and the maximum changed Python line length was 95 characters.

Validated identities:

| Artifact | Git blob | Bytes | SHA-256 |
|---|---|---:|---|
| builder | `aca5e9225247b92ca0b4011f3ec37e61197d3bfd` | 16274 | `27a6c833d1aafbbcbb51e6a879e04d8c8a8608681e3b198f21cf70404e5f8c18` |
| focused tests | `e187363c1f59134fbeddbf20363cb1b3d9859115` | 5973 | `d4dc17a63d1e7ad4d3e622baef56d8c84d0e9b8fe66ce3eef9ff349d2198f065` |
| renderer | `15f29bfac9cc16265464bcb8ea0cd1e205cdaafa` | 4372 | `5780a78ab354e2c57fa19fb460787858f94bdff786b6f65b0315e377ad79300d` |
| validation JSON | `654cd47e1ed32545791abc18bd12d35e1aabf286` | 3900 | `d1f6cd3f070a02e6ed6649642eff5788e91db707c121076ed73626d8f72c7c53` |
| SVG | `80f566fdb19924c7967ca4ee4d07b50c76ed2f19` | 2466 | `e09c040c6dde91caaf67a7b535a296f5a9ae33df5383bf5427130847dc4bf1d9` |

## Evidence

- `docs/validation/figure_registry_snapshot_provenance_validation.json`
- `docs/validation/figure_registry_snapshot_provenance.svg`
- `tests/test_figure_registry_snapshot_remediation.py`

The SVG is synthetic software/provenance evidence, not a scientific paper figure.

## Acceptance boundary

The focused split-snapshot defect is corrected and `AUD-FIG-002-R1` is `COMPLETE`. Repository-wide pytest, ruff, the complete paper build, link inventory, and GitHub Actions were not run and are not claimed as passing.

No paper scientific value, uncertainty, calibration, PID result, timing result, stopping profile, pile-up rate, or detector-performance claim was validated or changed.
