# MV3 artifact report

- **Status:** `PRODUCTION`
- **Run ID:** `20260627T180424Z_2516606_mv4_timing_final`
- **Scope:** `artifact-summary`
- **n tracks:** `100000`
- **Key metric:** `n_sample_I=6450`

## Artifact-backed metrics

```json
{
  "layer_occupancy_sample_I": [
    1.0,
    0.978139534883721,
    0.41767441860465115,
    0.23224806201550388,
    0.08759689922480621,
    0.08217054263565891,
    0.07193798449612403,
    0.0021705426356589145
  ],
  "layer_occupancy_sample_II": [
    1.0,
    0.9086583646616542,
    0.7031837406015038,
    0.6504934210526315,
    0.48179041353383456,
    0.45247885338345867,
    0.3341752819548872,
    0.17440084586466165
  ],
  "layer_to_stave_mapping": {
    "0": "B2",
    "1": "B2",
    "2": "B4",
    "3": "B4",
    "4": "B6",
    "5": "B6",
    "6": "B8",
    "7": "B8"
  },
  "mapping_hypothesis_scores": {},
  "truth_stave_counts": {
    "B2": 85158.0,
    "B4": 6057.0,
    "B6": 2624.0,
    "B8": 6161.0
  }
}
```

## Cutflow/support

```json
{
  "n_sample_I": 6450,
  "n_sample_II": 17024,
  "n_tracks": 100000
}
```

## Guardrail

This report summarizes validated frozen artifacts only. It does not add uncertainty/systematic arrays or final thesis/release conclusions.
