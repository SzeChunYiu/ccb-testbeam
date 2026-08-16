#include "EventAction.hh"
#include "RunAction.hh"
#include "SimData.hh"
#include "SipmDigitizerConfig.hh"

#include "G4Event.hh"
#include "G4SystemOfUnits.hh"

#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string>

#include "ccb/sipm/ResponseSimulator.hh"  // SIPM-P1-002

EventAction::EventAction(const AppConfig& cfg, const OpticalTables& tables,
                         RunAction* run_action)
    : cfg_(cfg), tables_(tables), run_action_(run_action) {
  // Scientific production is fail-closed: an invalid detector-response model
  // must abort before event 0 rather than masquerade as a dead/zero-ADC sensor.
  sipm_config_ = BuildSipmDigitizerConfig(cfg_, tables_);
  if (run_action_) {
    run_action_->SetSipmDigitizerConfig(sipm_config_);
  }
  std::cout << "SIPM_CONFIG"
            << " cells=" << sipm_config_.number_of_cells()
            << " cells_x=" << sipm_config_.cells_x
            << " cells_y=" << sipm_config_.cells_y
            << " active_mm=" << sipm_config_.active_width_mm << "x"
            << sipm_config_.active_height_mm
            << " recovery_ns=" << sipm_config_.recovery_time_ns
            << " dcr_hz=" << sipm_config_.dark_count_rate_hz
            << " dark_enabled=" << (sipm_config_.enable_dark_counts ? 1 : 0)
            << " crosstalk=" << sipm_config_.prompt_crosstalk_probability
            << " afterpulse_fast=" << sipm_config_.afterpulse_fast_probability
            << " window_start_ns=" << sipm_config_.window_start_ns
            << " window_end_ns=" << sipm_config_.window_end_ns
            << " sample_dt_ns=" << sipm_config_.sample_dt_ns
            << " adc_bits=" << sipm_config_.adc_bits
            << " adc_lsb_pe=" << sipm_config_.adc_lsb_pe
            << " baseline_adc=" << sipm_config_.baseline_adc
            << " overvoltage_V=" << sipm_config_.device_provenance.overvoltage_V
            << " temperature_C=" << sipm_config_.device_provenance.temperature_C
            << " trigger_recovery_model=" << sipm_config_.trigger_recovery_model
            << " gain_recovery_model=" << sipm_config_.gain_recovery_model
            << std::endl;
}

void EventAction::BeginOfEventAction(const G4Event*) { data_.Reset(); }

double EventAction::ApplySaturation(double n_pe) const {
  // Legacy diagnostic estimator only (#1084). Production ADC uses the core.
  const double ncell = static_cast<double>(cfg_.sipm_n_cells);
  if (ncell <= 0) return n_pe;
  return ncell * (1.0 - std::exp(-n_pe / ncell));
}

void EventAction::EndOfEventAction(const G4Event* event) {
  // Legacy independent PE/saturation diagnostic (#1084 H2).
  for (int i = 0; i < kNSensors; ++i) {
    data_.pe_saturated[i] = ApplySaturation(static_cast<double>(data_.n_detected[i]));
  }
  long n_arrivals = 0;
  for (int i = 0; i < kNSensors; ++i)
    n_arrivals += static_cast<long>(data_.sipm_arrivals[i].size());
  if (n_arrivals > 0) {
    std::cout << "SIPM_ARRIVALS event=" << event->GetEventID()
              << " total=" << n_arrivals << std::endl;
  }

  const std::uint64_t event_id = static_cast<std::uint64_t>(event->GetEventID());
  bool has_adc = false;
  for (int sid = 0; sid < kNSensors; ++sid) {
    auto cfg = sipm_config_;
    cfg.sensor_id = sid;
    ccb::sipm::ResponseSimulator sipm(cfg);
    auto result = sipm.simulate(data_.sipm_arrivals[sid], cfg_.seed, event_id);
    if (run_action_) {
      run_action_->NoteSipmEventDiagnostics(result.candidate_limit_reached,
                                            result.n_candidates_processed);
    }
    if (result.candidate_limit_reached) {
      throw std::runtime_error(
          "SiPM candidate_limit_reached=true for sensor " + std::to_string(sid) +
          " at event " + std::to_string(event->GetEventID()) +
          " (max_candidates=" + std::to_string(cfg.max_candidates) +
          ", n_candidates_processed=" +
          std::to_string(result.n_candidates_processed) +
          "). Run is non-authorising (issue #1069).");
    }
    if (!result.waveform.adc.empty()) {
      int peak_raw = *std::max_element(result.waveform.adc.begin(),
                                        result.waveform.adc.end());
      data_.adc[sid] = static_cast<double>(peak_raw) - cfg.baseline_adc;
    } else {
      data_.adc[sid] = 0.0;
    }
    if (data_.adc[sid] > 0.5) has_adc = true;
  }
  if (has_adc) {
    std::cout << "SIPM_ADC event=" << event->GetEventID()
              << " readout=" << data_.adc[kReadout]
              << " f1far=" << data_.adc[kF1Far]
              << " f2near=" << data_.adc[kF2Near]
              << " f2far=" << data_.adc[kF2Far]
              << std::endl;
  }

  if (run_action_) {
    run_action_->FillEvent(data_, event->GetEventID());
    if (cfg_.gpu_optical)
      run_action_->WriteGpuPhotons(data_, event->GetEventID());
    else if (!cfg_.optical_out.empty())
      run_action_->WriteCpuArrivals(data_, event->GetEventID());
  }
}

ccb::sipm::ModelConfig EventAction::BuildSipmConfig() const {
  return BuildSipmDigitizerConfig(cfg_, tables_);
}
