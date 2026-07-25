// StackingAction.hh — on the GPU optical path, optical-photon transport is
// delegated to Opticks, so every optical secondary (already captured by
// SteppingAction into the input-photon array) is killed here to skip the
// expensive CPU tracking. Charged primaries are unaffected. The CPU reference
// (flag OFF) routes everything to fUrgent as usual.
#ifndef CCB_STACKINGACTION_HH
#define CCB_STACKINGACTION_HH

#include "G4UserStackingAction.hh"
#include "globals.hh"
#include "AppConfig.hh"

class G4Track;

class StackingAction : public G4UserStackingAction {
 public:
  explicit StackingAction(const AppConfig& cfg) : cfg_(cfg) {}
  G4ClassificationOfNewTrack ClassifyNewTrack(const G4Track* track) override;
  void NewStage() override {}
  void PrepareNewEvent() override {}

 private:
  const AppConfig cfg_;
};

#endif  // CCB_STACKINGACTION_HH
