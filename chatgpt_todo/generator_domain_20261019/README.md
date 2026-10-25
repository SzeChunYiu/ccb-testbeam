# Publication assurance — generator stop-domain and direction algebra (2026-10-19)

**Status: NOT_AUTHORIZED.** This atomic follow-up to #1628/#1608 inspects main `a61427813344e29047ca9eb9b764182eb29e4c83`, `geant4/src_patch/ScatteringGenerator.cc` blob `a04da519551a7d505b4bce50b20d0b5424f0f40d`. It does not change production Geant4, publish detector claims, or supersede the unmerged #1542 corrected v3 trigger work.

## GD-01 — confirmed arithmetic domain failure

The generator's `/ElGen/E` UI condition is `E>=0.`; exact zero is permitted. In `BeamEnergy`, the 100-step target-loss loop also explicitly sets remaining energy to zero when the next positive loss exceeds the projectile's remaining energy. `GeneratePrimaryVertex` then attempts p+d elastic generation without checking reaction energy strictly positive and valid. At Ekin=0 the lab boost and both outgoing CM velocities vanish; `beta/beta3cm` and `beta/beta4cm` are 0/0. A compiled C++ scalar transcription of the exact expression yields **NaN for both outgoing polar angles** with zero kinetic energies, under both GCC 14.2.0 -O0 and -O2. The original path builds momentum directions from those angles; actual Geant4 handling is NOT tested.

A synthetic strictly positive 100 MeV/mm stopping rate over 2.3 mm from 190 MeV reaches the generator's zero-energy clamp at integration step 83. **This is an adversarial toy, not the original CD2 table nor evidence that a production beam stopped.** The normal Krakow macro uses 190 MeV and 2.3 mm; the stopped-beam frequency for the real material is NOT_EVALUATED. The old stopping-table unit/material/source contract is still BLOCKED in `docs/adr/ADR-WAVE-D-LANE04-DEDX-UNITS-BLOCKED.md`. This is a distinct domain issue from the already-reported negative high-energy stopping extrapolation.

**Required physical repair:** define the valid generator reaction-energy domain, explicitly reject impossible stopped-before-reaction encounters or use a source-justified conditional/resampling policy with correct event probability/weight accounting, and verify all four-vectors finite before adding primaries to an event. Do not hide the issue with a tiny epsilon, quietly discard affected trials, or choose energy thresholds without stopping/source evidence.

## GD-02 — bounded positive direction-vector check

Using source algebra and a separately derived invariant-mass/Lorentz-boost four-vector oracle: 6 projectile energies (1,10,60,100,190,250 MeV) × 28 repository polar-angle nodes × 8 azimuths × 2 opposite-azimuth choices = **2,688 deterministic cases**. Maximum outgoing single-momentum-component discrepancy was **7.475e−12 MeV/c**, maximum kinetic-energy difference **9.237e−13 MeV**, and maximum scalar energy or component-momentum conservation residual **6.765e−12** in respective units. This is a positive check of the source-formula θlab/φ direction plumbing for the tested positive energies, not actual Geant4 execution, source data accuracy, material stopping, detector acceptance or an error bound for production.

The 28 nodes are the repository's table, **not independently verified against the original Ermisch Table VI**. Normal 190MeV source expressions were finite. The check says neither that the old geometry is correct nor that existing detector results are validated.

## Execution

```sh
g++ -std=c++17 -O2 -Wall -Wextra -pedantic kinematics_scalar.cpp -o kinematics_scalar
python -O check_domain.py
g++ -std=c++17 -O0 -Wall -Wextra -pedantic kinematics_scalar.cpp -o kinematics_scalar_debug
./kinematics_scalar_debug 0 1.5707963267948966
```

**Five Python unittest methods passed**, and both C++ optimization levels reproduced the zero-energy NaNs. Source classes are a copied scalar excerpt, not a linked Geant4 compilation or runtime source file. The repo script produces RESULT.json with named NaN strings, never JSON NaN numerics. Reproducer environments: Debian GCC 14.2.0 and Python 3.13.5. No real ROOT files, full Geant4, beam/material measurement, latest-head CI or independent human review was executed.

Four complementary specialist perspectives were applied by **one assistant, not four human reviewers**: DAQ/metrology (target/survey unknown), transport (stopping reaction validity), statistics (resampling changes population and normalization), software/provenance (finite guards and recorded source). No scientific-release boxes close from these tests.

Next: owner-integrate a fail-closed production-domain policy, obtain authoritative stopping material/units and a fully pinned Geant4 build, test zero/stopped and ordinary 190MeV paths with actual SD/ROOT output, then propagate effects through source/trigger/PID and publication claims. Keep #1628/#1608 open and distinguish real validation from a mathematical fixture.

Primary method references: [Geant4 Event Generator Interface](https://geant4.web.cern.ch/documentation/pipelines/master/bfad_html/ForApplicationDevelopers/Fundamentals/eventGenerator.html), [NIST PSTAR stopping methods](https://pml.nist.gov/PhysRefData/Star/Text/programs.html), [historical exact two-body kinematics monograph](https://digital.library.unt.edu/ark:/67531/metadc502340/). Source/model version matters.
