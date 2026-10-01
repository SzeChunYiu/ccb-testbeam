# ML timing tutorial notebook handoff

## Deliverable

A student-facing Jupyter notebook has been built and execution-validated for the combined classical + machine-learning timing programme. The notebook title is:

`CCB_Timing_and_ML_Results_Tutorial.ipynb`

The portable notebook embeds the numerical study tables, so it can run outside the repository. It is pinned to repository main commit:

`cec9edc28257e0699c70c17fa9b2e8d806a3d42a`

## Scientific scope

The notebook teaches the following chain:

1. pair timing vs absolute timing and common-mode cancellation;
2. the historical ~0.1 ns B4-B6 central residual and its RMS/fit-quality contradiction;
3. S02 traditional CFD/template/Ridge baselines;
4. P03a direct waveform MLP and its negative result versus analytic timewalk;
5. P03b leave-one-run-out stability;
6. P03c MLP/CNN residual learning after analytic timing;
7. S03k rich waveform+amplitude+shape+stave models and the HGB 1.107 ns historical winner;
8. S03l direct substitution and the waveform strata where HGB gains are largest;
9. S03m failure of the simple high-risk-only gating policy;
10. leakage controls, target shuffling, run-block splits, feature-group ablations, and current claim authorization.

## Key historical benchmark values embedded

### P03a run-65

- analytic timewalk: 1.49464 ns
- S02 Ridge-CFD20: 1.84611 ns
- direct waveform MLP: 1.92723 ns
- template phase: 2.88915 ns
- CFD20: 2.99339 ns

The direct waveform MLP does not beat the strong transparent comparator.

### P03b seven-run LORO means

- analytic timewalk: ~1.496 ns
- waveform MLP: ~1.805 ns
- Ridge-CFD20: ~1.905 ns

Run 61 is the principal stress case where the analytic model broadens to ~2.13 ns while the waveform MLP is ~2.11 ns.

### P03c run-65 residual learning

- MLP after analytic: 1.44836 ns
- analytic: 1.49464 ns
- CNN after analytic: 1.49705 ns

The MLP point-estimate improvement is small and not a robust discovery; the CNN adds no useful gain.

### S03k seven-run LORO primary gate

- HGB waveform+amp+shape+stave: 1.10742 ns, CI [1.075, 1.159]
- MLP waveform+amp+shape+stave: 1.16210 ns, CI [1.106, 1.235]
- Ridge waveform+stave: 1.24442 ns, CI [1.173, 1.322]
- feature-gated model: 1.25349 ns, CI [1.213, 1.308]
- 1D CNN waveform+amp+shape+stave: 1.26387 ns, CI [1.212, 1.343]
- analytic timewalk: 1.55109 ns, CI [1.364, 1.936]

The historical winner is HGB, not a neural network.

### S03m policy closure

- analytic everywhere: 1.55109 ns
- HGB everywhere: 1.10742 ns
- HGB only in frozen high-risk atoms: 1.61562 ns

The simple hand-built risk gate does not reproduce the global HGB gain.

## Current authorization boundary

Do not promote the historical ML results to a current beam-data single-stave timing claim. `docs/contracts/PUBLIC_CLAIM_AUTHORITY.json` withholds CL-002, and the waveform lineage audit treats the located LUNARC 8x16 source and historical 8x18 lane as distinct schemas unless exact reversible lineage is proven.

The notebook therefore labels the 1.107 ns HGB result and the historical ~0.1 ns core as algorithmic/historical timing diagnostics, not detector-resolution measurements.

## Source reports

- `reports/1780997954.15157.07ef03cf__s02_timing_pickoff/REPORT.md`
- `reports/1781004956.603.7dce65be__p03a_18_sample_mlp_timing/REPORT.md`
- `reports/1781009029.1279.4d6e17f9/REPORT.md`
- `reports/1781009029.1288.7e78286e/REPORT.md`
- `reports/1781048240.758.327a70d2__s03k_analytic_comparator_reuse_gate/REPORT.md`
- `reports/1781147391.1146.677159b3__s03l_direct_downstream_substitution_audit/REPORT.md`
- `reports/1781152686.1536.37412fee__s03m_downstream_consumer_closure/REPORT.md`
- `docs/contracts/PUBLIC_CLAIM_AUTHORITY.json`
- `tools/audit/audit_hrd_waveform_lineage_993.py`

## Validation

The generated notebook contains 64 cells and was executed end-to-end with `nbclient` under Python 3.11 with no cell execution errors. An HTML export was also produced for inspection. `ipywidgets` is optional; when absent, the interactive explorer cells fall back to deterministic static plots.

## Next repository action

A follow-on session should either:

1. copy the validated notebook JSON into this folder as `CCB_Timing_and_ML_Results_Tutorial.ipynb`, or
2. add a repository-native notebook generator that reads the report tables directly and checks their source hashes before constructing the notebook.

Prefer option 2 for long-term maintenance so study-number changes cannot silently leave stale embedded tables.
