# Figure registry schema-alignment audit

- **Task:** `AUD-FIG-001`
- **Policy:** `FIGURE_REGISTRY_SCHEMA_MUST_ACCEPT_ITS_SHIPPED_VOCABULARY`
- **Base main:** `d046259666a08dbf9188e8a80d5a3b0cbced5765`
- **Status:** audit tooling `VALIDATED`; shipped registry contract `FLAWED`

## Question

Can the shipped `paper/figures.yaml` pass the structural validator that is supposed to govern it, without changing scientific meaning or silently downgrading figure states?

## Repository facts inspected

The current registry implementation accepts only five statuses:

`VALIDATED`, `PRELIMINARY`, `TENSION`, `EXTERNAL_BLOCKER`, and `ILLUSTRATIVE`.

It accepts only two kinds: `quantitative` and `illustrative`, and it unconditionally requires every entry to carry a `result` path.

The shipped paper registry uses ten statuses and three kinds. Six used statuses are outside the implementation vocabulary:

- `BLOCKED`
- `GATED`
- `MC_METHOD_CLOSURE`
- `PARTIAL`
- `SIMULATION_RESULT`
- `SUPERSEDED`

It also uses `figure_sourced`, which is not an allowed kind. Five illustrative entries intentionally provide `source_figure` without a `result` path. The test suite freezes the obsolete five-status set while separately asserting that the shipped registry validates cleanly. Those requirements cannot all be true simultaneously.

## Demonstrated failure mode

The fail-closed semantic reconstruction returned `FLAWED` with nine findings:

- six `REGISTRY_STATUS_UNSUPPORTED` findings;
- one `REGISTRY_KIND_UNSUPPORTED` finding;
- one `ILLUSTRATIVE_RESULT_FALSE_REQUIREMENT` finding;
- one `TEST_FREEZES_OBSOLETE_STATUS_SET` finding.

This is a software-governance failure. It does not imply that any individual figure value is numerically wrong. It means the paper-figure front door cannot consistently represent the repository's own evidence classes, blocked states, correction history, and source-figure-only artifacts.

## Better method

The registry should use an explicit disposition table rather than conflating scientific evidence state with build behavior.

1. Preserve the repository's scientific statuses as a controlled vocabulary.
2. Map each status to a build disposition such as `BUILD`, `BLOCKED`, `QUARANTINED`, or `ILLUSTRATIVE`.
3. Make required paths conditional on kind:
   - `quantitative`: require `result`; require uncertainty for build-authorized quantitative states;
   - `figure_sourced`: require `source_figure`; do not invent a scalar result requirement;
   - `illustrative`: require `source_figure`; prohibit quantitative headline extraction.
4. Keep `BLOCKED`, `GATED`, `PARTIAL`, `SUPERSEDED`, and MC-only states non-authorizing unless a separately documented paper policy permits them.
5. Update tests to derive their expected vocabulary from the documented schema and require the exact shipped registry to validate.

## Reproducible validation

```text
python -m py_compile \
  tools/audit/audit_figure_registry_schema_alignment.py \
  tests/test_audit_figure_registry_schema_alignment.py \
  tools/audit/render_figure_registry_schema_evidence.py

pytest -q tests/test_audit_figure_registry_schema_alignment.py

5 passed in 0.07s
```

Additional checks:

- current-like fixture: `FLAWED`, nine findings;
- corrected fixture: `VALIDATED`, zero findings;
- invalid UTF-8: controlled input error;
- output/input alias: rejected;
- atomic JSON publication: passed;
- validation JSON parse: passed;
- SVG XML parse: passed.

## Provenance boundary

The execution container could not resolve `github.com`, so a complete checkout was unavailable. The current repository semantics were reconstructed from authenticated GitHub connector reads and bound to the following Git blobs:

- `tools/figure_registry/registry.py`: `0828d42c50e697bdc793d46d8bd23c4a57e3054d`;
- `paper/figures.yaml`: `5d03f284fd2e018fcda786313f46c64ea7a20105`;
- `tests/test_figure_registry.py`: `1546b8b6896fdbbdce28cfb53fccc8d727479436`.

The machine-readable evidence labels its audit input as a connector-reconstructed semantic excerpt, not a byte-identical local copy. No claim is made that repository-wide pytest or the full figure builder was executed in this environment.

## Acceptance boundary

`AUD-FIG-001` is `PARTIAL`. The defect and fail-closed audit are validated. The registry implementation, builder disposition map, shipped registry, and existing tests were deliberately not rewritten in this audit unit.

No paper figure was regenerated. No source result, uncertainty, detector calibration, PID metric, timing resolution, stopping profile, pile-up rate, or detector-performance claim was validated or changed.
