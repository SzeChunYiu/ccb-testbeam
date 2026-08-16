#include "PrimaryGeneratorAction.hh"
#include "DetectorConstruction.hh"

#include "G4ParticleGun.hh"
#include "G4ParticleTable.hh"
#include "G4ParticleDefinition.hh"
#include "G4Proton.hh"
#include "G4Deuteron.hh"
#include "G4Event.hh"
#include "G4SystemOfUnits.hh"
#include "G4PhysicalConstants.hh"

#include <cmath>

PrimaryGeneratorAction::PrimaryGeneratorAction(const AppConfig& cfg) : cfg_(cfg) {
  gun_ = new G4ParticleGun(1);
  G4ParticleDefinition* def =
      (cfg_.particle == "deuteron")
          ? static_cast<G4ParticleDefinition*>(G4Deuteron::Deuteron())
          : static_cast<G4ParticleDefinition*>(G4Proton::Proton());
  gun_->SetParticleDefinition(def);
  gun_->SetParticleEnergy(cfg_.kinetic_energy_MeV * MeV);
}

PrimaryGeneratorAction::~PrimaryGeneratorAction() { delete gun_; }

void PrimaryGeneratorAction::GeneratePrimaries(G4Event* event) {
  // Enter just upstream of the -z face, travel +z (normal incidence), optionally
  // tilted by theta/phi. This crosses the 2 cm NORMAL thickness.
  const double z0 = -DetectorConstruction::kStaveHalfZ - 1.0 * mm;
  gun_->SetParticlePosition(G4ThreeVector(cfg_.hit_x_cm * cm,
                                          cfg_.hit_y_cm * cm, z0));
  const double th = cfg_.theta_deg * deg;
  const double ph = cfg_.phi_deg * deg;
  const G4ThreeVector dir(std::sin(th) * std::cos(ph),
                          std::sin(th) * std::sin(ph),
                          std::cos(th));
  gun_->SetParticleMomentumDirection(dir.unit());
  gun_->GeneratePrimaryVertex(event);
}
