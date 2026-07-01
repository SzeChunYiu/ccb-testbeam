# Results and figures

## Artifact metric table

| Study | Status | Support | Headline artifact metric |
|---|---:|---:|---|
| MV1 | PRODUCTION | 1000000 | AUC = 0.997641986278 |
| MV2 | PRODUCTION | 1000000 | proton 68% energy residual = 0.0365311094732 |
| MV3 | PRODUCTION | 1000000 | Sample-I support = 64762 |

## Figure catalog excerpt

| Figure | Title | PNG | SVG | Data sidecar |
|---|---|---|---|---|
| SUMMARY-F001 | Study support overview | `figures/summary/study_support.png` | `figures/summary/study_support.svg` | `reports/mc_validation/summary/metrics_table.csv` |
| SUMMARY-F002 | Selected validated metrics | `figures/summary/selected_metrics.png` | `figures/summary/selected_metrics.svg` | `reports/mc_validation/summary/metrics_table.csv` |

## Supported claims

- `CLAIM-ARTIFACT-VALIDATION`: The selected run has internally consistent frozen MV1-MV3/MV9 artifacts.
- `CLAIM-MV1-SUMMARY`: MV1 has a frozen artifact-summary metric (hgb_auc=0.997641986278) for run 20260625T064500Z_full_input_artifacted.
- `CLAIM-MV2-SUMMARY`: MV2 has a frozen artifact-summary metric (proton_ekin_recon_res68=0.0365311094732) for run 20260625T064500Z_full_input_artifacted.
- `CLAIM-MV3-SUMMARY`: MV3 has a frozen artifact-summary metric (n_sample_I=64762) for run 20260625T064500Z_full_input_artifacted.
