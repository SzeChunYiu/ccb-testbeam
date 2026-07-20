#include "DetectorMessenger.hh"
#include "AppConfig.hh"

#include "G4UIdirectory.hh"
#include "G4UIcmdWithAString.hh"
#include "G4UIcmdWithADoubleAndUnit.hh"
#include "G4UIcmdWithAnInteger.hh"
#include "G4UIcmdWithADouble.hh"
#include "G4SystemOfUnits.hh"

DetectorMessenger::DetectorMessenger(AppConfig* cfg) : cfg_(cfg) {
  dir_ = new G4UIdirectory("/ccb/");
  dir_->SetGuidance("CCB single-stave run-time controls.");

  cmd_particle_ = new G4UIcmdWithAString("/ccb/particle", this);
  cmd_particle_->SetGuidance("proton|deuteron");
  cmd_particle_->SetParameterName("name", false);

  cmd_energy_ = new G4UIcmdWithADoubleAndUnit("/ccb/energy", this);
  cmd_energy_->SetGuidance("primary kinetic energy");
  cmd_energy_->SetParameterName("E", false);
  cmd_energy_->SetUnitCategory("Energy");

  cmd_nevents_ = new G4UIcmdWithAnInteger("/ccb/nevents", this);
  cmd_nevents_->SetGuidance("events for the next /run/beamOn");

  cmd_hitx_ = new G4UIcmdWithADoubleAndUnit("/ccb/hitX", this);
  cmd_hitx_->SetParameterName("x", false);
  cmd_hitx_->SetUnitCategory("Length");

  cmd_hity_ = new G4UIcmdWithADoubleAndUnit("/ccb/hitY", this);
  cmd_hity_->SetParameterName("y", false);
  cmd_hity_->SetUnitCategory("Length");

  cmd_theta_ = new G4UIcmdWithADouble("/ccb/thetaDeg", this);
  cmd_theta_->SetParameterName("theta", false);

  cmd_birks_ = new G4UIcmdWithADouble("/ccb/birksKB", this);
  cmd_birks_->SetGuidance("Birks kB [mm/MeV]");
  cmd_birks_->SetParameterName("kB", false);

  cmd_seed_ = new G4UIcmdWithAnInteger("/ccb/seed", this);
  cmd_seed_->SetGuidance("RNG seed");
}

DetectorMessenger::~DetectorMessenger() {
  delete cmd_particle_; delete cmd_energy_; delete cmd_nevents_;
  delete cmd_hitx_; delete cmd_hity_; delete cmd_theta_;
  delete cmd_birks_; delete cmd_seed_; delete dir_;
}

void DetectorMessenger::SetNewValue(G4UIcommand* command, G4String value) {
  if (!cfg_) return;
  if (command == cmd_particle_) cfg_->particle = value;
  else if (command == cmd_energy_) cfg_->kinetic_energy_MeV = cmd_energy_->GetNewDoubleValue(value) / MeV;
  else if (command == cmd_nevents_) cfg_->n_events = cmd_nevents_->GetNewIntValue(value);
  else if (command == cmd_hitx_) cfg_->hit_x_cm = cmd_hitx_->GetNewDoubleValue(value) / cm;
  else if (command == cmd_hity_) cfg_->hit_y_cm = cmd_hity_->GetNewDoubleValue(value) / cm;
  else if (command == cmd_theta_) cfg_->theta_deg = cmd_theta_->GetNewDoubleValue(value);
  else if (command == cmd_birks_) cfg_->birks_kB_mm_per_MeV = cmd_birks_->GetNewDoubleValue(value);
  else if (command == cmd_seed_) cfg_->seed = (std::uint64_t)cmd_seed_->GetNewIntValue(value);
}
