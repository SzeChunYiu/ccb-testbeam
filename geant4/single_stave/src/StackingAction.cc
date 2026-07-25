#include "StackingAction.hh"

#include "G4Track.hh"
#include "G4OpticalPhoton.hh"

G4ClassificationOfNewTrack
StackingAction::ClassifyNewTrack(const G4Track* track) {
  if (cfg_.gpu_optical &&
      track->GetDefinition() == G4OpticalPhoton::OpticalPhoton()) {
    return fKill;  // transport happens on GPU (Opticks) instead
  }
  return fUrgent;
}
