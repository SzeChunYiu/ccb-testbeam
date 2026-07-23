#include "EventAction.hh"
#include "RunAction.hh"
#include "SimData.hh"

#include "G4Event.hh"
#include "G4SystemOfUnits.hh"

#include <cmath>
#include <iostream>

EventAction::EventAction(const AppConfig& cfg, RunAction* run_action)
    : cfg_(cfg), run_action_(run_action) {}

void EventAction::BeginOfEventAction(const G4Event*) { data_.Reset(); }

double EventAction::ApplySaturation(double n_pe) const {
  // Non-recovery occupancy model: N_fired = Ncells * (1 - exp(-Npe/Ncells)).
  const double ncell = static_cast<double>(cfg_.sipm_n_cells);
  if (ncell <= 0) return n_pe;
  return ncell * (1.0 - std::exp(-n_pe / ncell));
}

void EventAction::EndOfEventAction(const G4Event* event) {
  // Apply SiPM saturation per sensor before persisting.
  for (int i = 0; i < kNSensors; ++i) {
    data_.pe_saturated[i] = ApplySaturation(static_cast<double>(data_.n_detected[i]));
  }
  // Report SiPM arrivals collected (SIPM-P1-001) for test verification.
  long n_arrivals = 0;
  for (int i = 0; i < kNSensors; ++i)
    n_arrivals += static_cast<long>(data_.sipm_arrivals[i].size());
  if (n_arrivals > 0) {
    std::cout << "SIPM_ARRIVALS event=" << event->GetEventID()
              << " total=" << n_arrivals << std::endl;
  }

  if (run_action_) run_action_->FillEvent(data_, event->GetEventID());
}
