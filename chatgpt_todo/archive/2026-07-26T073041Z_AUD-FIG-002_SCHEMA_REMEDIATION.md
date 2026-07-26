# Immutable session record — AUD-FIG-002

## Session

- **Stamp:** `2026-07-26T073041Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `67e019d5359d76cc82fa0634a8ae2161dd2a464c`
- **Task:** remediate the paper figure registry schema and builder disposition contract.
- **Policy:** `FIGURE_REGISTRY_STATUS_MUST_MAP_EXPLICITLY_TO_BUILD_DISPOSITION`
- **Focused acceptance:** `VALIDATED / COMPLETE`
- **Cumulative paper-figure review:** `PARTIAL`

## Repository and concurrency inspection

At the start of implementation, the newest remote-main commit was `67e019d5359d76cc82fa0634a8ae2161dd2a464c` (`fix(test): align pytest suite with honest post-audit claim state (#938)`). It changed tests only and explicitly documented that the real registry build remained xfailed pending status-governance remediation. No open pull requests were returned by the repository search. PR #868 was separately read and remained closed, unmerged, and non-mergeable; it was not modified.

Pre-change blobs:

- `tools/figure_registry/registry.py`: `0828d42c50e697bdc793d46d8bd23c4a57e3054d`;
- `tools/figure_registry/builder.py`: `de0a84ca4bde2c66f2482f1ff8ce2ffbdcbe95d2`;
- `tools/figure_registry/__init__.py`: `3b918efcc9a7f9263cfc707eddeadfc64eaf5440`;
- `tests/test_figure_registry.py`: `60d6368e27a51ac6630b46d4a2333c55e961c3f9`;
- `paper/figures.yaml`: `5d03f284fd2e018fcda786313f46c64ea7a20105`.

## Confirmed defect

The former production registry accepted only five statuses and two kinds, while the shipped registry used ten statuses and three kinds. It also required a `result` path unconditionally, rejecting source-artifact-only and illustrative entries. Scientific evidence state and build behavior were mixed together, so adding the missing vocabulary without a disposition map could accidentally authorize blocked, gated, partial, superseded, or MC-only artifacts.

The prior fail-closed audit measured nine findings:

- six unsupported statuses;
- one unsupported kind;
- one false illustrative-result requirement;
- one obsolete frozen-test vocabulary.

## Remediation

The controlled vocabulary is now eleven statuses, retaining `PRELIMINARY` for compatibility, and three kinds: `quantitative`, `figure_sourced`, and `illustrative`.

Explicit scientific disposition map:

- `VALIDATED`, `TENSION` -> `BUILD`;
- `PRELIMINARY` -> `CONDITIONAL`;
- `EXTERNAL_BLOCKER` -> `BLOCKED`;
- `ILLUSTRATIVE` -> `ILLUSTRATIVE`;
- `SIMULATION_RESULT`, `MC_METHOD_CLOSURE`, `PARTIAL`, `GATED`, `BLOCKED`, and `SUPERSEDED` -> `QUARANTINED`.

The builder now:

- records both scientific and runtime disposition;
- does not read numerical files for quarantined or blocked entries;
- requires a result JSON and finite uncertainty only for build-authorized quantitative entries;
- copies source-only and illustrative artifacts into separate locations with SHA-256 and byte-count provenance;
- supports slash-delimited nested result keys;
- rejects missing, null, nonnumeric, or nonfinite scalar/uncertainty values;
- preserves source-table SHA-256 checks;
- publishes `build_report.json` atomically;
- reports `PASS`, `FAIL`, `BLOCKED`, and `QUARANTINED` counts separately.

## Validation

Executed in the isolated validation fixture:

```text
python -m py_compile \
  tools/figure_registry/registry.py \
  tools/figure_registry/builder.py \
  tools/figure_registry/__init__.py \
  tests/test_figure_registry.py \
  tools/audit/render_figure_registry_schema_remediation_evidence.py

pytest -q tests/test_figure_registry.py

...........                                                              [100%]
11 passed in 0.52s
```

Additional checks:

- validation JSON parsed successfully;
- SVG parsed as XML;
- maximum changed Python line length: 97 characters;
- all 19 shipped entry IDs and every structural field consumed by `validate_registry` were represented in the local structural fixture;
- an exact `paper/figures.yaml` regression is committed for execution in a complete checkout.

Environment:

- Python `3.13.5`;
- PyYAML `6.0.3`;
- pandas `2.2.3`;
- matplotlib `3.10.8`;
- Linux `6.12.13-x86_64`.

The container could not resolve `github.com`; therefore the local shipped-registry fixture is explicitly labelled `CONNECTOR_INSPECTED_STRUCTURAL_FIELD_COPY`, not a byte-identical checkout. GitHub connector reads and blob identities were used for repository provenance. Repository-wide pytest, ruff, Actions, and a complete production paper build were not run.

## Evidence

- `docs/validation/figure_registry_schema_remediation_validation.json`
- `docs/validation/figure_registry_schema_remediation.svg`
- `docs/validation/figure_registry_schema_remediation_audit.md`
- `tools/audit/render_figure_registry_schema_remediation_evidence.py`
- `tests/test_figure_registry.py`

## Direct-main commits through task completion

- `6b5b8d4d8262a9b0021b91908867cda96ccbd6dc` — registry schema and status map;
- `413c7d931fde80b65d587803dfab9181b8d5b507` — builder disposition implementation;
- `bd7f41d9ed4e0d6b26fc4ddc500c9f68e79ec15d` — public exports;
- `bd46218b36c1169bacdd904844edab7385693f40` — focused regressions;
- `d9b0637e734edf4ee5f7d00ced94adc114a18adb` — evidence renderer;
- `4e1657d102da9c7308bd0965baf2262c3c41dd46` — machine-readable validation;
- `95c4af313e33f2f190a3878ffdaffe22ab067fda` — visual evidence;
- `ce9a647f93126aeb55545627ce98c86da16f9c8c` — audit report;
- `1433af6ad11d348bdc79a637cf715dad9d2a09a2` — active-task completion.

GitHub contents writes returned direct-main commit SHAs. No force update, branch rewrite, or task PR was used.

## Scientific boundary

This unit validates software governance and artifact provenance. It does not validate any paper figure's number, uncertainty, calibration, timing resolution, PID metric, stopping profile, pile-up rate, simulation-to-data transfer, or detector performance. No production paper figure was regenerated.

## Remaining work

- execute the exact shipped-registry and full builder tests in a complete checkout;
- run repository-wide pytest and ruff and inspect Actions when available;
- independently review the scientific authorization of each registry entry and its bound result/source artifact;
- regenerate paper artifacts only after every build-authorized input and uncertainty is content-addressed and scientifically accepted.

## Coordination limitation

`SESSION_LOG.md`, `BACKLOG.md`, `MASTER_INDEX.md`, and aggregate matrices were reviewed but not replaced. The connector provides whole-file replacement while complete append-only contents are returned through paged or truncated views; replacing a partial reconstruction could erase unrelated or concurrent provenance. This immutable archive and the latest `HANDOFF.md` preserve the complete append-equivalent record, but the mandatory aggregate synchronization gap remains explicit.
