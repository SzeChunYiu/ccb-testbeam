#include "StackingAction.hh"

#include "G4Track.hh"
#include "G4OpticalPhoton.hh"
#include "G4VProcess.hh"
#include "Randomize.hh"

G4ClassificationOfNewTrack
StackingAction::ClassifyNewTrack(const G4Track* track) {
  if (cfg_.gpu_optical &&
      track->GetDefinition() == G4OpticalPhoton::OpticalPhoton()) {
    return fKill;  // transport happens on GPU (Opticks) instead
  }
  // #1088 bernoulli_thinned: kill each OpWLS re-emission with probability
  // (1-q). Draw ONLY when q<1 so q=1 leaves the RNG stream untouched; the
  // draw is ordered last (definition -> creator -> RNG) so non-WLS optical
  // photons never consume random numbers.
  if (cfg_.wls_fluorescence_model == "bernoulli_thinned" &&
      cfg_.wls_fluorescence_yield < 1.0 &&
      track->GetDefinition() == G4OpticalPhoton::OpticalPhoton()) {
    const G4VProcess* creator = track->GetCreatorProcess();
    if (creator && creator->GetProcessName() == "OpWLS" &&
        G4UniformRand() >= cfg_.wls_fluorescence_yield) {
      return fKill;
    }
  }
  return fUrgent;
}
