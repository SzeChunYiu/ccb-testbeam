// -------------------------------------------------
// Trigger Sensitive Detector Implementation
// Records energy deposit and time for T1/T2 trigger scintillators
// -------------------------------------------------

#include "TriggerSensitiveDetector.hh"
#include "G4Step.hh"
#include "G4TouchableHistory.hh"
#include "G4HCofThisEvent.hh"
#include "G4SDManager.hh"
#include "G4SystemOfUnits.hh"
#include <iostream>

TriggerSensitiveDetector::TriggerSensitiveDetector(const G4String& nameVol)
    : SD_Det(nameVol), fEarliestTime(1e30), fTotalEDep(0.0), fHitCount(0)
{
}

TriggerSensitiveDetector::~TriggerSensitiveDetector() {}

void TriggerSensitiveDetector::Initialize(G4HCofThisEvent* HCE)
{
    SD_Det::Initialize(HCE);
    fEarliestTime = 1e30;
    fTotalEDep = 0.0;
    fHitCount = 0;
}

G4bool TriggerSensitiveDetector::ProcessHits(G4Step* aStep, G4TouchableHistory*)
{
    // Get energy deposit
    double edep = aStep->GetTotalEnergyDeposit() / MeV;
    
    if (edep <= 0.0) return false;
    
    // Get time of hit (global time)
    double hitTime = aStep->GetPreStepPoint()->GetGlobalTime() / ns;
    
    // Track earliest time and total EDep
    if (hitTime < fEarliestTime) {
        fEarliestTime = hitTime;
    }
    fTotalEDep += edep;
    fHitCount++;
    
    // Also record in parent class for general hit tracking
    return SD_Det::ProcessHits(aStep, nullptr);
}

void TriggerSensitiveDetector::EndOfEvent(G4HCofThisEvent* HCE)
{
    SD_Det::EndOfEvent(HCE);
    
    // Print summary for debugging
    if (fTotalEDep > 0.0) {
        std::cout << "[TriggerSD] " << SensitiveDetectorName 
                  << " EDep=" << fTotalEDep << " MeV"
                  << " Time=" << fEarliestTime << " ns"
                  << " Hits=" << fHitCount << std::endl;
    }
}
