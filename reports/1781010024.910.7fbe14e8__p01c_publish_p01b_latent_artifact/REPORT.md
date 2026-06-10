# P01c: publish P01b latent artifact outside git

**Ticket:** 1781010024.910.7fbe14e8

## Raw-data check

Before copying the artifact, I independently recounted the P01b selected B-stack
pulses from the raw ROOT files in `data/root/root` using the P01b cut
(`A > 1000 ADC`, staves B2/B4/B6/B8). The result reproduced the P01b release
row count exactly:

| quantity | expected | reproduced | pass |
|---|---:|---:|---|
| selected B-stave pulses | 640737 | 640737 | yes |

The upstream P01b benchmark remains the relevant method comparison: traditional
PCA-4 held-out reconstruction MSE `0.013372` (95% CI `0.009224-0.016965`) versus
ML masked-denoising AE-4 `0.014277` (`0.009938-0.017722`), split by run with
held-out runs 42, 57, 64, and 65. Leakage checks from P01b are preserved in the
source report; the label-shuffle control falls to balanced accuracy `0.239`.

## Published location

I copied the two binary release artifacts to the worker-local non-git artifact
store:

`/home/billy/.tb-workers/testbeam-laptop-2/artifacts/p01b_full_data_embedding_artifact/1781005204.1292.46e43fb0/`

This path is inside the writable worker mount but the binaries are not tracked
by git (`*.npz` and `*.pt` are ignored). Attempts to create
`/home/billy/ccb-data/artifacts` and `/home/billy/ccb-testbeam-artifacts` failed
because those paths are read-only in this worker.

| file | bytes | sha256 | verification |
|---|---:|---|---|
| `p01b_embedding_latents.npz` | 11923919 | `9dcffdb123a8c091781771ba9f1c6667a65af91cfabbfb64328427dfd7f865be` | matches P01b metadata |
| `p01b_autoencoder_state.pt` | 13715 | `20ca87b4df2a1d31ef99130423101772f6f293fe5fe0e0af3c859038d9d082d1` | copied source hash matches destination |

The latent table contains keys `run`, `event_index`, `stave_index`,
`amplitude_adc`, and `z`; `z` has shape `640737 x 4` and dtype `float32`.
The upstream composite key hash also verifies:
`605aa0fb0161573bf4afd95df232307823a4e7fd50a580455b0d53ee81121193`.

## Retrieval

Downstream P02-P08 workers should load the `.npz` directly from the path above
and join on `(run, event_index, stave_index)`. The release AE state is only for
auditing or re-encoding consistency checks; downstream feature studies should
use the frozen `z` columns rather than refitting this release model.
