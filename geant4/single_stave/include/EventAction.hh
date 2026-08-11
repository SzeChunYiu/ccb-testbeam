// EventAction.hh — owns the per-event accumulators and applies the SiPM
// occupancy-saturation model before handing the event to RunAction.
#ifndef CCB_EVENTACTION_HH
#define CCB_EVENTACTION_HH

#include "G4UserEventAction.hh"
#include "globals.hh"
#include "AppConfig.hh"
#include "OpticalTables.hh"
#include "SimData.hh"
#include "ccb/sipm/Config.hh"  // ModelConfig (SIPM-P1-002)

class RunAction;
class G4Event;

class EventAction : public G4UserEventAction {
 public:
  EventAction(const AppConfig& cfg, const OpticalTables& tables,
              RunAction* run_action);
  ~EventAction() override = default;

  void BeginOfEventAction(const G4Event* event) override;
  void EndOfEventAction(const G4Event* event) override;

  EventData& Data() { return data_; }

  // Legacy analytical occupancy saturation (INDEPENDENT_DIAGNOSTIC_DRAW).
  // Not the latent microcell state that produced adc_* (#1084).
  double ApplySaturation(double n_pe) const;

  // Build the ccb-sipm-core ModelConfig from AppConfig + optical tables + env.
  ccb::sipm::ModelConfig BuildSipmConfig() const;

  const ccb::sipm::ModelConfig& SipmConfig() const { return sipm_config_; }

 private:
  const AppConfig cfg_;
  OpticalTables tables_;
  RunAction* run_action_ = nullptr;
  EventData data_;
  ccb::sipm::ModelConfig sipm_config_;  // base config; sensor_id set per sensor
};

#endif  // CCB_EVENTACTION_HH
