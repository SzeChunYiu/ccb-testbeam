# Visualization Matrix

| Plot ID | Claim / purpose | Inputs | Plot code | Output | Uncertainty / acceptance criteria | State |
|---|---|---|---|---|---|---|
| VIS-G4-001 | Same-seed 1T/4T event-tree equality | Real event ROOT files + metadata | PR #868 event validator | JSON + multipage PDF | Exact comparison first; any tolerance must be justified; complete unique event IDs required | BLOCKED |
| VIS-G4-002 | Photon-population equality independent of ROOT row order | Real optical photon trees + metadata | PR #868 photon validator | JSON + multipage PDF | Canonical full-record multiset equality; valid event keys, sensor IDs, wavelengths, times, paths, detection flags | BLOCKED |
| VIS-G4-003 | Different-seed stream stability and correlation | >=4 unique seeds/effective-thread group | PR #868 multiseed validator | JSON + multipage PDF | Thresholds fixed before final ensemble; reject duplicate streams, anomalous seed means, excessive correlations/thread effects | BLOCKED |
| VIS-G4-004 | Optical yield and PE/MeV deposited | Current-branch optical ROOT ensemble | To be implemented or extended from analysis scripts | Distribution, run/seed stability, uncertainty summary, configuration table | Axes and units explicit; event and seed uncertainty; no promotion of simulation to calibrated detector response | NOT_STARTED |

Every generated plot must record title, axes, units, selections, provenance, normalization, binning, uncertainty meaning, generation command, output path, caption, and failure criteria.
