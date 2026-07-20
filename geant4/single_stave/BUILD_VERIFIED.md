# Build verification — LUNARC (Geant4 11.2.2)

The single-stave optical simulation (#796) builds and passes its smoke tests on
LUNARC with the real Geant4 toolkit.

| item | value |
|---|---|
| Date | 2026-07-20 |
| Host | cosmos3.int.lunarc |
| Toolchain | `module load GCC/12.3.0 Geant4/11.2.2` |
| Geant4 | 11.2.2 (GCC-12.3.0) |
| CMake | configure found Geant4 11.2.2, `-DCCB_ENABLE_VIS=OFF` |
| Compile | 100% — `ccb_stave_sim` (187 KB) |
| ctest | **3/3 passed** |

```
1/3 ccb_stave_geometry_smoke ............ Passed   (OVERLAP_CHECK_PASS)
2/3 ccb_stave_proton_smoke .............. Passed   (5-event proton run -> CCB_STAVE_END)
3/3 ccb_stave_geometry_report_python .... Passed   (geometry invariants)
```

## One fix required vs the as-merged code
`src/PrimaryGeneratorAction.cc`: the proton/deuteron selection ternary returned
distinct pointer types (`G4Deuteron*` vs `G4Proton*`); GCC 12 requires an
explicit cast to the common base `G4ParticleDefinition*`. Fixed in this commit.

## Reproduce
```bash
git clone --depth 1 --branch main https://github.com/SzeChunYiu/ccb-testbeam /tmp/ccb   # clone to LOCAL disk (fs10 rejects git config locking)
module load GCC/12.3.0 Geant4/11.2.2
cd /tmp/ccb/geant4/single_stave && bash slurm/build.sh build
```

Note: clone to node-local `/tmp` (or `$SNIC_TMP`), not fs10 — the fs10 NFS mount
rejects git's config-file locking (`could not lock config file .../.git/config`).
