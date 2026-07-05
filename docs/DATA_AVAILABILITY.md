# Data Availability & FAIR plan — CCB test-beam analysis

> Scope: prepared with the `nature-data` skill (Springer Nature / Nature Portfolio data policy as the
> governing layer; FAIR + DataCite as the implementation layer). This document is a **planning
> artifact**, not a submitted statement: the analysis is research-in-progress and no data are yet in a
> public repository. Every DOI/accession below is a **placeholder to be minted before submission** —
> none are invented as if they already exist.

---

## 0. Honest current state (read first)

As of 2026-07-05 the supporting data live in **exactly two places, both access-controlled**:

- **LUNARC (canonical):** `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/` (fs10, mounted on
  compute nodes; requires a LUNARC/SNIC account and project membership).
- **Local immutable store:** `/home/billy/ccb-data/` (`raw/` + `extracted/`, ~6.1 GB extracted),
  outside git, read-only, created after the 2026-06-08 data-loss incident (`fleet/LESSONS.md`).

There is **no persistent identifier (DOI/accession), no public landing page, and no license** on any
dataset yet. Per Nature Portfolio policy this is currently a **blocking gap** for an original-research
submission. Sections 3–4 give the concrete steps to close it. The statement in Section 2 is written
to be truthful *today* (access on request) and is annotated with the wording to switch to once the
Zenodo/HEPData deposits exist.

---

## 1. Dataset inventory & access-route classification

| # | Dataset | Size / form | Produced by | Access route (now → target) |
|---|---|---|---|---|
| D1 | **Raw per-run HRD ROOT files** | ~6.4 GB compressed; 110 files (57 `hrda_run_NNNN.root` A-stack + 53 `hrdb_run_NNNN.root` B-stack), runs 0012–0065; 18-sample waveforms @ 10 ns | CCB DAQ (reduced HRD ROOT) | controlled access (LUNARC) → **public repository w/ large-file handling** (Zenodo record or institutional archive) |
| D2 | **Sorted ROOT bundles** | `sorted-a.zip` 2.68 GB, `sorted-b.zip` 2.87 GB, `root.zip` 0.81 GB inside `CCB Data.zip` (6.37 GB) | sorting pipeline | controlled access → same deposit as D1 |
| D3 | **GEANT4 truth sample (1M events)** | `geant4/data/output_krakow_1M.root`, `hibeam` tree (primary PDG/Ekin/momentum + per-stave `LayerID`/`PDG`/`EDep`/time); summary `geant4/results/sim_summary.json` (836,534 truth protons, 314,646 deuterons) | `hibeam_g4` (HIBEAM-NNBAR GitHub) in conda `nnbar_env` | reproducible-from-public-code → **public repository** (config + macros + output) |
| D4 | **Derived selected-pulse table** | 640,737 B-stave pulse records (median selector, `A > 1000 ADC`) / 706,373 (dynamic selector); `data/processed/s00_selected_b_pulses.csv.gz` | `scripts/01_build_pulse_table_from_root.py` | within-repo but git-ignored (regenerable) → **public repository / HEPData** (small, tabular) |
| D5 | **Per-study report artifacts** | ~480 `reports/<study>/` dirs: `REPORT.md`, `manifest.json`, `result.json`, per-study CSV tables + PNG figures; per-report `input_sha256.csv` | study scripts; scoreboard `reports/SUMMARY.md`, FDR census `reports/stats01_program_fdr_*` | in git (GitHub) → **archive a tagged release to Zenodo** for a DOI |
| D6 | **Figure source data** | the CSVs backing each manuscript/WIKI figure (subset of D5) | `scripts/02_make_report_plots.py` etc. | in git → **Source Data + HEPData table per figure** |
| D7 | **Analysis + simulation code** | `scripts/`, `src/`, `geant4/`, `configs/`, tests | this repo | GitHub `SzeChunYiu/ccb-testbeam` → **archive release to Zenodo** (Code Availability) |

Integrity anchor: **Study S00** recorded a zero-tolerance reproduction of the 640,737-pulse table from
raw ROOT and stored the raw-archive SHA-256 manifest
(`reports/S00_data_integrity_pipeline_reproduction/input_sha256.csv`). The five raw-archive checksums
are reproduced in `DATA.md` and should be published verbatim in the D1/D2 deposit README.

---

## 2. Data Availability statement (ready to paste)

**Version A — truthful today (pre-deposit):**

> **Data availability.** The raw test-beam data (approximately 6.4 GB; 110 reduced HRD ROOT files
> comprising 57 A-stack and 53 B-stack per-run files, runs 12–65, with 18-sample waveforms digitized
> at 10 ns) are archived on the LUNARC computing facility
> (`/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/`) and on an immutable local store, and are
> available from the corresponding author on reasonable request pending access to the host facility.
> The GEANT4 truth-labelled simulation sample (10^6 events) was generated with the public `hibeam_g4`
> code and is reproducible from the configuration and macro files provided with the analysis code. The
> derived selected-pulse table (640,737 B-stave pulses passing the A > 1000 ADC selection) is
> regenerable from the raw files with the scripts provided; SHA-256 checksums of all raw inputs are
> given in the repository (`DATA.md`, `reports/S00_.../input_sha256.csv`). Per-study result tables and
> figure source data are included in the analysis repository (see Code availability).

