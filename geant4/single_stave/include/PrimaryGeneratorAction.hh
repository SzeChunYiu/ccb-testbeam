// PrimaryGeneratorAction.hh — normal-incidence proton/deuteron gun.
// Launches the primary at (hit_x, hit_y, z = -stave_half_z - eps) travelling
// +z (tilted by theta/phi), so it crosses the 2.0 cm NORMAL thickness.
#ifndef CCB_PRIMARYGENERATORACTION_HH
#define CCB_PRIMARYGENERATORACTION_HH

#include "G4VUserPrimaryGeneratorAction.hh"
#include "globals.hh"
#include "AppConfig.hh"

class G4ParticleGun;
class G4Event;

class PrimaryGeneratorAction : public G4VUserPrimaryGeneratorAction {
 public:
  explicit PrimaryGeneratorAction(const AppConfig& cfg);
  ~PrimaryGeneratorAction() override;
  void GeneratePrimaries(G4Event* event) override;

 private:
  const AppConfig cfg_;
  G4ParticleGun* gun_ = nullptr;
};

#endif  // CCB_PRIMARYGENERATORACTION_HH
