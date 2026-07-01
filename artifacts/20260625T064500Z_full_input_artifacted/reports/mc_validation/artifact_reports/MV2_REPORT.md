# MV2 artifact report

- **Status:** `PRODUCTION`
- **Run ID:** `20260625T064500Z_full_input_artifacted`
- **Scope:** `artifact-summary`
- **n tracks:** `1000000`
- **Key metric:** `proton_ekin_recon_res68=0.0365311094732`

## Artifact-backed metrics

```json
{
  "censored_range_note": "Tracks with stop_layer==7 excluded from ekin regression (range censored at instrument boundary).",
  "deuteron_ekin_mean_MeV": 8.434812395837786e-05,
  "deuteron_ekin_recon_res68": 0.13292951136118858,
  "deuteron_n_censored_excluded": 372,
  "deuteron_stoplayer_vs_ekin": {
    "0": {
      "mean_edep_tot_MeV": 53.634602702793515,
      "mean_ekin_MeV": 6.607838958673756e-05,
      "mean_tracklen_mm": 110.17921520322952,
      "n": 14327
    },
    "1": {
      "mean_edep_tot_MeV": 101.43909150654027,
      "mean_ekin_MeV": 7.505260275724434e-05,
      "mean_tracklen_mm": 109.7429370616107,
      "n": 68267
    },
    "2": {
      "mean_edep_tot_MeV": 131.84764118507354,
      "mean_ekin_MeV": 8.832233702314526e-05,
      "mean_tracklen_mm": 110.14149597837158,
      "n": 16831
    },
    "3": {
      "mean_edep_tot_MeV": 134.81142615855518,
      "mean_ekin_MeV": 0.00011031347587953121,
      "mean_tracklen_mm": 110.8224791657808,
      "n": 35230
    },
    "4": {
      "mean_edep_tot_MeV": 103.50744305737172,
      "mean_ekin_MeV": 7.885197876163932e-05,
      "mean_tracklen_mm": 110.88404003989935,
      "n": 765
    },
    "5": {
      "mean_edep_tot_MeV": 129.78122960871963,
      "mean_ekin_MeV": 6.018772469690152e-05,
      "mean_tracklen_mm": 111.22517751994523,
      "n": 952
    },
    "6": {
      "mean_edep_tot_MeV": 163.7293708059013,
      "mean_ekin_MeV": 3.945907134857259e-05,
      "mean_tracklen_mm": 111.60319445348298,
      "n": 4303
    },
    "7": {
      "mean_edep_tot_MeV": 91.83408529064536,
      "mean_ekin_MeV": 8.677809156234195e-05,
      "mean_tracklen_mm": 110.6933623461683,
      "n": 372
    }
  },
  "proton_ekin_mean_MeV": 0.00013332355730454152,
  "proton_ekin_recon_res68": 0.036531109473233174,
  "proton_n_censored_excluded": 29734,
  "proton_stoplayer_vs_ekin": {
    "0": {
      "mean_edep_tot_MeV": 24.86920971681107,
      "mean_ekin_MeV": 9.692364081346271e-05,
      "mean_tracklen_mm": 104.72355023804604,
      "n": 3845
    },
    "1": {
      "mean_edep_tot_MeV": 48.60254876043409,
      "mean_ekin_MeV": 9.830924857009364e-05,
      "mean_tracklen_mm": 106.55845538874465,
      "n": 5392
    },
    "2": {
      "mean_edep_tot_MeV": 62.52440188179504,
      "mean_ekin_MeV": 0.00012605074351343886,
      "mean_tracklen_mm": 110.31311696566947,
      "n": 4476
    },
    "3": {
      "mean_edep_tot_MeV": 75.15308826720276,
      "mean_ekin_MeV": 0.00013290393564356748,
      "mean_tracklen_mm": 110.35672896993756,
      "n": 4624
    },
    "4": {
      "mean_edep_tot_MeV": 88.92548046937455,
      "mean_ekin_MeV": 0.00014169145566501548,
      "mean_tracklen_mm": 111.06459602035672,
      "n": 4685
    },
    "5": {
      "mean_edep_tot_MeV": 123.17903938900159,
      "mean_ekin_MeV": 0.00013253975286783645,
      "mean_tracklen_mm": 111.27639214661556,
      "n": 20246
    },
    "6": {
      "mean_edep_tot_MeV": 133.8626911611151,
      "mean_ekin_MeV": 0.00013908075553179655,
      "mean_tracklen_mm": 110.76625120295097,
      "n": 27547
    },
    "7": {
      "mean_edep_tot_MeV": 128.61664362839156,
      "mean_ekin_MeV": 0.00016044704077844283,
      "mean_tracklen_mm": 111.59990455868932,
      "n": 29734
    }
  }
}
```

## Cutflow/support

```json
{
  "n_deuteron_uncensored": 139074,
  "n_proton_uncensored": 69455,
  "n_tracks": 1000000
}
```

## Guardrail

This report summarizes validated frozen artifacts only. It does not add uncertainty/systematic arrays or final thesis/release conclusions.
