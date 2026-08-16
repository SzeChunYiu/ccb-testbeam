// SteppingAction.hh — two jobs:
//  (1) charged/non-optical primary: accumulate quenched + raw Edep and track
//      length INSIDE the scintillator, and entry/exit points.
//  (2) optical photons: detect a boundary crossing from a fibre core into a
//      named endcap sensor volume, record raw arrival (sensor, wavelength,
//      time, path length), then apply PDE * coupling for the detected flag and
//      KILL the photon at the sensor to prevent double counting.
#ifndef CCB_STEPPINGACTION_HH
#define CCB_STEPPINGACTION_HH

#include "G4UserSteppingAction.hh"
#include "globals.hh"
#include "AppConfig.hh"
#include "OpticalTables.hh"

class EventAction;

class SteppingAction : public G4UserSteppingAction {
 public:
  SteppingAction(const AppConfig& cfg, const OpticalTables& tables,
                 EventAction* event_action);
  void UserSteppingAction(const G4Step* step) override;

 private:
  int SensorIndexForVolume(const G4String& name) const;  // -1 if not a sensor
  double PdeAt(double wavelength_nm) const;

  const AppConfig cfg_;
  OpticalTables tables_;
  EventAction* event_action_ = nullptr;
};

#endif  // CCB_STEPPINGACTION_HH
