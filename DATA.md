# Data manifest

The raw data is **not in git** (it is ~6.4 GB compressed). This file is the single source of
truth for where it lives and what it contains.

## Canonical locations

| Copy | Path | Status |
|---|---|---|
| Local raw ROOT mount (worker-visible canonical) | `/home/billy/ccb-data/data/extracted/root/root/` | current canonical path for direct `h101/HRDv` audits |
| Local data root alias | `data/extracted/` | gitignored symlink or directory alias to `/home/billy/ccb-data/data/extracted/` |
| Legacy local raw ROOT path | `/home/billy/ccb-data/extracted/root/root/` | legacy reference; do not hard-code in new studies |
| Local (laptop `billy`) | `/home/billy/Desktop/test_beam/data/` | older working copy; gitignored |
| LUNARC (canonical archive) | `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam-data/` | **NOT YET POPULATED** — intended primary archive for the fleet |

> **Status (DATA-008, 2026-07-23):** the canonical LUNARC archive is not yet
> populated. The historical path on the fs9 tier does not exist either. Do not
> invent data here: until the store is rsynced in, every worker must derive
> inputs from its local working copy and record the source path + sha256 in the
> run manifest. The intended archive layout (to be created on population):

```
/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam-data/
├── raw/                       # original archives (immutable); sha256 below
│   ├── CCB Data.zip
│   ├── CCB Data/{sorted-a.zip, sorted-b.zip, root.zip}
│   └── root.zip.tar
└── extracted/                 # 6.1 GB (see "Extracted layout" below)
    ├── root/root/             # hrda_run_NNNN.root / hrdb_run_NNNN.root
    ├── sorted-a/
    └── sorted-b/
```

### Raw ROOT path resolution

New raw-ROOT consumers should call
`ccb_mc_validation.raw_root_paths.resolve_raw_root_dir(repo_root=...)` or run:

```bash
python -m ccb_mc_validation raw-root-probe --repo-root .
```

Resolution order is:

1. `CCB_RAW_ROOT_DIR`, if set.
2. `/home/billy/ccb-data/data/extracted/root/root` (worker-visible canonical mount).
3. `data/extracted/root/root` relative to the repository.
4. `/home/billy/ccb-data/extracted/root/root` (legacy absolute alias).

The probe records the first usable directory with B-stack `hrdb_run_*.root`
files, plus existence and file-count evidence for each candidate it inspected.
Historical reports may mention the legacy path; new reports should record the
resolved path from the probe output.

### Hash-verification procedure

When the archive is populated, every worker MUST verify byte-identical inputs
using the sha256 manifest recorded by Study S00 in
`reports/S00_data_integrity_pipeline_reproduction/input_sha256.csv` (raw-archive
digests listed under "Integrity" below). Verify with:

```bash
sha256sum -c reports/S00_data_integrity_pipeline_reproduction/input_sha256.csv
```

A mismatch is a hard stop: do not run downstream studies until the archive and
the manifest agree. The PulseTable itself is versioned via the
`schema_version` field mandated by `docs/contracts/PULSE_TABLE_CONTRACT.md`.

## Archive contents

`CCB Data.zip` (6.37 GB) contains three inner archives:

| Inner archive | Size | Expected contents |
|---|---|---|
| `sorted-a.zip` | 2.68 GB | A-stack sorted data |
| `sorted-b.zip` | 2.87 GB | B-stack sorted data |
| `root.zip` | 810 MB | reduced HRD ROOT files (the inputs the reports were built from) |

`root.zip.tar` (543 MB) → `root.zip.gz` → a separate copy of the ROOT bundle (provenance:
nested re-compression; verify it matches `CCB Data/root.zip` before trusting either).

### Extracted layout (verified)

```
data/
├── raw/                       # original archives (immutable)
│   ├── CCB Data.zip
│   ├── root.zip.tar
│   └── CCB Data/{sorted-a.zip, sorted-b.zip, root.zip}
└── extracted/                 # 6.1 GB
    ├── root/root/             # 110 raw per-run ROOT files:
    │                          #   hrda_run_NNNN.root  (57 files, A-stack)
    │                          #   hrdb_run_NNNN.root  (53 files, B-stack)
    ├── sorted-a/              # hrda_run_NNNN-sorted.root  (A-stack, sorted)
    └── sorted-b/              # hrdb_run_NNNN-sorted.root  (B-stack, sorted)
                               #   ← the B-stack reports are built from these
```

Run numbers span 0012–0065. The report run-splits: Sample I = runs 31–57 (calib 31–42,
analysis 44–57; run 43 removed, run 38 absent for A-stack), Sample II = runs 58–65 (calib 64).

### Environment (laptop `billy`)

Python 3.7.6 (anaconda base): `uproot 5.0.9`, `numpy 1.21.6`, `pandas 1.3.4`,
`scikit-learn 1.0.1`, `torch 1.13.1+cu117` (CUDA available, RTX A3000 6 GB).
Heavier deep-learning training should run on LUNARC GPU nodes with a newer env.

## Reduced tables

The reports are built from a **selected-pulse table** of **640,737 B-stave pulse records**
(cut: baseline-subtracted amplitude A > 1000 ADC), produced by:
- `scripts/01_build_pulse_table_from_root.py` — ROOT → pulse table
- `scripts/02_make_report_plots.py` — table → figures

Reproducing those scripts and confirming the 640,737 count is **Study S00** (see
`studies/STUDIES.md`).

## Integrity

Study S00 recorded the full checksum manifest for the raw archives and the B-stack ROOT inputs
used by the reproduction gate in
`reports/S00_data_integrity_pipeline_reproduction/input_sha256.csv`.

| File | sha256 |
|---|---|
| `data/raw/CCB Data.zip` | `01365d81479efbfc6fe4f975ee460be1db554ae21891ec7fa594ed8906e009eb` |
| `data/raw/CCB Data/root.zip` | `19ba847cfbeb46d2944cf8d5c304afb52da6fcad991d1d402a6fd3e9a432efc1` |
| `data/raw/CCB Data/sorted-a.zip` | `5504642819482198bc7f2cc4198fc91a4f7bcfdc538304c8759c090cf7578e7c` |
| `data/raw/CCB Data/sorted-b.zip` | `f77835459bb1d797b8da74e6ac2fc88eab2402dd84b29965dc4f1dadcee1db94` |
| `data/raw/root.zip.tar` | `5fdfa62223a4219c61d2bf15dd5480bcb144435f80f546f807452b298d019b68` |
