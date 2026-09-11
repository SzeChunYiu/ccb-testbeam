#include "PrimaryGeneratorAction.hh"
#include "DetectorConstruction.hh"

#include "G4ParticleGun.hh"
#include "G4ParticleTable.hh"
#include "G4ParticleDefinition.hh"
#include "G4Event.hh"
#include "G4Exception.hh"
#include "G4SystemOfUnits.hh"
#include "G4PhysicalConstants.hh"

#include <cmath>
#include <cstdint>

namespace {

// Counter-based uniform stream (SplitMix64). Keyed on (seed, eventID) so the
// sampled phase space of event N is a pure function of the run seed and the
// event index -- identical for any --threads value and any worker scheduling.
// This deliberately does NOT touch the Geant4/CLHEP engine, whose per-event
// state drives the physics and whose same-seed 1T/48T equality is recorded
// evidence for this simulation.
inline std::uint64_t SplitMix64(std::uint64_t& x) {
  std::uint64_t z = (x += 0x9E3779B97F4A7C15ULL);
  z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
  z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
  return z ^ (z >> 31);
}

inline std::uint64_t StreamKey(std::uint64_t seed, int event_id) {
  std::uint64_t k = seed * 0x9E3779B97F4A7C15ULL;
  k ^= static_cast<std::uint64_t>(static_cast<std::uint32_t>(event_id)) +
       0x165667B19E3779F9ULL + (k << 6) + (k >> 2);
  return k;
}

inline double Uniform01(std::uint64_t& state) {
  // 53-bit mantissa in [0,1).
  return static_cast<double>(SplitMix64(state) >> 11) *
         (1.0 / 9007199254740992.0);
}

}  // namespace

PrimaryGeneratorAction::PrimaryGeneratorAction(const AppConfig& cfg) : cfg_(cfg) {
  gun_ = new G4ParticleGun(1);
  // Geant4 particle names: proton, deuteron, mu-, mu+, pi+, pi-.
  // AppConfig::ParseArgs already restricts the accepted set; a null lookup here
  // is a build/physics-list defect, not a user error, so fail loudly.
  G4ParticleDefinition* def =
      G4ParticleTable::GetParticleTable()->FindParticle(cfg_.particle);
  if (!def) {
    G4Exception("PrimaryGeneratorAction::PrimaryGeneratorAction", "CCB_PGA_001",
                FatalException,
                ("unknown Geant4 particle name: " + cfg_.particle).c_str());
  }
  gun_->SetParticleDefinition(def);
  gun_->SetParticleEnergy(cfg_.kinetic_energy_MeV * MeV);
}

PrimaryGeneratorAction::~PrimaryGeneratorAction() { delete gun_; }

void PrimaryGeneratorAction::GeneratePrimaries(G4Event* event) {
  // Enter just upstream of the -z face, travel +z (normal incidence), optionally
  // tilted by theta/phi. This crosses the 2 cm NORMAL thickness.
  const double z0 = -DetectorConstruction::kStaveHalfZ - 1.0 * mm;

  double x_cm = cfg_.hit_x_cm;
  double y_cm = cfg_.hit_y_cm;

  const double th = cfg_.theta_deg * deg;
  const double ph = cfg_.phi_deg * deg;
  G4ThreeVector dir(std::sin(th) * std::cos(ph),
                    std::sin(th) * std::sin(ph),
                    std::cos(th));

  // Issue #1623: opt-in per-event phase-space sampling. When neither flag is
  // set no random number is consumed and the launch is bit-identical to the
  // historic fixed-point behaviour.
  if (cfg_.sample_position || cfg_.sample_angle) {
    std::uint64_t state = StreamKey(cfg_.seed, event->GetEventID());
    if (cfg_.sample_position) {
      x_cm = cfg_.hit_x_min_cm +
             (cfg_.hit_x_max_cm - cfg_.hit_x_min_cm) * Uniform01(state);
      y_cm = cfg_.hit_y_min_cm +
             (cfg_.hit_y_max_cm - cfg_.hit_y_min_cm) * Uniform01(state);
    }
    if (cfg_.sample_angle) {
      // Isotropic inside a cone of half-angle theta_spread about the nominal
      // direction: cos(theta') uniform in [cos(spread), 1], phi' uniform.
      const double cos_max = std::cos(cfg_.theta_spread_deg * deg);
      const double ct = 1.0 - Uniform01(state) * (1.0 - cos_max);
      const double st = std::sqrt(std::max(0.0, 1.0 - ct * ct));
      const double pp = 2.0 * CLHEP::pi * Uniform01(state);
      G4ThreeVector cone(st * std::cos(pp), st * std::sin(pp), ct);
      cone.rotateUz(dir);  // map the cone axis onto the nominal direction
      dir = cone;
    }
  }

  gun_->SetParticlePosition(G4ThreeVector(x_cm * cm, y_cm * cm, z0));
  gun_->SetParticleMomentumDirection(dir.unit());
  gun_->GeneratePrimaryVertex(event);
}
