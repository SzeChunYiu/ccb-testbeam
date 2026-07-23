// PhysicsList.hh — hadronic reference list (QGSP_BIC) + optical physics.
// QGSP_BIC is a standard choice for protons/deuterons in the 10s-100s MeV range
// (Binary Cascade). Optical physics is registered for scintillation / WLS /
// boundary processes. Birks quenching is set on the scintillator material in
// DetectorConstruction; production cuts are set here deliberately.
#ifndef CCB_PHYSICSLIST_HH
#define CCB_PHYSICSLIST_HH

#include "G4VModularPhysicsList.hh"
#include "globals.hh"

class PhysicsList {
 public:
  // Factory helper: returns a reference list with optical physics registered
  // and optical parameters configured. Caller passes it to the run manager.
  static G4VModularPhysicsList* Build(const G4String& reference = "QGSP_BIC",
                                      G4double optical_cut_mm = 0.1,
                                      const G4String& wls_time_profile = "exponential");
};

#endif  // CCB_PHYSICSLIST_HH
