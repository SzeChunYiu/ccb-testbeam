# Active Task

- **Task ID:** AUD-G4-003
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-23T09:27:46Z
- **Initial main SHA:** `3ecefa27002e370f57001399d27a88244e0aa523`
- **Concurrent main SHA incorporated before the validated change:** `aea19386b7d2f25e5a0b5d64bb585f3fe0f1a2ef`
- **Scope:** independently review the repository impact of merged PR #888 and remove generated Geant4 build products without altering its scientific source changes.
- **Confirmed finding:** PR #888 added 71 files, of which 66 were under `geant4/single_stave/build/`. They included CMake cache/generator files, object files, compiler probes, a linked executable, copied macros/optical tables, and a generated metadata sidecar. `CMakeLists.txt` explicitly creates those runtime copies in the binary directory, so they are build products rather than canonical source.
- **Validated change:** removed the tracked build tree, ignored future `geant4/**/build/` trees, and added a Git-index regression test that fails whenever a Geant4 build artifact is tracked.
- **Validation:** the regression was compiled and exercised in a synthetic Git checkout: it failed with a tracked `CMakeCache.txt`, then passed after removal plus the ignore rule (`1 passed in 0.03s`). The candidate commit was inspected before updating `main`; the build path returned 404 while PR #888/PR #889 source files remained present. Remote `main` contains `c7cdd653c5fef08b1e70cb33db9c574f7e7e0de9`.
- **Boundary:** no PR #888 or PR #889 scientific source change was reverted. No Geant4 executable was run, no ROOT file or detector result was regenerated, and the four PR #888 scientific fixes remain only partially independently reviewed.
- **Status:** COMPLETE for repository hygiene and recurrence prevention; PARTIAL for independent scientific review of PR #888 source claims.
