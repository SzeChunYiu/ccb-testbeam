# G408-KEYLINEAGE-01 next-session handoff

Confirmed posted/readback LIVE #1608 comment: https://github.com/SzeChunYiu/ccb-testbeam/issues/1608#issuecomment-6393062088. Read `README.md` and `EVIDENCE.json`; do not rerun these 1,056-row generated-key tests as new progress.

The generated keyed G4-08 ROOT blob is authentic stored bytes; the audit did NOT parse its event stream with ROOT. It is not authoritative raw DAQ or Geant4 output. Source code and archived CSV show random independent Geant4 truth assignment, DAQ key stamping, followed by self-generated ROOT roundtrip. The guard successfully detects post-write key corruption, but deliberate within-run reassignment survives if output regenerated. Original report already discloses upstream event keys missing. No observed physics bias is inferred.

Historical manifest `git_commit=9ff7f2...` points to a producer source missing the keyed writer; later commit `6a88ae79...` contains it. An uncommitted-run source is possible; don't allege fabrication. Exact executed source bytes still need a receipt.

Future work should target owner-integrated honest bridge-status gates and new genuine native Sci_bar/T1/T2 writer/ROOT/DAQ/calibration evidence, or a *different* unexamined physical production atom. Never label generated seed/key matching as independent physical truth. Preserve all #781 work, closed #1023's generic domain controls, the two historic ROOT blobs and figures; no source or production was modified in this atom. Protected #977/PR1294 and canonical PR1595 untouched. Paper NOT_AUTHORIZED.
