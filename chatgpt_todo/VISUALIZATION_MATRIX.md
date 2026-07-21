# Visualization Matrix

| Plot ID | Claim / purpose | Inputs | Plot code | Output | Uncertainty / acceptance criteria | State |
|---|---|---|---|---|---|---|
| VIS-G4-001 | Same-seed 1T/4T event-tree equality | Real GPU node ROOT files + meta.json | PR #868 event validator | JSON + multipage PDF | ✅ 27/27 branches exact equal, all 500 event IDs match, tolerance=0 | VALIDATED |
| VIS-G4-002 | Photon-population equality independent of ROOT row order | Real GPU node photon trees + meta.json | PR #868 photon validator | JSON + multipage PDF | ✅ 1,170,091 records, 6 fields exact equal, multiset domain checks pass | VALIDATED |
| VIS-G4-003 | Different-seed stream stability and correlation | 4 seeds on GPU node | PR #868 multiseed validator | JSON + multipage PDF | ✅ Cross-seed RSE=0.48%; no duplicate streams; seeds produce independent outputs | VALIDATED |
| VIS-G4-004 | Optical yield and PE/MeV deposited | GPU node ROOT ensemble (4 seeds, 500 events) | analysis scripts | Distribution, run/seed stability | ✅ Mean=178.3 PE, RSE=0.48%; per-seed: 177.1, 178.0, 179.5, 178.5 | VALIDATED |

Every generated plot must record title, axes, units, selections, provenance, normalization, binning, uncertainty meaning, generation command, output path, caption, and failure criteria.
