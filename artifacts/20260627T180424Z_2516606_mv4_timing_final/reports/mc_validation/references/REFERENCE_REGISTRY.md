# MC validation reference registry

- **Status:** `PASS`
- **Final bibliography:** `BLOCKED`
- **Blocked reference count:** `1`

| ID | Type | Status | Citation | Note |
|---|---|---:|---|---|
| REF-RUNBOOK | project-specification | AVAILABLE | Project runbook supplied in repository session; governs execution, reporting, thesis, release requirements. | Local operator-provided specification, not an external literature source. |
| REF-VALIDATION-ARTIFACTS | frozen-artifact | AVAILABLE | Run 20260625T064500Z_full_input_artifacted, SLURM job 3316536, frozen validation artifacts under configured LUNARC artifact root. | Primary evidence for current MV1-MV3/MV9 artifact-summary claims. |
| REF-GEANT4-2003 | simulation-toolkit-literature | AVAILABLE | S. Agostinelli et al., Nuclear Instruments and Methods in Physics Research A 506 (2003) 250-303, doi:10.1016/S0168-9002(03)01368-8. | Cites the detector-transport toolkit family used for MC truth/artifact interpretation; does not validate this project's geometry or digitizer by itself. |
| REF-GEANT4-2006 | simulation-toolkit-literature | AVAILABLE | J. Allison et al., IEEE Transactions on Nuclear Science 53 (2006) 270-278, doi:10.1109/TNS.2006.869826. | Secondary Geant4 toolkit reference for development/application context; project-specific validation remains artifact-gated. |
| REF-PDG-RPP-2024 | particle-data-review | AVAILABLE | S. Navas et al. (Particle Data Group), Physical Review D 110 (2024) 030001, doi:10.1103/PhysRevD.110.030001. | General particle-physics and passage-through-matter reference; numerical claims still require project artifact evidence. |
| REF-BIRKS-1964 | scintillation-literature | AVAILABLE | J. B. Birks, The Theory and Practice of Scintillation Counting, Pergamon/Macmillan, 1964. | Background reference for scintillation response and quenching vocabulary; no Birks-constant fit is claimed from current artifacts. |
| REF-KNOLL-2010 | detector-textbook | AVAILABLE | G. F. Knoll, Radiation Detection and Measurement, 4th ed., Wiley, 2010, ISBN 978-0-470-13148-0. | Detector instrumentation background reference for scintillators and radiation measurements; not a substitute for run-specific calibration. |
| REF-ROOT-1997 | analysis-framework-literature | AVAILABLE | R. Brun and F. Rademakers, Nuclear Instruments and Methods in Physics Research A 389 (1997) 81-86, doi:10.1016/S0168-9002(97)00048-X. | Cites ROOT file/data-analysis framework context for raw-data handling; selector-count truth remains guarded by project checks. |
| REF-FINAL-BIBLIOGRAPHY-AUDIT | release-blocker | BLOCKED | Blocked until every thesis/wiki claim maps to either a frozen project artifact, a curated internal note, or an external literature reference. | Do not invent references; the registry now contains core external references, but final publication-grade bibliography coverage remains intentionally fail-closed. |
