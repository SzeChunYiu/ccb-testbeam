# Data provenance for the publication

Raw beam ROOT data are **not copied into the publication tree**.

Known beam source:

`/projects/hep/fs10/shared/nnbar/ccb_data/hrd/root/hrdb_run_*.root`

The publication build must consume only result/source tables whose manifests bind raw/product input hashes, waveform schema, event keys, producer commit/hash and selection contract.

Historical single-stave optical calibration files under `/projects/hep/fs10/shared/nnbar/billy/ccb_calib_grid/` are currently superseded for nominal publication use by #1303.
