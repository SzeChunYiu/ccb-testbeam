# Results and figures

## Artifact metric table

| Study | Status | Support | Headline artifact metric |
|---|---:|---:|---|
| MV1 | PRODUCTION | 100000 | AUC = 0.997271496084 |
| MV2 | PRODUCTION | 100000 | proton 68% energy residual = 0.0153808233017 |
| MV3 | PRODUCTION | 100000 | Sample-I support = 6450 |

## Figure catalog excerpt

| Figure | Title | PNG | SVG | Data sidecar |
|---|---|---|---|---|
| SUMMARY-F001 | Study support overview | `figures/summary/study_support.png` | `figures/summary/study_support.svg` | `reports/mc_validation/summary/metrics_table.csv` |
| SUMMARY-F002 | Selected validated metrics | `figures/summary/selected_metrics.png` | `figures/summary/selected_metrics.svg` | `reports/mc_validation/summary/metrics_table.csv` |

## Supported claims

- `CLAIM-ARTIFACT-VALIDATION`: The selected run has internally consistent frozen MV1-MV4/MV9 artifacts.
- `CLAIM-MV1-SUMMARY`: MV1 has a frozen artifact-summary metric (hgb_auc=0.997271496084) for run 20260627T180424Z_2516606_mv4_timing_final.
- `CLAIM-MV2-SUMMARY`: MV2 has a frozen artifact-summary metric (proton_ekin_recon_res68=0.0153808233017) for run 20260627T180424Z_2516606_mv4_timing_final.
- `CLAIM-MV3-SUMMARY`: MV3 has a frozen artifact-summary metric (n_sample_I=6450) for run 20260627T180424Z_2516606_mv4_timing_final.
