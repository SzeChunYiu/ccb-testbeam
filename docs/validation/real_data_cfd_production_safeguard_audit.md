# Real-data CFD production safeguard remediation

- **Task:** `AUD-TIMING-003-R1`
- **Policy:** `REAL_DATA_CFD_REQUIRES_COMPOSITE_EVENT_KEYS_AND_PAIR_ONLY_INFERENCE`
- **Base remote main:** `be97e1a1e77de3bba6305f28802d1c876d2d1605`
- **Status:** focused software remediation `VALIDATED`; production physics result `PENDING_CONTENT_ADDRESSED_RERUN`

## Trigger

PR #939 was merged to `main` on 2026-07-26 after the repository already contained three fail-closed audits of the same producer:

1. event identity must include `run` as well as `event_id`;
2. residual plots must not hide most events outside a fixed display range;
3. a B6-B8 pair `sigma68` cannot be divided by `sqrt(2)` and presented as an individual-stave result without validated assumptions and deconvolution.

The merge commit reintroduced all three demonstrated defects into the canonical branch and published the unsupported `0.635 ns` single-stave interpretation.

## Corrective implementation

The producer is now version `2.0.0` and delegates identity/statistical safeguards to `scripts/real_data_cfd_contract.py`.

### Composite event identity

Every selection and pivot uses `(run, event_id)`. Duplicate `(run, event_id, stave)` rows are rejected as ambiguous rather than silently aggregated. A deterministic control uses the same `event_id=7` in two runs. The legacy identifier has one unique value; the composite key has two events and preserves pair residuals `[1.0, 1.0]`.

### Pair-only inference

The producer no longer calculates or reports `pair sigma68 / sqrt(2)`. Machine-readable output contains:

```json
{
  "single_stave_inference": {
    "authorized": false,
    "scope": "B6-B8 pair residual only"
  }
}
```

An individual-stave result requires multi-pair or external-reference deconvolution, an explicit covariance/common-mode model, propagated uncertainty and assumption sensitivity, and closure or injection-recovery validation.

### Residual visualization

Residuals are median-centered. The generated figure contains:

- a full-range panel whose range spans the complete finite residual vector;
- a core panel with explicit displayed, underflow, and overflow counts;
- q16 and q84 markers matching the `sigma68` calculation.

The synthetic tail control `[-100, -2, -1, 0, 1, 2, 100] ns` has full-range underflow/overflow `0/0` and core-view underflow/overflow `1/1`.

### Legacy bundle quarantine

The merged JSON and Markdown remain available, but are now explicitly marked `FLAWED_LEGACY_OUTPUT_QUARANTINED`. Historical metrics are retained and are not reinterpreted. The two legacy residual PNGs are machine-readably unauthorized pending regeneration.

## Validation

Executed:

```text
python -m py_compile \
  scripts/real_data_cfd_contract.py \
  scripts/real_data_cfd_timing.py \
  tests/test_real_data_cfd_production_safeguards.py \
  tools/audit/render_real_data_cfd_production_safeguard_evidence.py

PYTHONPATH=. pytest -q tests/test_real_data_cfd_production_safeguards.py

8 passed in 0.05s
```

Additional checks:

- evidence renderer returned `VALIDATED` with zero findings;
- validation JSON parsed with strict standard JSON and no NaN tokens;
- SVG parsed as XML;
- changed Python lines are at most 95 characters;
- environment: Python 3.13.5, NumPy 2.3.5, pandas 2.2.3, Matplotlib 3.10.8, pytest 9.0.2.

## Exact file identities before Git publication

| File | SHA-256 |
|---|---|
| `scripts/real_data_cfd_contract.py` | `ae1386a80389787e41620e9351c72a1d091e22bba6c8969636014f67ccd320bd` |
| `scripts/real_data_cfd_timing.py` | `83422ea881d34c777928d30b548ad553c25b0ace3a324d6204246ade9f96825e` |
| `tests/test_real_data_cfd_production_safeguards.py` | `e2306704e16ccf89a47a8f41d55902b48ff214d9e186cf8022b5015565415ef7` |
| `tools/audit/render_real_data_cfd_production_safeguard_evidence.py` | `2a0b9db4445c65a2e9b6283f89b3083b74e3f8cfa49776caa1801c1a3eec2aff` |
| `reports/real_data_cfd_timing/REPORT.md` | `79cbcb5bcb0cf480ed03bc52f7261bbd5f9d156c8d92ef78dfa722f89acef8c5` |
| `reports/real_data_cfd_timing/result.json` | `0eb33e7dd41f9a382aff3eacdf9f901de0c60f8c7301ef28cbac64c8ae1b6d02` |

## Direct-main sequence

- `af20aef19fac1d8a6ad99932e9b06fcd8cdee5a4` — task claim
- `609b3450888d508e14c9272deb8138f5ed233efd` — composite-key/pair-only contract
- `b9e874a7ad2ca59a3f9199c46b12de420724c2f3` — producer remediation
- `b3d6ad7791f96fa6fd74e408dbb7e5830e4e3cb2` — initial regressions
- `e2790c7227e309acef3a82d36094fdf9e089b544` — report quarantine
- `0614ae1e2f535e60df7e614348ff12e85dca6b72` — final producer safeguards
- `8e6af22c3981cd184787932852e6719cbc58fbdd` — final regressions
- `f0476141e50be1d7a26933d028316380505958f1` — machine-output quarantine
- `88114bb2d2d1110e10156c4ccc19e3f8588b6391` — evidence renderer
- `5e0a728bc8e445eb9d8a1d1e679f3044a975cd99` — validation JSON
- `2ae162b24f42bc6807d8b80ffe25079f16554f5e` — deterministic SVG renderer
- `335c2e1bc25d5f856fc525838654cc93e8f5a0e6` — visual evidence

## Scientific boundary

No ROOT file was available in this execution environment and no beam event was reprocessed. The legacy event count, pair width, bootstrap interval, tail fraction, pulse-shape summaries, and figures are not revalidated by this remediation. A clean production rerun must retain immutable ROOT paths, byte counts, SHA-256 digests, producer commit, exact command, environment, event-key closure, regenerated artifacts, and independent diagnostic review.
