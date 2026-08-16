// PhysicsList.hh — configurable hadronic reference list + optical physics.
// Caller MUST pass an explicit reference list name (issue #1006). Unavailable
// lists abort; there is no warning-fallback to QGSP_BIC. Optical physics is
// registered for scintillation / WLS / boundary processes. Birks quenching
// is set on the scintillator material in DetectorConstruction.
//
// PRODUCTION CUTS are set here deliberately via SetDefaultCutValue(). Despite
// naming this parameter "production_cut_mm", it controls the Geant4 secondary-
// production range threshold (gamma, e-, e+, proton) — NOT an optical-photon
// tracking cut. Optical photons are tracked by G4OpticalPhysics with its own
// dedicated tracking thresholds (see G4OpticalParameters). Changing this value
// changes which secondary particles are produced explicitly, which in turn
// changes the local ionization-density bookkeeping that feeds Birks quenching
// (SteppingAction::UserSteppingAction). This is the "cut x kB coupling" that
// issue #1089 documents: the Birks coefficient kB MUST be re-calibrated or
// the production cut changed together with the Birks parameter.
//
// NEUTRON TRACKING-TIME CUT (issue #1091 / ADR-0005): QGSP_BIC inherits a
// documented 10 microsecond default neutron tracking-time cut from the
// Geant4 Physics List Guide. This application currently PIN/RECORDS that
// reference default in run metadata (neutron_timecut_policy_id =
// pin_qgsp_bic_default_10us) rather than silently leaving it unnamed.
// Sensitivity claims require a registered convergence digest.
//
// STEP POLICY (issue #1095 / ADR-0005): EM StepFunction / light-ion
// stepping is inherited from the reference list unless an explicit
// step_policy_id is declared. "Step-converged" claims are fail-closed
// until a registered study digest exists.
#ifndef CCB_PHYSICSLIST_HH
#define CCB_PHYSICSLIST_HH

#include "G4VModularPhysicsList.hh"
#include "globals.hh"

class PhysicsList {
 public:
  // Factory helper: returns a reference list with optical physics registered
  // and optical parameters configured. Caller passes it to the run manager.
  // @param production_cut_mm  Geant4 G4ProductionCuts range threshold [mm]
  //                            (default 0.1). Controls secondary production
  //                            (gamma, e-, e+, proton), NOT optical tracking.
  //                            See issue #1089 for the cut x kB coupling.
  static G4VModularPhysicsList* Build(const G4String& reference,
                                      G4double production_cut_mm = 0.1,
                                      const G4String& wls_time_profile = "exponential");
};

#endif  // CCB_PHYSICSLIST_HH
