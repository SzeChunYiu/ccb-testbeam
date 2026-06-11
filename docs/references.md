# References

Key references grouped by topic. The thesis source keeps this as a compact working bibliography
for the docs; paper-specific citation keys should be normalized when the manuscript is moved to a
formal BibTeX workflow.

## Statistics / ML methods
- Breiman, *Random Forests*, Mach. Learn. 45 (2001) — RF classifier. [29]
- Hoerl & Kennard, *Ridge Regression*, Technometrics 12 (1970). [30]
- Metodiev, Nachman, Thaler, *Classification Without Labels (CWoLa)*, JHEP 10 (2017) 174 — weak
  supervision from mixed samples. [40]

## Pile-up / waveform decomposition & recovery
- Belli et al. — NE213 pile-up separation (separations ≳15 ns reducible). [31]
- Luo et al. — pile-up decomposition. [32]
- Fu et al. — ML pile-up methods. [33]
- Kim et al. — deep learning pile-up. [34]
- Deltoro et al. — 1-D convolutional autoencoder for NEDA. [35]
- Liu et al. — support-vector-regression pile-up. [36]
- Liu et al. — saturation recovery. [37]
- Lee & Park — PMT saturation recovery. [38]
- Anderson et al. — HPGe convolutional autoencoder denoising. [39]

## Timing / CFD / detectors
- Gedcke & McDonald — constant-fraction timing. [14]
- Fallu-Labruyere et al. — digital CFD. [15]
- Stopping power / quenching: NIST PSTAR, Bethe, ICRU; Birks quenching [7,8]; Pöschl ionisation
  quenching [9].
- TOF-detector performance comparisons: ALICE, STAR, BESIII, CLAS12, HADES, NA62, CMS MIP,
  ATLAS HGTD, MEG II, SuperFGD [26].

## Simulation and energy-loss references
- GEANT4 Collaboration papers and application developer documentation for detector geometry,
  particle transport, and truth-tree production.
- NIST PSTAR proton stopping-power tables for external stopping-power scale checks.
- Birks, *The Theory and Practice of Scintillation Counting*, for ionisation-quenching response.

## CCB analysis artifacts
- `reports/SUMMARY.md` and the per-study `REPORT.md` files are the authoritative local analysis
  record for quoted numbers.
- [FINDINGS_SUMMARY.md](FINDINGS_SUMMARY.md) lists the high-level claims and links the plots used
  in the Markdown narrative.
- [latex/main.tex](latex/main.tex) is the thesis-style assembled manuscript.
