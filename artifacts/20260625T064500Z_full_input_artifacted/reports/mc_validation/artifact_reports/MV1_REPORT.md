# MV1 artifact report

- **Status:** `PRODUCTION`
- **Run ID:** `20260625T064500Z_full_input_artifacted`
- **Scope:** `artifact-summary`
- **n tracks:** `1000000`
- **Key metric:** `hgb_auc=0.997641986278`

## Artifact-backed metrics

```json
{
  "cut_edep_l0_thr_MeV": 23.391984775109016,
  "cut_efficiency": 0.8204428311130333,
  "cut_purity": 0.9579711584628885,
  "deltaE_E_medians": {
    "deuteron": {
      "edep_l0": 53.0748501785012,
      "edep_l1": 29.207290667434783,
      "edep_tot": 123.04164629352441,
      "stop_layer": 1.0
    },
    "proton": {
      "edep_l0": 12.195985352475857,
      "edep_l1": 13.046976199794067,
      "edep_tot": 127.49393913443596,
      "stop_layer": 6.0
    }
  },
  "hgb_auc": 0.997641986277693,
  "hgb_purity_at_90eff": 0.9954311373484896,
  "logreg_auc": 0.9764543474193328,
  "logreg_purity_at_90eff": 0.9606945181590719,
  "n_deuteron": 141047,
  "n_proton": 100549,
  "n_tracks": 1000000,
  "split": "legacy_parity"
}
```

## Cutflow/support

```json
{
  "n_binary_pid": 241596,
  "n_deuteron": 141047,
  "n_proton": 100549,
  "n_tracks": 1000000
}
```

## Guardrail

This report summarizes validated frozen artifacts only. It does not add uncertainty/systematic arrays or final thesis/release conclusions.
