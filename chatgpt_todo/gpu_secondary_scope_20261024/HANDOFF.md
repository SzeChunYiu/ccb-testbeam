# GPU-STEP-01 next-session handoff

Live owning #1608 comment is **POSTED_AND_READ_BACK**: https://github.com/SzeChunYiu/ccb-testbeam/issues/1608#issuecomment-6389388653.

Do **not** duplicate GPU-STEP-01: exact main-source `GetSecondary()` is cumulative per parent track, `GetSecondaryInCurrentStep()` is per step, and the optional GPU input is not creator-filtered. The C++ source-mock's 4-versus-2/210-versus-20 outputs are not Geant4 or beam measurements. All 12 tests in normal/-O passed; executable mock only exists in conversation ZIP, not here.

Next owner-integrated task: native G4 11.2.2 (or actual installed version) producer identity, track/step/parent/creator occurrence ledger, current-step API correction and physically meaningful all-optical vs scint-only policy, then actual Opticks NPY/CPU parity with frozen version/physics/geometry/seed, figures, covariance and human signoff. If native runtime/custody is absent, select a DIFFERENT physical-source or production atom; do not rerun this mock as research progress.

Main `a614278...`, PR1629 prior head `a8b8d9ae...`, canonical PR1595 prior head `8a5344a0...` were read. Protected merged #977/PR1294 work is untouched; external Sci_bar/T1/T2 writer remains separate. **NOT_AUTHORIZED**.
