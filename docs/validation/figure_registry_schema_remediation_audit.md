# Figure registry schema and disposition remediation

- **Task:** `AUD-FIG-002`
- **Policy:** `FIGURE_REGISTRY_STATUS_MUST_MAP_EXPLICITLY_TO_BUILD_DISPOSITION`
- **Base main:** `67e019d5359d76cc82fa0634a8ae2161dd2a464c`
- **Focused status:** `VALIDATED`

## Scientific-governance question

Can the paper registry preserve all shipped scientific evidence states while preventing
blocked, gated, partial, superseded, or MC-only artifacts from becoming paper-authorized
merely because a file exists?

## Confirmed defect

The former implementation accepted five statuses and two kinds, required `result` for
every entry, and embedded status-specific behaviour directly in the builder. The shipped
registry uses ten statuses and three kinds, including source-artifact-only and illustrative
entries. The former structural test froze the obsolete vocabulary while also requiring the
shipped registry to validate.

The prior fail-closed audit measured nine findings: six unsupported statuses, one
unsupported kind, one false illustrative-result requirement, and one obsolete frozen-test
vocabulary.

## Remediation

The production registry now defines a controlled vocabulary and an explicit status-to-build
map:

- `VALIDATED`, `TENSION` -> `BUILD`;
- `PRELIMINARY` -> `CONDITIONAL`;
- `EXTERNAL_BLOCKER` -> `BLOCKED`;
- `ILLUSTRATIVE` -> `ILLUSTRATIVE`;
- `SIMULATION_RESULT`, `MC_METHOD_CLOSURE`, `PARTIAL`, `GATED`, `BLOCKED`, and
  `SUPERSEDED` -> `QUARANTINED`.

Path requirements are conditional on kind and authorization:

- build-authorized `quantitative` entries require a result JSON and finite uncertainty;
- `figure_sourced` entries require `source_figure` and do not invent a scalar-result
  contract;
- `illustrative` entries require `source_figure`, are copied into a separate directory, and
  never count as quantitative figures;
- quarantined and blocked states do not read or validate numerical result files.

The builder now records both scientific disposition and runtime disposition, includes a
`QUARANTINED` summary count, copies existing source artifacts with SHA-256 and byte-count
provenance, accepts slash-delimited nested result keys, rejects nonfinite scalar values, and
publishes `build_report.json` atomically.

## Validation

```text
python -m py_compile \
  tools/figure_registry/registry.py \
  tools/figure_registry/builder.py \
  tools/figure_registry/__init__.py \
  tests/test_figure_registry.py \
  tools/audit/render_figure_registry_schema_remediation_evidence.py

pytest -q tests/test_figure_registry.py

11 passed in 0.52s
```

Focused regressions cover:

- build-authorized quantitative result and uncertainty handling;
- nested `value_key` resolution;
- source-table SHA-256 mismatch;
- source-artifact-only and illustrative paths;
- explicit quarantine of six non-authorizing scientific statuses;
- external-blocker and preliminary policy;
- unknown status/kind rejection;
- duplicate IDs and conditional path requirements;
- the complete status/kind vocabulary used by the shipped registry.

The validation JSON and SVG parse successfully. Changed Python lines are at most 97
characters.

## Provenance

Inspected pre-change blobs:

- `tools/figure_registry/registry.py`: `0828d42c50e697bdc793d46d8bd23c4a57e3054d`;
- `tools/figure_registry/builder.py`: `de0a84ca4bde2c66f2482f1ff8ce2ffbdcbe95d2`;
- `tools/figure_registry/__init__.py`: `3b918efcc9a7f9263cfc707eddeadfc64eaf5440`;
- `tests/test_figure_registry.py`: `60d6368e27a51ac6630b46d4a2333c55e961c3f9`;
- `paper/figures.yaml`: `5d03f284fd2e018fcda786313f46c64ea7a20105`.

The execution container could not resolve `github.com`. The local registry fixture reproduces
all 19 connector-inspected entry IDs and every structural field consumed by
`validate_registry`; it is explicitly labelled a structural field copy rather than a
byte-identical checkout. The exact shipped-registry regression is committed for execution in
a complete repository checkout.

## Acceptance boundary

This remediation validates schema alignment, scientific disposition mapping, source-artifact
handling, and focused builder behaviour. It does not validate any figure's value,
uncertainty, calibration, PID metric, timing result, stopping profile, pile-up rate, or
detector-performance claim. No paper figure was regenerated from production inputs in this
unit.
