# P01b Artifact Retrieval Note

Use this worker-local non-git path for the P01b full-data latent release:

```text
/home/billy/.tb-workers/testbeam-laptop-2/artifacts/p01b_full_data_embedding_artifact/1781005204.1292.46e43fb0/
```

Files:

- `p01b_embedding_latents.npz`
  - sha256: `9dcffdb123a8c091781771ba9f1c6667a65af91cfabbfb64328427dfd7f865be`
  - rows: `640737`
  - keys: `run`, `event_index`, `stave_index`
  - values: `amplitude_adc`, `z`
  - `z`: `float32`, shape `640737 x 4`
- `p01b_autoencoder_state.pt`
  - sha256: `20ca87b4df2a1d31ef99130423101772f6f293fe5fe0e0af3c859038d9d082d1`

Join downstream tables on `(run, event_index, stave_index)`. The
`event_index` is the zero-based entry ordinal within each raw
`hrdb_run_NNNN.root` file.

The upstream key hash from `p01b_embedding_metadata.json` verifies:

```text
605aa0fb0161573bf4afd95df232307823a4e7fd50a580455b0d53ee81121193
```

The canonical `/home/billy/ccb-data` tree was mounted read-only in this worker,
so the artifact was placed under the writable worktree mount while remaining
outside git tracking.