**Version B — switch to this once deposits are minted (target):**

> **Data availability.** The derived data underlying the figures and the selected-pulse table are
> available at Zenodo under DOI [10.5281/zenodo.XXXXXXX] and, for the per-figure tables, at HEPData
> under [HEPData record 1XXXXXX]. The raw HRD ROOT files (~6.4 GB) and GEANT4 truth sample are deposited
> at [Zenodo/institutional repository DOI 10.5281/zenodo.YYYYYYY]; because of their size, bulk transfer
> instructions are given on the record landing page while metadata, file manifest and SHA-256 checksums
> remain openly accessible. Source data for each figure are provided with the paper. [State license,
> e.g. CC-BY-4.0 for derived data; CC0 for checksums/metadata.]

**Code availability (companion statement):**

> **Code availability.** The analysis and simulation-driver code are available at
> `https://github.com/SzeChunYiu/ccb-testbeam` and archived at [Zenodo DOI 10.5281/zenodo.ZZZZZZZ]. The
> GEANT4 physics application is the public `hibeam_g4` release (HIBEAM-NNBAR), run under GEANT4 11.2.2 /
> ROOT 6.32 / VGM 5.4.0 (conda environment `nnbar_env`); analysis used Python 3.11.

*Do not ship Version B until the DOIs actually resolve. "Available on request" (Version A) is
acceptable here only because the host facility imposes a genuine access-control restriction — but it is
the weak route and should be replaced by Version B before submission to a Nature-family journal.*

---

## 3. Repository & deposition plan (what goes where)

| Dataset | Recommended home | Rationale | Public vs controlled |
|---|---|---|---|
| D4 selected-pulse table, D6 figure source data | **HEPData** (per-figure tables) + **Zenodo** (full table) | HEPData is the particle-physics community standard for figure-level data; Zenodo gives one DOI for the full table | **public**, CC-BY-4.0 |
| D3 GEANT4 truth + configs/macros | **Zenodo** (linked to `hibeam_g4` version + git commit) | small enough; makes the PID/energy truth reusable | **public**, CC-BY-4.0 |
| D5 report artifacts / D7 code | **Zenodo via GitHub release integration** (mint DOI on a tagged release) | one command, versioned, DOI per release | **public**, code license (e.g. MIT/BSD/Apache-2.0) + CC-BY for docs |
| D1/D2 raw + sorted ROOT (~6.4 GB) | **Zenodo** (accepts up to 50 GB/record on request) **or** an institutional / national repository (SND/Swedish National Data Service, or a LUNARC-backed archive) with a DataCite DOI | community HEP raw-data archives are not mandated for this data type; a trusted generalist/large-file archive is the correct tier | **public metadata + checksums always; bulk files public if permitted, else controlled with a documented access procedure** |

Decision notes:
- No **mandated** discipline repository applies to reduced test-beam waveforms, so the tier is
  "community-recognised generalist + HEPData for figure data" (nature-data repository decision tree,
  steps 2–3).
- Keep **raw and derived separate** (own DOIs); relate them with DataCite `isDerivedFrom` /
  `isSourceOf`.
- If bulk raw files cannot be made openly downloadable (facility policy, size, or ownership by the
  CCB/HIBEAM collaboration), publish a **controlled-access record**: public landing page + manifest +
  checksums + a named contact/committee and the criteria for granting access. Never leave the only copy
  on a personal cluster path with no public metadata record.
- **Do not** cite the GitHub URL alone as the data/code identifier — archive a release for a DOI
  (a Nature "red flag": *"Data available on GitHub" without release DOI*).

---

## 4. Dataset citation stubs (fill the placeholders before submission)

DataCite pattern — `[Creator(s)] ([Year]) [Title], version [v]. [Repository]. [DOI].`

```
[1] Yiu, S.-C. et al. (2026) CCB test-beam HRD raw waveform dataset (reduced ROOT, runs 12–65),
    version 1.0. Zenodo. https://doi.org/10.5281/zenodo.YYYYYYY   [TO BE MINTED]

[2] Yiu, S.-C. et al. (2026) CCB test-beam derived selected-pulse table (640,737 B-stave pulses),
    version 1.0. Zenodo. https://doi.org/10.5281/zenodo.XXXXXXX   [TO BE MINTED]

[3] Yiu, S.-C. et al. (2026) GEANT4 truth-labelled simulation sample for the CCB HRD range telescope
    (10^6 events), version 1.0. Zenodo. https://doi.org/10.5281/zenodo.WWWWWWW   [TO BE MINTED]

[4] Yiu, S.-C. et al. (2026) ccb-testbeam analysis code, version vX.Y (git commit <hash>). Zenodo.
    https://doi.org/10.5281/zenodo.ZZZZZZZ   [TO BE MINTED; archived from
    github.com/SzeChunYiu/ccb-testbeam]

[5] CCB test-beam figure source data. HEPData record 1XXXXXX (2026).   [TO BE MINTED]
```

