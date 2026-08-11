// AppConfig.hh — CCB single-stave simulation configuration
// Issue #796. All run-time knobs live here; parsed from argv in main.cc and
// exposed to macros through DetectorMessenger. Every field is written into the
// output metadata so a run is fully reproducible.
#ifndef CCB_APPCONFIG_HH
#define CCB_APPCONFIG_HH

#include <string>
#include <cstdint>

// Simulation mode.
//  - kOpticalCalibration: full optical transport, modest statistics, keeps
//    per-photon arrival wavelength/time. Used to derive the response kernel.
//  - kFastKernel: optical transport disabled downstream (kernel applied by the
//    analysis layer). The executable still records Edep / track length so the
//    analysis can apply a pre-derived response model.
enum class SimMode { kOpticalCalibration, kFastKernel };

struct AppConfig {
  // --- Primary beam ---
  std::string particle = "proton";   // "proton" | "deuteron"
  double kinetic_energy_MeV = 100.0; // primary kinetic energy
  int    n_events = 1000;            // events for this invocation

  // --- Execution ---
  // Requested value comes from the CLI. Effective value is read back from the
  // constructed run manager because G4FORCENUMBEROFTHREADS may override it.
  int    n_threads = 1;
  int    n_threads_effective = 1;
  std::string g4_force_number_of_threads = "";

  // --- Incidence (detector-local, see DetectorConstruction coordinate note) ---
  // Normal incidence: primary launched at (hit_x, hit_y, z = -half_z - eps),
  // direction (0,0,+1). theta/phi tilt the direction away from +z.
  double hit_x_cm = 0.0;   // impact point along stave length x
  double hit_y_cm = 0.0;   // impact point along width y
  double theta_deg = 0.0;  // polar tilt from +z
  double phi_deg   = 0.0;  // azimuth of the tilt
  // Issue #999 / ADR-0003: intentional miss studies only.
  bool allow_miss = false;  // --allow-miss; default rejects non-intersecting primaries

  // --- Detector / optical systematics knobs (multiplicative unless noted) ---
  double birks_kB_mm_per_MeV = 0.126; // Birks constant kB [mm/MeV] (Edep scan var)
  // Secondary-production range threshold [mm] (issue #1089). Controls Geant4
  // production of gamma/e-/e+/proton secondaries — NOT optical-photon tracking.
  // Coupled to Birks: changing it alters the explicit delta-ray population and
  // thus the fitted kB (the "cut x kB coupling").
  double production_cut_mm = 0.1;
  double reflectivity_scale = 1.0;    // scales the TiO2 reflectivity table
  double attenuation_scale  = 1.0;    // DEPRECATED: use scintillator_absorption_scale
                                       //   and y11_bulk_attenuation_scale instead.
                                       //   Kept for legacy config compatibility;
                                       //   affects both when the new fields are
                                       //   at their default (1.0).
  double scintillator_absorption_scale = 1.0; // scales scintillator self-absorption length
  double y11_bulk_attenuation_scale    = 1.0; // scales Y-11 bulk attenuation length
  double pde_scale          = 1.0;    // scales the SiPM PDE table
  // Fibre-end-face -> sensor optical interface model (issue #1083).
  // UNKNOWN_EXTERNAL = the physical end-face construction has not been
  // recovered from hardware evidence; the hard-coded 10 um world-air gap
  // and Y-11-core sensor placeholder are acknowledged placeholders.
  // Future values: dry_butt, grease, epoxy, bonded, windowed.
  std::string optical_interface_model = "UNKNOWN_EXTERNAL";

  // Post-transport collection efficiency [0,1] (separate from the optical
  // interface model above). Applied after the photon has crossed the
  // sensor boundary: P_det = PDE(lambda) * collection_efficiency.  This
  // scalar is NOT equivalent to the unresolved end-face interface and
  // cannot substitute for it (see issue #1083, H1-H6).
  double collection_efficiency = 1.0;

  std::string far_end_mode = "instrumented";  // absorb|open|mirror|instrumented (SIPM-P0-002)

  // --- Provenance / reproducibility ---
  std::uint64_t seed = 1;             // primary RNG seed
  SimMode mode = SimMode::kOpticalCalibration;

  // --- Optical input tables (versioned CSV, path recorded + hashed) ---
  std::string optical_dir = "optical";

  // --- Optical validation mode (G4-003) ---
  // false (default, dev): missing/malformed optical tables warn and fall back
  // to built-in constants (historic fail-open). true (production): missing
  // required tables or schema/unit/range violations abort the run BEFORE the
  // event loop. Enabled by --strict-optical or env CCB_STRICT_OPTICAL=1.
  bool strict_optical = false;

  // --- I/O ---
  std::string output = "ccb_stave.root"; // ntuple output (ROOT via g4tools)
  std::string macro  = "";                // optional macro to /control/execute

  // --- Optional GPU optical path (Opticks) ---
  // When enabled, optical-photon secondaries from the Geant4 Scintillation
  // process (authoritative yield/spectrum/positioning) are captured and
  // emitted as Opticks "input photon" arrays (.npy, sphoton layout) for GPU
  // transport; CPU optical-photon tracking is suppressed (proton-only, fast).
  // The CPU reference (flag OFF) is byte-for-byte unchanged. Also env
  // CCB_GPU_OPTICAL=1. Default OFF.
  bool   gpu_optical = false;             // --gpu-optical / CCB_GPU_OPTICAL=1
  std::string optical_out = "";           // dir for per-event input-photon npy
  std::string dump_gdml = "";             // write production geometry to GDML
                                          //  after Initialize, then exit

  // --- Sensor spec (Hamamatsu S13360-3050CS public spec) ---
  int    sipm_n_cells = 3600;   // microcells (saturation model)
  double sipm_overvoltage_V = 3.0; // recorded; PDE table is OV-tagged
  std::string wls_time_profile = "exponential"; // WLS delay profile: exponential|delta (SIPM-P0-001)

  // Parse argv. Returns false on --help or a parse error (prints usage).
  bool ParseArgs(int argc, char** argv);
  // Human-readable dump written to stdout and into the output metadata.
  std::string Describe() const;
  static void PrintUsage(const char* prog);
};

#endif  // CCB_APPCONFIG_HH
