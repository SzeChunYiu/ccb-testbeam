#include "PhysicsList.hh"

#include "G4PhysListFactory.hh"
#include "G4OpticalPhysics.hh"
#include "G4OpticalParameters.hh"
#include "G4SystemOfUnits.hh"
#include "G4ProcessManager.hh"

#include <iostream>

G4VModularPhysicsList* PhysicsList::Build(const G4String& reference,
                                          G4double optical_cut_mm,
                                          const G4String& wls_time_profile) {
  G4PhysListFactory factory;
  G4VModularPhysicsList* physics = nullptr;
  if (factory.IsReferencePhysList(reference)) {
    physics = factory.GetReferencePhysList(reference);
  } else {
    std::cerr << "warning: reference list '" << reference
              << "' unavailable; falling back to QGSP_BIC\n";
    physics = factory.GetReferencePhysList("QGSP_BIC");
  }

  // Optical physics: scintillation, WLS, boundary, absorption, Rayleigh.
  auto* optical = new G4OpticalPhysics();
  physics->RegisterPhysics(optical);

  // Configure optical parameters (Geant4 >= 11 API).
  auto* op = G4OpticalParameters::Instance();
  op->SetScintTrackSecondariesFirst(true);
  op->SetScintByParticleType(false);
  op->SetWLSTimeProfile(wls_time_profile);

  physics->SetDefaultCutValue(optical_cut_mm * CLHEP::mm);
  return physics;
}
