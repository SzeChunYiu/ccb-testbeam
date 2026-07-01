# MV2 artifact report

- **Status:** `PRODUCTION`
- **Run ID:** `20260627T112940Z_719788b_wrapper_release`
- **Scope:** `artifact-summary`
- **n tracks:** `100000`
- **Key metric:** `proton_ekin_recon_res68=0.0153808233017`

## Artifact-backed metrics

```json
{
  "censored_range_note": "Tracks with stop_layer==7 excluded from ekin regression (range censored at instrument boundary).",
  "deuteron_ekin_mean_MeV": 8.391776449568594e-05,
  "deuteron_ekin_recon_res68": 0.03677415671940314,
  "deuteron_n_censored_excluded": 41,
  "deuteron_stoplayer_vs_ekin": {
    "0": {
      "mean_edep_tot_MeV": 53.325764726548584,
      "mean_ekin_MeV": 6.488409465542544e-05,
      "mean_tracklen_mm": 109.86863302303702,
      "n": 1435
    },
    "1": {
      "mean_edep_tot_MeV": 101.57142962493415,
      "mean_ekin_MeV": 7.505787781078171e-05,
      "mean_tracklen_mm": 109.7452447144331,
      "n": 6758
    },
    "2": {
      "mean_edep_tot_MeV": 132.6428588926043,
      "mean_ekin_MeV": 8.825784906395434e-05,
      "mean_tracklen_mm": 110.2211959689144,
      "n": 1729
    },
    "3": {
      "mean_edep_tot_MeV": 134.4305318103906,
      "mean_ekin_MeV": 0.00011035937888325466,
      "mean_tracklen_mm": 110.82084162966582,
      "n": 3410
    },
    "4": {
      "mean_edep_tot_MeV": 104.59147374237219,
      "mean_ekin_MeV": 7.961181158052195e-05,
      "mean_tracklen_mm": 110.86247361207406,
      "n": 73
    },
    "5": {
      "mean_edep_tot_MeV": 127.54290467480811,
      "mean_ekin_MeV": 6.431499547594432e-05,
      "mean_tracklen_mm": 111.13550338749896,
      "n": 99
    },
    "6": {
      "mean_edep_tot_MeV": 165.1760946179713,
      "mean_ekin_MeV": 3.7944697688175877e-05,
      "mean_tracklen_mm": 111.60774268448581,
      "n": 471
    },
    "7": {
      "mean_edep_tot_MeV": 93.89859115930182,
      "mean_ekin_MeV": 8.387728649256865e-05,
      "mean_tracklen_mm": 110.88964219290771,
      "n": 41
    }
  },
  "proton_ekin_mean_MeV": 0.0001329271985133293,
  "proton_ekin_recon_res68": 0.015380823301696338,
  "proton_n_censored_excluded": 2943,
  "proton_stoplayer_vs_ekin": {
    "0": {
      "mean_edep_tot_MeV": 23.722606134037473,
      "mean_ekin_MeV": 9.733029285067479e-05,
      "mean_tracklen_mm": 107.3659262958612,
      "n": 387
    },
    "1": {
      "mean_edep_tot_MeV": 50.076982897086275,
      "mean_ekin_MeV": 9.771409860204037e-05,
      "mean_tracklen_mm": 105.67630396476918,
      "n": 564
    },
    "2": {
      "mean_edep_tot_MeV": 62.681251136694954,
      "mean_ekin_MeV": 0.00012515615892937524,
      "mean_tracklen_mm": 110.40229481137989,
      "n": 453
    },
    "3": {
      "mean_edep_tot_MeV": 75.23038510914097,
      "mean_ekin_MeV": 0.00013559235310213534,
      "mean_tracklen_mm": 110.12957323632178,
      "n": 443
    },
    "4": {
      "mean_edep_tot_MeV": 89.33674458863939,
      "mean_ekin_MeV": 0.00014154125817408494,
      "mean_tracklen_mm": 111.21261067587398,
      "n": 461
    },
    "5": {
      "mean_edep_tot_MeV": 123.5597461174923,
      "mean_ekin_MeV": 0.000132089776548346,
      "mean_tracklen_mm": 111.3051458192407,
      "n": 1979
    },
    "6": {
      "mean_edep_tot_MeV": 133.97382950909255,
      "mean_ekin_MeV": 0.00013909515088290762,
      "mean_tracklen_mm": 110.79981656358326,
      "n": 2699
    },
    "7": {
      "mean_edep_tot_MeV": 128.53331255781453,
      "mean_ekin_MeV": 0.00016048505174072182,
      "mean_tracklen_mm": 111.62889833991039,
      "n": 2943
    }
  }
}
```

## Cutflow/support

```json
{
  "n_deuteron_uncensored": 13815,
  "n_proton_uncensored": 6858,
  "n_tracks": 100000
}
```

## Guardrail

This report summarizes validated frozen artifacts only. It does not add uncertainty/systematic arrays or final thesis/release conclusions.
