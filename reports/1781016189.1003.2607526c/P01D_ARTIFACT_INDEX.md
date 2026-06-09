# P01d Artifact Index

P01b released a reusable four-dimensional B-stack waveform embedding artifact for downstream
P02-P08 studies. The two binary artifacts are not stored in git.

| Artifact | Current retrieval path | sha256 | Notes |
|---|---|---|---|
| `p01b_embedding_latents.npz` | `/home/billy/.tb-workers/testbeam-laptop-2/artifacts/p01b_full_data_embedding_artifact/1781005204.1292.46e43fb0/p01b_embedding_latents.npz` | `9dcffdb123a8c091781771ba9f1c6667a65af91cfabbfb64328427dfd7f865be` | 640,737 rows; `z` shape `640737 x 4`; key hash `605aa0fb0161573bf4afd95df232307823a4e7fd50a580455b0d53ee81121193` |
| `p01b_autoencoder_state.pt` | `/home/billy/.tb-workers/testbeam-laptop-2/artifacts/p01b_full_data_embedding_artifact/1781005204.1292.46e43fb0/p01b_autoencoder_state.pt` | `20ca87b4df2a1d31ef99130423101772f6f293fe5fe0e0af3c859038d9d082d1` | Release AE state for audit/re-encoding checks |

P01d attempted to promote these files to:

`/home/billy/ccb-data/artifacts/p01b_full_data_embedding_artifact/1781005204.1292.46e43fb0`

That canonical copy is blocked in this worker because `/home/billy/ccb-data` is mounted
read-only (`ro,nosuid,nodev,relatime,errors=remount-ro`) and the LUNARC `/projects/...`
path is not present. When either canonical path is writable, copy the two files above and
preserve the listed sha256 values.
