# Study Review Ledger

| Study ID | Study | State | Current evidence | Main limitation | Next validation |
|---|---|---|---|---|---|
| ST-G4-OPT-001 | Single-stave optical collection and ~178 PE/event | FLAWED | Prior repository result and documentation; no current-branch regeneration | Missing current executable provenance, uncertainty, hashes, and real MT validation | Rebuild, rerun declared configuration, quantify event/seed uncertainty, generate plots |
| ST-G4-RNG-001 | Geant4 single-stave MT RNG reproducibility | PARTIAL | PR #868 validators; synthetic pytest passed | Real Geant4 outputs unavailable; lint still failed at inspected head | Fix lint, then run same-seed 1T/4T, forced-thread, and multiseed studies |

Add one record per identifiable study. Preserve negative and superseded findings.
