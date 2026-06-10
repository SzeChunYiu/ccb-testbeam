# P01d: promote P01b artifact to canonical ccb-data archive

**Ticket:** `1781016189.1003.2607526c`

## Raw ROOT reproduction

The first audit step rescanned the raw B-stack ROOT files before artifact promotion, using the P01b/S00 gate: B2/B4/B6/B8 channels, median samples 0-3 baseline, and `A > 1000` ADC.

| quantity | expected | reproduced | pass |
|---|---:|---:|---|
| selected B-stave pulses | 640737 | 640737 | yes |

## Artifact hash preservation

| file | source bytes | source sha256 | matches P01c |
|---|---:|---|---|
| `p01b_embedding_latents.npz` | 11923919 | `9dcffdb123a8c091781771ba9f1c6667a65af91cfabbfb64328427dfd7f865be` | yes |
| `p01b_autoencoder_state.pt` | 13715 | `20ca87b4df2a1d31ef99130423101772f6f293fe5fe0e0af3c859038d9d082d1` | yes |

## Canonical promotion

Promotion is blocked in this worker: no requested canonical data path is writable.

| target | status | error |
|---|---|---|
| `/home/billy/ccb-data/artifacts/p01b_full_data_embedding_artifact/1781005204.1292.46e43fb0` | failed | `[Errno 30] Read-only file system: '/home/billy/ccb-data/artifacts'` |
| `/projects/hep/fs9/shared/nnbar/billy/ccb-testbeam/data/artifacts/p01b_full_data_embedding_artifact/1781005204.1292.46e43fb0` | failed | `[Errno 30] Read-only file system: '/projects'` |

The preserved worker-local retrieval path from P01c remains:

`/home/billy/.tb-workers/testbeam-laptop-2/artifacts/p01b_full_data_embedding_artifact/1781005204.1292.46e43fb0`

`P01D_ARTIFACT_INDEX.md` records the current retrieval path, expected hashes, and blocked canonical target.

## Notes

- `input_sha256.csv` records all raw ROOT inputs scanned plus the two source artifact hashes.
- `manifest.json` records the copy attempts and generated files.
- The upstream P01b method comparison remains PCA-4 held-out MSE `0.013372` versus masked-denoising AE-4 MSE `0.014277`; P01d performs artifact promotion/audit only and does not refit models.
