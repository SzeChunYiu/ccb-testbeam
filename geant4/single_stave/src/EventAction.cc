#include "EventAction.hh"
#include "RunAction.hh"
#include "SimData.hh"

#include "G4Event.hh"
#include "G4SystemOfUnits.hh"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <stdexcept>

#include "ccb/sipm/ResponseSimulator.hh"  // SIPM-P1-002
#include <iostream>

EventAction::EventAction(const AppConfig& cfg, RunAction* run_action)
    : cfg_(cfg), run_action_(run_action) {
  try {
    sipm_config_ = BuildSipmConfig();
  } catch (const std::exception& e) {
    std::cerr << "warning: SiPM core config invalid (" << e.what()
              << "); ADC output will be zero. Check env overrides." << std::endl;
  }
}

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

  // Run the ccb-sipm-core ResponseSimulator per sensor (SIPM-P1-002).
  // Feeds the collected boundary arrivals into the microcell response model
  // and records the peak ADC above baseline.
  const std::uint64_t event_id = static_cast<std::uint64_t>(event->GetEventID());
  bool has_adc = false;
  try {
    for (int sid = 0; sid < kNSensors; ++sid) {
      if (data_.sipm_arrivals[sid].empty()) {
        data_.adc[sid] = 0.0;
        continue;
      }
      // Copy base config and set sensor_id so simulate() filters correctly.
      auto cfg = sipm_config_;
      cfg.sensor_id = sid;
      ccb::sipm::ResponseSimulator sipm(cfg);
      auto result = sipm.simulate(data_.sipm_arrivals[sid], cfg_.seed,
                                  event_id);
      // Peak ADC above baseline (signal amplitude in ADC counts).
      if (!result.waveform.adc.empty()) {
        int peak_raw = *std::max_element(result.waveform.adc.begin(),
                                          result.waveform.adc.end());
        data_.adc[sid] = static_cast<double>(peak_raw) - cfg.baseline_adc;
      } else {
        data_.adc[sid] = 0.0;
      }
      if (data_.adc[sid] > 0.5) has_adc = true;
    }
  } catch (const std::exception& e) {
    std::cerr << "warning: SiPM core error at event " << event_id
              << ": " << e.what() << std::endl;
  }
  if (has_adc) {
    std::cout << "SIPM_ADC event=" << event->GetEventID()
              << " readout=" << data_.adc[kReadout]
              << " f1far=" << data_.adc[kF1Far]
              << " f2near=" << data_.adc[kF2Near]
              << " f2far=" << data_.adc[kF2Far]
              << std::endl;
  }

  if (run_action_) run_action_->FillEvent(data_, event->GetEventID());
}

ccb::sipm::ModelConfig EventAction::BuildSipmConfig() const {
  // Start from the published representative parameters (no magic numbers here).
  auto c = ccb::sipm::ModelConfig::RepresentativeS13360_3050CS();
  // Wire the Geant4-side systematic knobs into the core config.
  c.pde_scale = cfg_.pde_scale;
  c.coupling_efficiency = cfg_.coupling_efficiency;
  // Env overrides for core-specific parameters (all optional, all default
  // to the representative spec).
  auto getenv_d = [](const char* name, double& out) {
    if (const char* e = std::getenv(name)) {
      double v = std::strtod(e, nullptr);
      if (std::isfinite(v) && v > 0) out = v;
    }
  };
  getenv_d("CCB_SIPM_RECOVERY_TIME_NS", c.recovery_time_ns);
  getenv_d("CCB_SIPM_DARK_COUNT_RATE_HZ", c.dark_count_rate_hz);
  getenv_d("CCB_SIPM_WINDOW_END_NS", c.window_end_ns);
  getenv_d("CCB_SIPM_SAMPLE_DT_NS", c.sample_dt_ns);
  getenv_d("CCB_SIPM_CROSSTALK_PROB", c.prompt_crosstalk_probability);
  getenv_d("CCB_SIPM_AFTERPULSE_FAST_PROB", c.afterpulse_fast_probability);
  if (const char* e = std::getenv("CCB_SIPM_NO_DARK")) {
    c.enable_dark_counts = !(std::strcmp(e, "1") == 0);
  }
  c.validate();
  return c;
}
