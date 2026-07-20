#include "TrackingAction.hh"
#include "EventAction.hh"
#include "SimData.hh"

#include "G4Track.hh"
#include "G4OpticalPhoton.hh"
#include "G4VProcess.hh"

TrackingAction::TrackingAction(EventAction* event_action)
    : event_action_(event_action) {}

void TrackingAction::PreUserTrackingAction(const G4Track* track) {
  if (track->GetDefinition() != G4OpticalPhoton::OpticalPhoton()) return;
  // Count generated optical photons by creator process, once per track.
  const G4VProcess* creator = track->GetCreatorProcess();
  if (!creator) return;
  const G4String& proc = creator->GetProcessName();
  EventData& d = event_action_->Data();
  if (proc == "Scintillation")   ++d.n_scint_generated;
  else if (proc == "OpWLS")      ++d.n_wls_generated;
  else if (proc == "Cerenkov")   ++d.n_cerenkov_generated;
}
