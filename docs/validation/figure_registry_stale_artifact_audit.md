# Figure-registry stale managed-artifact audit

## Status

- Task: `AUD-FIG-006`
- Policy: `FIGURE_REGISTRY_BUILD_MUST_NOT_LEAVE_STALE_ARTIFACTS`
- Audit implementation/evidence: `VALIDATED`
- Current production builder contract: `FLAWED`
- Scientific scope: software and artifact provenance only

## Question

Can a figure that was produced by an earlier successful registry build remain at a
managed paper-output path after the corresponding current entry becomes blocked,
quarantined, fails to build, or is removed from the registry?

## Inspected repository facts

The current `tools/figure_registry/builder.py` Git blob is
`39dcd3b13d3886c43f3e9111291d420f86cc7c85` on remote `main` at
`8acfc727a1479ff5b616042e65743b0652900c25`.

The current control flow:

1. returns immediately for `BLOCKED` and `QUARANTINED` dispositions;
2. catches per-entry `FigureRegistryError` and records `FAIL`;
3. iterates only over IDs present in the current registry;
4. does not call a managed-output cleanup or reconciliation function in those paths.

The version-controlled source fixture records the exact inspected blob and source
range. It is a semantic control-flow excerpt, not a byte-identical copy of the
complete 526-line module. The auditor is implementation-ready for the complete
source file in a checkout.

## Deterministic controls

Each scenario starts with two prior managed files:

- `Q.png`
- `Q_source_data.csv`

The current no-cleanup model leaves both files in all three cases:

| Current registry state | Stale files after build |
|---|---:|
| entry becomes BLOCKED | 2 |
| entry raises a build failure | 2 |
| entry is removed from registry | 2 |

The corrected cleanup model leaves zero files in each case.

These controls do not claim that every existing paper output is stale. They show
that the current control flow does not establish that a non-PASS or removed entry
has no older managed artifact at its former path.

## Findings

1. `NO_ENTRY_OUTPUT_CLEANUP`: `_process_entry` contains no managed-artifact cleanup
   call.
2. `NONPASS_DISPOSITION_CAN_RETAIN_STALE_ARTIFACTS`: blocked or quarantined entries
   return before any artifact removal.
3. `FAILED_ENTRY_CAN_RETAIN_STALE_ARTIFACTS`: the per-entry failure handler records
   `FAIL` without removing prior outputs.
4. `REMOVED_ENTRY_CAN_RETAIN_STALE_ARTIFACTS`: the build does not reconcile previous
   managed outputs against current registry IDs.

A stale PNG can therefore remain discoverable or includable even when the current
`build_report.json` no longer authorizes it. This is a paper-artifact integrity
problem, not evidence that a scientific central value is numerically wrong.

## Better method

The remediation should define a complete managed-output inventory per entry and
make the output set fail closed:

1. retain the previous build report or a dedicated manifest only as an inventory,
   never as scientific authorization;
2. remove or quarantine prior managed paths before recording a current non-PASS;
3. reconcile IDs removed from the registry;
4. prevent path escape and source/output aliasing;
5. publish the build report and managed artifact set as one coherent state;
6. add direct regressions for PASS-to-BLOCKED, PASS-to-FAIL, kind/suffix changes,
   and removed entries;
7. record removed/quarantined paths and their prior hashes in the report.

A directory-level staging and controlled swap is preferable to a sequence of
untracked deletions because it minimizes mixed old/new build states. The swap must
preserve the previous validated directory if publication fails, while a reported
failed build must not leave the previous artifact set in the canonical current
output location.

## Validation

Executed:

```text
python -m py_compile \
  tools/audit/audit_figure_registry_stale_artifacts.py \
  tests/test_audit_figure_registry_stale_artifacts.py \
  tools/audit/render_figure_registry_stale_artifact_evidence.py

PYTHONPATH=. pytest -q \
  tests/test_audit_figure_registry_stale_artifacts.py

6 passed in 0.05s
```

Additional checks:

- current-like fixture: `FLAWED`, four finding families;
- corrected fixture: `VALIDATED`, zero findings;
- invalid UTF-8: controlled rejection;
- input/output alias: controlled rejection;
- injected JSON publication failure: previous target preserved, temporary removed;
- validation JSON parse: passed;
- SVG XML parse: passed;
- maximum changed Python line length: 93 characters.

Environment: Python 3.13.5, pytest 9.0.2.

## Evidence

- Auditor: `tools/audit/audit_figure_registry_stale_artifacts.py`
- Regressions: `tests/test_audit_figure_registry_stale_artifacts.py`
- Source fixture:
  `docs/validation/fixtures/figure_registry_builder_stale_artifact_current.py`
- Machine record:
  `docs/validation/figure_registry_stale_artifact_validation.json`
- Visual evidence: `docs/validation/figure_registry_stale_artifact.svg`
- Renderer: `tools/audit/render_figure_registry_stale_artifact_evidence.py`

Local SHA-256 identities before publication:

| File | SHA-256 | Bytes |
|---|---|---:|
| auditor | `48a96d9166f84b42c7a727e7246291eab7844b515be0bef75b576d04fe6c39ba` | 9820 |
| tests | `016ed25318f18d2a5925ff88030f4a00897c96faca7691bf599842d71db1304e` | 4951 |
| renderer | `12dd5843251aca51f051bf9662316c94cc83ba6b8fa18cca6566ca6130c55814` | 3813 |
| source fixture | `a4d7490428b48467f101a2b9847799ac1594885d599adf7cb416421c66b76538` | 1796 |
| validation JSON | `b3035c63baec67ae943b6e6fae51f9f53028cd09826168b934e64c0ad1617baa` | 3155 |
| SVG | `abe2e9d054c3ec4f283e376de575dbb4dded01e8e52076339692ea5b0925f7bd` | 2084 |

## Acceptance boundary

This run validates the audit gate and reproduces the stale-output failure mode. It
does not remediate the production builder and does not assert that a particular
committed paper figure is stale.

No paper figure, registry entry, scientific value, uncertainty, calibration, timing
result, PID result, stopping profile, pile-up rate, or detector-performance claim
was regenerated or revalidated.

Completion requires production cleanup/reconciliation code, direct builder tests,
and a clean complete registry/paper build whose report and output inventory close
exactly.