Confirm authorship/creator order, funding reference, and the CCB/HIBEAM collaboration's rights over the
raw data before minting (the raw beam data may be collaboration-owned, not author-owned — this governs
who can license D1/D2).

---

## 5. FAIR metadata checklist — scored against current state

Scoring: ✅ met · ⚠️ partial · ❌ missing. Score reflects **today** (LUNARC-only, no DOI).

| Principle | Check | State | Score | Concrete gap → fix |
|---|---|---|---|---|
| **Findable** | Persistent identifier (DOI/accession) | none; only a cluster filepath | ❌ | Mint Zenodo DOIs (D1–D5) + HEPData record (D6); put DOIs in the manuscript. |
| | Rich indexed metadata (title/abstract/keywords) | prose in `DATA.md`/`README.md`, not a repository record | ⚠️ | Create DataCite metadata (creators, title, year, resource type, keywords: HIBEAM, HRD, plastic scintillator, proton timing, pile-up). |
| | Metadata names the data identifier | n/a (no identifier) | ❌ | Add `relatedIdentifier` linking dataset ↔ preprint ↔ code. |
| **Accessible** | Identifier resolves via standard protocol | no resolver; needs LUNARC login | ❌ | Publish landing page (Zenodo/HEPData over HTTPS). |
| | Access conditions explicit | implicit ("on request") | ⚠️ | Write an access policy for any controlled part: who/how/criteria/contact. |
| | Metadata stay public even if data restricted | no public metadata at all | ❌ | Even if bulk raw stays controlled, publish manifest + checksums + README openly. |
| **Interoperable** | Community formats | ROOT + gzipped CSV + JSON + PNG | ✅ | Keep; also export figure data as CSV/YAML for HEPData. |
| | Shared vocabulary, units, identifiers | units live in prose/captions, not in a data dictionary | ⚠️ | Ship a data dictionary: column → definition → unit → missing-value code (e.g. `amplitude_adc` [ADC], `peak_sample` [index, 10 ns/sample], `A>1000 ADC` cut). |
| | Qualified links to related data/code/paper | git commit hashes in reports only | ⚠️ | Use DataCite relation types (`isDerivedFrom`, `isSupplementTo`, `references`). |
| **Reusable** | Clear license | **none** on data or code | ❌ | Add a data license (CC-BY-4.0 derived; CC0 metadata/checksums) + a code `LICENSE` file. |
| | Provenance | strong: per-report `manifest.json`, git commit, config path, `input_sha256.csv`, S00 exact-reproduction gate | ✅ | Keep; surface provenance in each deposit README. |
| | Methods/variables/QC documented | `REPORT_STANDARD.md`, per-study REPORT.md, selection rule documented | ✅/⚠️ | Fold into a per-dataset README (FAIR template). |
| | Versioning | git + selector variants (640,737 vs 706,373) noted | ⚠️ | Use repository versioning (Zenodo concept-DOI + version-DOI) and state selector version in the record. |
| | Checksums | SHA-256 for all raw inputs (S00) | ✅ | Publish them in the deposit; add checksums for derived table + GEANT4 output too. |

**Overall:** provenance, checksums, reproducibility and format choices are **strong** (better than
typical); findability, accessibility and licensing are **the weak axis** because nothing is deposited
with a PID/license yet.

### Blocking gaps (must clear before a Nature-family submission)
1. **No persistent identifier / stable access route** for data supporting central conclusions. → mint
   Zenodo DOIs + HEPData record.
2. **No license** on data or code. → add CC-BY-4.0 (derived data), CC0 (metadata/checksums), and a code
   license file.
3. **No public metadata record** — raw data exists only on an access-controlled cluster path. → publish
   an open landing page with manifest + checksums even if bulk raw stays controlled.
4. **Figure source data not yet mapped** to figure panels in a citable form. → HEPData table per figure.
5. **Raw-data ownership/rights unconfirmed** (CCB/HIBEAM collaboration vs authors). → confirm before
   licensing D1/D2; if collaboration-owned, use a controlled-access record with a named access route.

### Non-blocking but do-before-submission
- Add a per-dataset README (use the FAIR template) and a data dictionary with units/missing-value codes.
- Replace git-ignored derived table with a deposited, checksummed version.
- Record the exact `hibeam_g4` version/commit used for D3 in the deposit metadata.
- State selector variant (median vs dynamic) explicitly wherever the pulse count is quoted.

### 中文核对
- 数据现仅存放在 LUNARC 与本地不可变副本中，**尚无 DOI、无公开落地页、无许可协议** —— 投稿前必须补齐。
- 需作者确认：原始束流数据的**归属权**（CCB/HIBEAM 合作组 vs 作者）决定 D1/D2 能否公开授权。
- 需确认：Zenodo/HEPData 记录的创建者顺序、基金编号、许可类型（建议派生数据 CC-BY-4.0、校验和/元数据 CC0）。
</content>
