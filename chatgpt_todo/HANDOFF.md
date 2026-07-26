# Latest Handoff

## Session

- **Task ID:** `AUD-TIMING-003-R1`
- **Stamp:** `2026-07-26T190253Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `be97e1a1e77de3bba6305f28802d1c876d2d1605`
- **Validated implementation/evidence/archive/active-task head:** `8ce582f25d497cb67df86a4a09f5634ca6fd5c51`
- **Destination:** authenticated sequential commits directly to `main`; no force-push, branch transport, pull-request merge, or history rewrite.
- **Push result:** GitHub contents writes returned successful commit SHAs. Post-write remote history confirmed the focused sequence through `8ce582f25d497cb67df86a4a09f5634ca6fd5c51` consecutively on `main`, with no concurrent interleaving after the PR #939 merge.
- **Acceptance:** software remediation `VALIDATED / COMPLETE`; production physics result `PAIR_ONLY_PENDING_CONTENT_ADDRESSED_RERUN`.

## Trigger and finding

PR #939 merged as `be97e1a1e77de3bba6305f28802d1c876d2d1605` after current-main audits had already demonstrated three defects in its producer:

1. multiple ROOT runs were selected and pivoted by `event_id` alone rather than `(run,event_id)`;
2. residual PNGs displayed uncentered values only inside `[-10,10] ns`, while labels used complete-vector statistics whose medians were far outside that window;
3. the B6-B8 pair `sigma68` was divided by `sqrt(2)` and published as a `0.635 ns` individual-stave estimate without validated equal variances, zero covariance, or a deconvolution law for the interquantile estimator.

The merged report/result bundle is now explicitly `FLAWED_LEGACY_OUTPUT_QUARANTINED`. Historical numbers remain visible for provenance but are unauthorized for pair or individual-stave acceptance. Existing residual PNGs are machine-readably unauthorized pending regeneration.

## Remediation

Policy: `REAL_DATA_CFD_REQUIRES_COMPOSITE_EVENT_KEYS_AND_PAIR_ONLY_INFERENCE`.

Producer v2.0.0 now:

- uses `(run,event_id)` for every selection and pivot;
- rejects duplicate `(run,event_id,stave)` rows;
- reports B6-B8 pair metrics only;
- emits `single_stave_inference.authorized=false`;
- centers residuals on their median;
- produces complete-range and core panels with q16/q84 and displayed/underflow/overflow counts;
- converts optional nonfinite fit diagnostics to JSON `null`, rejects nonfinite required metrics, uses `allow_nan=False`, and publishes JSON/Markdown atomically.

## Reproducible controls

- Same `event_id=7` in two runs: event-ID-only identity gives one value; `(run,event_id)` preserves two events and pair residuals `[1.0,1.0]`.
- Residual vector `[-100,-2,-1,0,1,2,100] ns`: median `0`; q16/q84 `-5.9200000000000035/+5.9200000000000035 ns`; full underflow/overflow `0/0`; `[-5,5] ns` core underflow/overflow `1/1`.
- Pair-only inference contract: authorization `false`; individual-stave acceptance requires multi-pair or external-reference deconvolution, explicit covariance/common-mode treatment, propagated uncertainty/sensitivity, and closure or injection recovery.

## Validation

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

- evidence JSON status `VALIDATED`, findings `[]`;
- strict JSON parse and SVG XML parse passed;
- changed Python lines are at most 95 characters;
- environment: Python 3.13.5, NumPy 2.3.5, pandas 2.2.3, Matplotlib 3.10.8, pytest 9.0.2;
- `uproot` and immutable ROOT data were unavailable; no producer execution or physics rerun is claimed.

## Files and identities

- `scripts/real_data_cfd_contract.py` — SHA-256 `ae1386a80389787e41620e9351c72a1d091e22bba6c8969636014f67ccd320bd`
- `scripts/real_data_cfd_timing.py` — SHA-256 `83422ea881d34c777928d30b548ad553c25b0ace3a324d6204246ade9f96825e`
- `tests/test_real_data_cfd_production_safeguards.py` — SHA-256 `e2306704e16ccf89a47a8f41d55902b48ff214d9e186cf8022b5015565415ef7`
- `tools/audit/render_real_data_cfd_production_safeguard_evidence.py` — SHA-256 `2a0b9db4445c65a2e9b6283f89b3083b74e3f8cfa49776caa1801c1a3eec2aff`
- `reports/real_data_cfd_timing/REPORT.md` — SHA-256 `79cbcb5bcb0cf480ed03bc52f7261bbd5f9d156c8d92ef78dfa722f89acef8c5`
- `reports/real_data_cfd_timing/result.json` — SHA-256 `0eb33e7dd41f9a382aff3eacdf9f901de0c60f8c7301ef28cbac64c8ae1b6d02`
- validation JSON — SHA-256 `cb93aa081cf08059bf551fa34943b90496e3ecf6611cd6ef15edb2ce2122e709`
- deterministic SVG — SHA-256 `059254c36e2ff42171d3cbe16683feb8a0cbd75d2da30ac629094620818800af`
- immutable record: `chatgpt_todo/archive/2026-07-26T190253Z_AUD-TIMING-003-R1_CFD_PRODUCTION_SAFEGUARDS.md`

## Direct-main sequence

- `af20aef19fac1d8a6ad99932e9b06fcd8cdee5a4` — task claim
- `609b3450888d508e14c9272deb8138f5ed233efd` — event/statistics contract
- `b9e874a7ad2ca59a3f9199c46b12de420724c2f3` — initial producer remediation
- `b3d6ad7791f96fa6fd74e408dbb7e5830e4e3cb2` — initial tests
- `e2790c7227e309acef3a82d36094fdf9e089b544` — report quarantine
- `0614ae1e2f535e60df7e614348ff12e85dca6b72` — final producer safeguards
- `8e6af22c3981cd184787932852e6719cbc58fbdd` — final tests
- `f0476141e50be1d7a26933d028316380505958f1` — result quarantine
- `88114bb2d2d1110e10156c4ccc19e3f8588b6391` — initial renderer
- `5e0a728bc8e445eb9d8a1d1e679f3044a975cd99` — validation JSON
- `2ae162b24f42bc6807d8b80ffe25079f16554f5e` — deterministic renderer
- `335c2e1bc25d5f856fc525838654cc93e8f5a0e6` — visual evidence
- `84d49de5d6f141fcc6e94e354c212902efa4d9eb` — audit report
- `0c8e02d3167ce238a18b5a7988584e7f3a0e0d64` — immutable archive
- `8ce582f25d497cb67df86a4a09f5634ca6fd5c51` — active-task completion

## Required next work

Run producer v2.0.0 against immutable LUNARC ROOT files. Record every input path, size and SHA-256, exact producer commit and command, Python/uproot/NumPy versions, composite-key cardinalities, selections, regenerated JSON/Markdown/PNG hashes, and full/core diagnostic review. Pair-level acceptance may be considered only after that rerun. Do not infer B6 or B8 individually without validated deconvolution and covariance treatment.

## Limitations

Repository-wide pytest/ruff, producer execution, ROOT hashing and processing, regeneration of the six study PNGs, complete link checking, and GitHub Actions were not run. No event count, pair width, individual-stave resolution, channel map, CFD performance, CL-002 state, or detector-performance result was accepted or changed.

`SESSION_LOG.md`, `BACKLOG.md`, `MASTER_INDEX.md`, and the long aggregate matrices were reviewed but not safely replaced. Connector reads are paged/truncated while writes replace complete files; partial reconstruction could erase append-only or concurrent provenance. The immutable archive is the append-equivalent record, and this mandatory synchronization gap is explicit rather than reported as complete.
