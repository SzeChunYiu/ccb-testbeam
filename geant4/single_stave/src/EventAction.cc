#include "EventAction.hh"
#include "RunAction.hh"
#include "SimData.hh"

#include "G4Event.hh"
#include "G4SystemOfUnits.hh"

#include <algorithm>
#include <cerrno>
#include <cctype>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

#include "ccb/sipm/ResponseSimulator.hh"  // SIPM-P1-002

namespace {

double ParseRequiredEnvDouble(const char* name,
                              double min_value,
                              bool min_inclusive,
                              double max_value,
                              bool max_inclusive) {
  const char* raw = std::getenv(name);
  if (raw == nullptr) {
    throw std::logic_error(std::string("ParseRequiredEnvDouble called for unset env ") + name);
  }

  errno = 0;
  char* end = nullptr;
  const double value = std::strtod(raw, &end);
  while (end != nullptr && *end != '\0' &&
         std::isspace(static_cast<unsigned char>(*end))) {
    ++end;
  }
  const bool min_ok = min_inclusive ? value >= min_value : value > min_value;
  const bool max_ok = max_inclusive ? value <= max_value : value < max_value;
  if (errno == ERANGE || end == raw || end == nullptr || *end != '\0' ||
      !std::isfinite(value) || !min_ok || !max_ok) {
    throw std::invalid_argument(std::string("invalid ") + name + "='" + raw + "'");
  }
  return value;
}

void ApplyOptionalEnvDouble(const char* name,
                            double& out,
                            double min_value = -std::numeric_limits<double>::infinity(),
                            bool min_inclusive = true,
                            double max_value = std::numeric_limits<double>::infinity(),
                            bool max_inclusive = true) {
  if (std::getenv(name) == nullptr) return;
  out = ParseRequiredEnvDouble(name, min_value, min_inclusive, max_value, max_inclusive);
}

int ParseRequiredEnvInt(const char* name, int min_value, int max_value) {
  const char* raw = std::getenv(name);
  if (raw == nullptr) {
    throw std::logic_error(std::string("ParseRequiredEnvInt called for unset env ") + name);
  }
  errno = 0;
  char* end = nullptr;
  const long value = std::strtol(raw, &end, 10);
  while (end != nullptr && *end != '\0' &&
         std::isspace(static_cast<unsigned char>(*end))) {
    ++end;
  }
  if (errno == ERANGE || end == raw || end == nullptr || *end != '\0' ||
      value < min_value || value > max_value) {
    throw std::invalid_argument(std::string("invalid ") + name + "='" + raw + "'");
  }
  return static_cast<int>(value);
}

void ApplyOptionalEnvInt(const char* name, int& out, int min_value, int max_value) {
  if (std::getenv(name) == nullptr) return;
  out = ParseRequiredEnvInt(name, min_value, max_value);
}

bool ParseStrictEnvBool(const char* name, bool default_value) {
  const char* raw = std::getenv(name);
  if (raw == nullptr) return default_value;
  const std::string value(raw);
  if (value == "1" || value == "true" || value == "TRUE" || value == "yes") return true;
  if (value == "0" || value == "false" || value == "FALSE" || value == "no") return false;
  throw std::invalid_argument(std::string("invalid boolean ") + name + "='" + raw + "'");
}

}  // namespace

EventAction::EventAction(const AppConfig& cfg, RunAction* run_action)
    : cfg_(cfg), run_action_(run_action) {
  // Scientific production is fail-closed: an invalid detector-response model
  // must abort before event 0 rather than masquerade as a dead/zero-ADC sensor.
  sipm_config_ = BuildSipmConfig();
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
  // Start from the published representative parameters.  They remain
  // manufacturer-representative priors, not a CCB device calibration.
  auto c = ccb::sipm::ModelConfig::RepresentativeS13360_3050CS();

  // Wire the Geant4-side systematic knobs into the core config.
  c.pde_scale = cfg_.pde_scale;
  c.coupling_efficiency = cfg_.coupling_efficiency;

  // Strictly parse every ccb-sipm-core environment override currently exposed
  // by the pinned core.  The core helper intentionally ignores malformed env
  // values; scientific production must instead surface them as configuration
  // errors so a typo cannot silently fall back to the representative default.
  ApplyOptionalEnvDouble("CCB_SIPM_WINDOW_START_NS", c.window_start_ns);
  ApplyOptionalEnvDouble("CCB_SIPM_WINDOW_END_NS", c.window_end_ns);
  ApplyOptionalEnvDouble("CCB_SIPM_SAMPLE_DT_NS", c.sample_dt_ns, 0.0, false);
  ApplyOptionalEnvInt("CCB_SIPM_SHAPER_STAGES", c.shaper_integrator_stages, 1, 6);
  ApplyOptionalEnvDouble("CCB_SIPM_SHAPER_TAU_NS", c.pulse_decay_ns, 0.0, false);
  ApplyOptionalEnvDouble("CCB_SIPM_SHAPER_EXTRA_TAU_NS",
                         c.shaper_extra_stage_tau_ns, 0.0, false);
  ApplyOptionalEnvInt("CCB_SIPM_ADC_BITS", c.adc_bits, 1, 30);
  ApplyOptionalEnvDouble("CCB_SIPM_ADC_LSB_PE", c.adc_lsb_pe, 0.0, false);
  ApplyOptionalEnvDouble("CCB_SIPM_BASELINE_ADC", c.baseline_adc);
  ApplyOptionalEnvDouble("CCB_SIPM_PDE_SCALE", c.pde_scale, 0.0, true);
  ApplyOptionalEnvDouble("CCB_SIPM_OVERVOLTAGE_V",
                         c.device_provenance.overvoltage_V);
  ApplyOptionalEnvDouble("CCB_SIPM_TEMPERATURE_C",
                         c.device_provenance.temperature_C);

  // Campaign-specific correlated-noise/recovery knobs.  Zero is deliberately
  // accepted for rates/probabilities so the documented zero-control points are
  // real controls rather than silent representative-default runs.
  ApplyOptionalEnvDouble("CCB_SIPM_RECOVERY_TIME_NS", c.recovery_time_ns,
                         0.0, false);
  ApplyOptionalEnvDouble("CCB_SIPM_DARK_COUNT_RATE_HZ", c.dark_count_rate_hz,
                         0.0, true);
  ApplyOptionalEnvDouble("CCB_SIPM_CROSSTALK_PROB",
                         c.prompt_crosstalk_probability,
                         0.0, true, 1.0, false);
  ApplyOptionalEnvDouble("CCB_SIPM_AFTERPULSE_FAST_PROB",
                         c.afterpulse_fast_probability,
                         0.0, true, 1.0, false);

  // CCB_SIPM_NO_DARK=1 means disabled; =0 means enabled.
  if (std::getenv("CCB_SIPM_NO_DARK") != nullptr) {
    c.enable_dark_counts = !ParseStrictEnvBool("CCB_SIPM_NO_DARK", false);
  }

  c.validate();
  return c;
}