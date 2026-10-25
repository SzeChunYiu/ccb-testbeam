# OGUARD-WIN01 handoff

Live #1608 finding POSTED_AND_READ_BACK: https://github.com/SzeChunYiu/ccb-testbeam/issues/1608#issuecomment-6403512006.

Read README, EVIDENCE and exact `optical_guard.inc`. This is source-excerpt fake-interface C++/Python verification, **not** native G4/ROOT/DAQ. The historical 3875 step kills have no per-kill times; the independent step guard can conditionally kill at t=100ns within a stated 250ns window. The unqualified #1623 truncation-no-impact claim is unproven for this guard, not disproven by observed hardware or transport. Full executable local ZIP SHA256 `fdd688080f677a233b19e870b3f32af5053f391d3cfbfd5cb66c78d24bda480c` (not committed). No protected #977/PR1294, canonical PR1595 or production edits. Choose a materially different physics/production atom after this; publication blocked.
