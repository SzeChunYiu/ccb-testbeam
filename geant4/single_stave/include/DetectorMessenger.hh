// DetectorMessenger.hh — exposes the run-time knobs macros need. argv parsing
// (AppConfig::ParseArgs) is the primary interface for batch/SLURM; this
// messenger lets interactive/vis macros override the same fields.
#ifndef CCB_DETECTORMESSENGER_HH
#define CCB_DETECTORMESSENGER_HH

#include "G4UImessenger.hh"
#include "globals.hh"

struct AppConfig;
class G4UIdirectory;
class G4UIcmdWithAString;
class G4UIcmdWithADoubleAndUnit;
class G4UIcmdWithAnInteger;
class G4UIcmdWithADouble;

// Holds a pointer to the live AppConfig so /ccb/... commands mutate it before
// the run. The DetectorConstruction reads AppConfig at Construct() time.
class DetectorMessenger : public G4UImessenger {
 public:
  explicit DetectorMessenger(AppConfig* cfg);
  ~DetectorMessenger() override;
  void SetNewValue(G4UIcommand* command, G4String value) override;

 private:
  AppConfig* cfg_ = nullptr;
  G4UIdirectory* dir_ = nullptr;
  G4UIcmdWithAString* cmd_particle_ = nullptr;
  G4UIcmdWithADoubleAndUnit* cmd_energy_ = nullptr;
  G4UIcmdWithAnInteger* cmd_nevents_ = nullptr;
  G4UIcmdWithADoubleAndUnit* cmd_hitx_ = nullptr;
  G4UIcmdWithADoubleAndUnit* cmd_hity_ = nullptr;
  G4UIcmdWithADouble* cmd_theta_ = nullptr;
  G4UIcmdWithADouble* cmd_birks_ = nullptr;
  G4UIcmdWithAnInteger* cmd_seed_ = nullptr;
};

#endif  // CCB_DETECTORMESSENGER_HH
