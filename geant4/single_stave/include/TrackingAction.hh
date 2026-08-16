// TrackingAction.hh — counts optical photons at CREATION time by creator
// process (Scintillation / OpWLS / Cerenkov). This is the correct place to
// count generated photons; it does NOT rely on energy deposit in the fibre
// (the prototype defect).
#ifndef CCB_TRACKINGACTION_HH
#define CCB_TRACKINGACTION_HH

#include "G4UserTrackingAction.hh"

class EventAction;

class TrackingAction : public G4UserTrackingAction {
 public:
  explicit TrackingAction(EventAction* event_action);
  void PreUserTrackingAction(const G4Track* track) override;
  void PostUserTrackingAction(const G4Track* track) override;

 private:
  EventAction* event_action_ = nullptr;
};

#endif  // CCB_TRACKINGACTION_HH
