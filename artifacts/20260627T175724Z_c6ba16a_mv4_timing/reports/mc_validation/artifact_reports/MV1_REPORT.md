# MV1 artifact report

- **Status:** `PRODUCTION`
- **Run ID:** `20260627T175724Z_c6ba16a_mv4_timing`
- **Scope:** `artifact-summary`
- **n tracks:** `100000`
- **Key metric:** `hgb_auc=0.99728749681`

## Artifact-backed metrics

```json
{
  "cut_edep_l0_thr_MeV": 23.483633636797858,
  "cut_efficiency": 0.817494292237443,
  "cut_purity": 0.9570664884731039,
  "deltaE_E_medians": {
    "deuteron": {
      "edep_l0": 53.11532825022807,
      "edep_l1": 29.25954649717863,
      "edep_tot": 122.94344416917055,
      "stop_layer": 1.0
    },
    "proton": {
      "edep_l0": 12.205358136137388,
      "edep_l1": 13.053462853167208,
      "edep_tot": 127.32770934912904,
      "stop_layer": 6.0
    }
  },
  "hgb_auc": 0.9972874968095413,
  "hgb_purity_at_90eff": 0.9954128440366973,
  "logreg_auc": 0.9776122159551996,
  "logreg_purity_at_90eff": 0.9620272546317562,
  "n_deuteron": 14016,
  "n_proton": 9929,
  "n_tracks": 100000,
  "split": "legacy_parity"
}
```

## Cutflow/support

```json
{
  "n_binary_pid": 23945,
  "n_deuteron": 14016,
  "n_proton": 9929,
  "n_tracks": 100000
}
```

## Guardrail

This report summarizes validated frozen artifacts only. It does not add uncertainty/systematic arrays or final thesis/release conclusions.
