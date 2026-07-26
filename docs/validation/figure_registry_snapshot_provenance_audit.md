# Figure-registry snapshot-provenance audit

- **Task:** `AUD-FIG-002`
- **Policy:** `FIGURE_ARTIFACT_PROVENANCE_MUST_BIND_TO_SINGLE_READ_EXACT_BYTES`
- **Initial remote main:** `770fa6e8ba305b29c539e64f1f151c4cf5dc1053`
- **Reviewed source:** `tools/figure_registry/builder.py`
- **Reviewed Git blob:** `ef6e11cfac3e9eacdabfb146ec7586e8764fceb1`
- **Audit status:** tooling `VALIDATED`; current builder contract `FLAWED`

## Question

Does every rendered or copied paper artifact record byte count and SHA-256 for the exact bytes that were used, or can a later replacement of an input path change the reported provenance after the artifact has already been produced?

## Confirmed source-contract defects

The current quantitative path parses a result with `path.read_text(...)`. After the figure has been rendered, `_emit_quantitative` calls `sha256_file(entry.result)` and records that later path hash in source data. If the path is replaced between those operations, the figure can contain values from one JSON object while its CSV cites another object's digest.

The current `figure_sourced` / `illustrative` path calls `shutil.copy2(source, target)` and only afterward calls `sha256_file(source)` and `source.stat().st_size`. A source replacement between copy and metadata generation can therefore make the metadata describe bytes and a size different from the copied target.

These are time-of-check/time-of-use provenance defects. They do not require malicious mutation: regenerated results, concurrent analysis publication, or a path swap can trigger the same mismatch.

## Independent behavioral controls

Two deterministic synthetic controls were executed.

### Result JSON replacement

1. JSON v1 with value `1.0` was read and parsed.
2. The path was replaced with JSON v2 containing value `99.0`.
3. The path was hashed afterward.

The value used by the hypothetical figure remained `1.0`, but the later digest was for v2:

- bytes used SHA-256: `33066bb044c6d3dc3c6afe6ca68d0104cf7f29a9735659cccf650018f5b24c78`;
- later reported SHA-256: `3b6204ea9a2aad1f6c90d59f42f6484bb9ec9e766094bdae23981c70306988d7`.

The corrected single-read control parsed and hashed one retained byte snapshot and matched exactly.

### Source-artifact replacement

1. source v1 was copied to the output target;
2. the source path was replaced by longer v2 bytes;
3. the source path was hashed and statted afterward.

The copied target digest was:

`baabbed7db11b99073870ca9517ea3caf20541d33848bfbde0830d77be6d2eb3`

but the later source metadata digest was:

`5846f2f03f5bfc0b295fccb71360798c49e95c1b1528964a82db0f17c92f7cb7`

and the later size was 38 bytes. The corrected control published the target from one retained byte snapshot and recorded the same digest.

## Audit result

The exact relevant current-source contract returns `FLAWED` with three findings:

- `RESULT_VALUE_AND_HASH_CAN_REFERENCE_DIFFERENT_BYTES`;
- `COPIED_SOURCE_AND_HASH_CAN_REFERENCE_DIFFERENT_BYTES`;
- `COPIED_SOURCE_AND_SIZE_CAN_REFERENCE_DIFFERENT_BYTES`.

Machine-readable and visual evidence:

- `docs/validation/figure_registry_snapshot_provenance_validation.json`
- `docs/validation/figure_registry_snapshot_provenance.svg`

The SVG is synthetic software/provenance evidence, not a scientific paper figure.

## Better method and required remediation

1. Read each result JSON as exact bytes once.
2. Decode and parse those retained bytes.
3. Compute byte count and SHA-256 from the same retained bytes used for numeric extraction.
4. Read each source artifact as exact bytes once.
5. Compute size and SHA-256 from that retained snapshot.
6. Publish the target atomically from those retained bytes.
7. Record target digest as an independent post-publication check.
8. Add replacement-race regressions that mutate the path after snapshot acquisition and require provenance to remain bound to the used bytes.

The builder should not re-open an input path merely to produce provenance for an artifact already derived from an earlier read.

## Reproducible validation

```text
python -m py_compile \
  tools/audit/audit_figure_registry_snapshot_provenance.py \
  tests/test_audit_figure_registry_snapshot_provenance.py \
  tools/audit/render_figure_registry_snapshot_provenance_evidence.py

PYTHONPATH=. pytest -q tests/test_audit_figure_registry_snapshot_provenance.py

5 passed in 0.10s
```

Additional checks:

- current-like fixture: `FLAWED`, three findings;
- corrected single-snapshot fixture: `VALIDATED`, zero findings;
- invalid UTF-8: controlled input error;
- destructive output alias: rejected;
- injected `os.replace` failure: previous JSON preserved and temporary file removed;
- validation JSON parse: passed;
- SVG XML parse: passed.

Local validation environment used Python 3.13.5 and pytest 9.0.2.

## Provenance boundary

The execution container could not resolve `github.com`. Repository inspection and writes used the authenticated GitHub connector. The exact current source blob and relevant lines were re-read at initial main; the local executable audit input is explicitly labelled `CONNECTOR_INSPECTED_EXACT_RELEVANT_SOURCE_EXCERPT`, not a byte-identical full checkout.

## Scientific boundary

This validates a software/provenance failure mode only. No result JSON, paper figure, uncertainty, source table, calibration, PID result, timing result, stopping profile, pile-up rate, or detector-performance claim was scientifically validated or changed.

`AUD-FIG-002` is `PARTIAL`: the defect and audit gate are validated, while the production builder remains non-accepting until the single-read remediation and direct builder regressions are delivered.
