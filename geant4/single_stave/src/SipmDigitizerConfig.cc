#include "SipmDigitizerConfig.hh"

#include <cerrno>
#include <cctype>
#include <cmath>
#include <cstdlib>
#include <limits>
#include <stdexcept>
#include <string>

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


void ApplyOptionalEnvString(const char* name, std::string& out) {
  const char* raw = std::getenv(name);
  if (raw == nullptr) return;
  const std::string value(raw);
  if (value.empty()) {
    throw std::invalid_argument(std::string("invalid empty ") + name);
  }
  for (unsigned char ch : value) {
    if (std::isspace(ch)) {
      throw std::invalid_argument(std::string("invalid ") + name + "='" + raw + "'");
    }
  }
  out = value;
}

void RejectImmutableOperatingPointOverride(const char* name, double expected) {
  if (std::getenv(name) == nullptr) return;
  const double requested = ParseRequiredEnvDouble(
      name, -std::numeric_limits<double>::infinity(), true,
      std::numeric_limits<double>::infinity(), true);
  if (requested != expected) {
    throw std::invalid_argument(
        std::string(name) + " override is not supported: the representative "
        "profile physics is fixed at " + std::to_string(expected) +
        " (requested " + std::to_string(requested) + "). "
        "Overvoltage/temperature currently change provenance only; "
        "see ADR-SIPM-OPERATING-POINT-H1 / issue #1072.");
  }
}

void ApplySipmCellCount(ccb::sipm::ModelConfig& c, int n_cells) {
  if (n_cells <= 0) {
    throw std::invalid_argument("--sipm-n-cells must be > 0");
  }
  const int side = static_cast<int>(std::lround(std::sqrt(static_cast<double>(n_cells))));
  if (side <= 0 || side * side != n_cells) {
    throw std::invalid_argument(
        "--sipm-n-cells=" + std::to_string(n_cells) +
        " is not a perfect square; ccb-sipm-core requires an explicit "
        "cells_x × cells_y grid (issue #974). Use 1600,2500,3600,4900,6400.");
  }
  c.cells_x = side;
  c.cells_y = side;
}

}  // namespace

ccb::sipm::ModelConfig BuildSipmDigitizerConfig(const AppConfig& cfg,
                                                const OpticalTables& tables) {
  auto c = ccb::sipm::ModelConfig::RepresentativeS13360_3050CS();
  ApplySipmCellCount(c, cfg.sipm_n_cells);

  if (!tables.Has("sipm_pde") || tables.Get("sipm_pde").Empty()) {
    throw std::runtime_error(
        "sipm_pde optical table missing/empty; cannot build digitizer config");
  }
  {
    const auto& curve = tables.Get("sipm_pde");
    c.pde_curve.clear();
    c.pde_curve.reserve(curve.x.size());
    for (size_t i = 0; i < curve.x.size(); ++i) {
      c.pde_curve.push_back({curve.x[i], curve.y[i]});
    }
  }

  c.pde_scale = cfg.pde_scale;
  c.coupling_efficiency = cfg.collection_efficiency;

  ApplyOptionalEnvDouble("CCB_SIPM_WINDOW_START_NS", c.window_start_ns);
  ApplyOptionalEnvDouble("CCB_SIPM_WINDOW_END_NS", c.window_end_ns);
  ApplyOptionalEnvDouble("CCB_SIPM_HISTORY_START_NS", c.history_start_ns);
  ApplyOptionalEnvDouble("CCB_SIPM_SAMPLE_DT_NS", c.sample_dt_ns, 0.0, false);
  ApplyOptionalEnvInt("CCB_SIPM_SHAPER_STAGES", c.shaper_integrator_stages, 1, 6);
  ApplyOptionalEnvDouble("CCB_SIPM_SHAPER_TAU_NS", c.pulse_decay_ns, 0.0, false);
  ApplyOptionalEnvDouble("CCB_SIPM_SHAPER_EXTRA_TAU_NS",
                         c.shaper_extra_stage_tau_ns, 0.0, false);
  ApplyOptionalEnvInt("CCB_SIPM_ADC_BITS", c.adc_bits, 1, 30);
  ApplyOptionalEnvDouble("CCB_SIPM_ADC_LSB_PE", c.adc_lsb_pe, 0.0, false);
  ApplyOptionalEnvDouble("CCB_SIPM_BASELINE_ADC", c.baseline_adc);
  ApplyOptionalEnvDouble("CCB_SIPM_PDE_SCALE", c.pde_scale, 0.0, true);

  RejectImmutableOperatingPointOverride(
      "CCB_SIPM_OVERVOLTAGE_V", c.device_provenance.overvoltage_V);
  RejectImmutableOperatingPointOverride(
      "CCB_SIPM_TEMPERATURE_C", c.device_provenance.temperature_C);

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

  // Dual recovery-law selectors from ccb-sipm-core@cf12c6b (#1066 env surface).
  // Unknown tokens fail closed in ModelConfig::validate().
  ApplyOptionalEnvString("CCB_SIPM_TRIGGER_RECOVERY_MODEL", c.trigger_recovery_model);
  ApplyOptionalEnvString("CCB_SIPM_GAIN_RECOVERY_MODEL", c.gain_recovery_model);

  if (std::getenv("CCB_SIPM_NO_DARK") != nullptr) {
    c.enable_dark_counts = !ParseStrictEnvBool("CCB_SIPM_NO_DARK", false);
  }
  if (std::getenv("CCB_SIPM_MAX_CANDIDATES") != nullptr) {
    const int v = ParseRequiredEnvInt("CCB_SIPM_MAX_CANDIDATES", 1,
                                      std::numeric_limits<int>::max());
    c.max_candidates = static_cast<std::size_t>(v);
  }

  c.validate();
  return c;
}
