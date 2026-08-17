// -------------------------------------------------
// Trigger Sensitive Detector for Phase 2 of #1045
// Records energy deposit and time for T1/T2 trigger scintillators
// -------------------------------------------------

#ifndef TRIGGERSENSITIVEDETECTOR_H
#define TRIGGERSENSITIVEDETECTOR_H

#include "SensitiveD.hh"
#include "SingleHit.hh"

class TriggerSensitiveDetector : public SD_Det
{
public:
    TriggerSensitiveDetector(const G4String& nameVol);
    virtual ~TriggerSensitiveDetector();
    
    G4bool ProcessHits(G4Step* aStep, G4TouchableHistory* rohist) override;
    virtual void Initialize(G4HCofThisEvent* HCE) override;
    virtual void EndOfEvent(G4HCofThisEvent*) override;
    
private:
    // Track earliest time and total EDep per event for this volume
    double fEarliestTime;
    double fTotalEDep;
    int fHitCount;
};

#endif // TRIGGERSENSITIVEDETECTOR_H
