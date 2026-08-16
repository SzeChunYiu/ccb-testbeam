#include "PhysicsList.hh"

#include "G4PhysListFactory.hh"
#include "G4OpticalPhysics.hh"
#include "G4OpticalParameters.hh"
#include "G4SystemOfUnits.hh"
#include "G4ProcessManager.hh"
#include "G4Exception.hh"

#include <iostream>
#include <sstream>

G4VModularPhysicsList* PhysicsList::Build(const G4String& reference,
                                          G4double production_cut_mm,
                                          const G4String& wls_time_profile) {
  // Issue #1006: fail closed — never warning-fallback to another list.
  if (reference.empty()) {
    G4Exception("PhysicsList::Build", "CCBPhysList0001", FatalException,
                "physics list reference is empty; pass an explicit "
                "--physics-list (no silent QGSP_BIC default)");
  }

  G4PhysListFactory factory;
  if (!factory.IsReferencePhysList(reference)) {
    std::ostringstream msg;
    msg << "requested reference physics list '" << reference
        << "' is unavailable in this Geant4 build; refusing to fall back "
           "(issue #1006 fail-closed)";
    G4Exception("PhysicsList::Build", "CCBPhysList0002", FatalException,
                msg.str().c_str());
  }
  G4VModularPhysicsList* physics = factory.GetReferencePhysList(reference);
  if (physics == nullptr) {
    std::ostringstream msg;
    msg << "G4PhysListFactory returned null for '" << reference << "'";
    G4Exception("PhysicsList::Build", "CCBPhysList0003", FatalException,
                msg.str().c_str());
  }

  // Optical physics: scintillation, WLS, boundary, absorption, Rayleigh.
  auto* optical = new G4OpticalPhysics();
  physics->RegisterPhysics(optical);

  // Configure optical parameters (Geant4 >= 11 API).
  auto* op = G4OpticalParameters::Instance();
  op->SetScintTrackSecondariesFirst(true);
  op->SetScintByParticleType(false);
  op->SetWLSTimeProfile(wls_time_profile);

  // Set the global secondary-production range threshold. This is NOT an
  // optical-photon tracking cut — G4OpticalPhysics uses its own dedicated
  // tracking thresholds. The value controls production of gamma, e-, e+, and
  // proton secondaries. Changing this value alters the explicit delta-ray
  // population, which changes local ionization density bookkeeping in the
  // Birks-quenching calculation (SteppingAction::UserSteppingAction). See
  // issue #1089 for the cut x kB coupling.
  physics->SetDefaultCutValue(production_cut_mm * CLHEP::mm);
  return physics;
}
