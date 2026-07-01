# Scientific introduction

This wiki draft introduces the CCB testbeam MC validation status for run `20260627T175952Z_afe8992_mv4_timing_retry`. The goal is to compare frozen MC validation artifacts against detector-analysis questions while keeping production, fixture, blocked, and release states distinct.

The current package is not final-release ready. It is a curated navigation surface for validated artifacts, plots, claim ledgers, and limitations.

## Reference anchors

- `REF-GEANT4-2003` and `REF-GEANT4-2006` justify standard Geant4 toolkit terminology only; they do not by themselves prove the CCB geometry, digitizer, or production macro alignment.
- `REF-PDG-RPP-2024` anchors particle and passage-through-matter vocabulary; any numerical efficiency, energy, or range claim must still cite frozen project artifacts.
- `REF-BIRKS-1964` and `REF-KNOLL-2010` anchor scintillation-detector language; the current artifact package does not claim a fitted Birks constant or final detector calibration.
- `REF-ROOT-1997` anchors ROOT analysis-file context; raw selector-count reproduction remains governed by project S00/S00c/S00d guards, not by the external ROOT reference.
