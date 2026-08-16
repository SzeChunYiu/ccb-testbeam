#include "TrackingAction.hh"
#include "EventAction.hh"
#include "SimData.hh"

#include "G4Track.hh"
#include "G4OpticalPhoton.hh"
#include "G4VProcess.hh"
#include "G4Step.hh"

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

void TrackingAction::PostUserTrackingAction(const G4Track* track) {
  // #1088: count optical photons whose transport ENDED in the OpWLS process
  // (WLS absorption), the denominator of the multiplicity known-answer
  // observable n_wls_generated / n_wls_absorbed (expected 1, mu, q per mode).
  if (track->GetDefinition() != G4OpticalPhoton::OpticalPhoton()) return;
  const G4Step* step = track->GetStep();
  if (!step) return;
  const G4VProcess* post = step->GetPostStepPoint()->GetProcessDefinedStep();
  if (post && post->GetProcessName() == "OpWLS") {
    ++event_action_->Data().n_wls_absorbed;
  }
}
