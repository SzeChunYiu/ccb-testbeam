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

  // Quenching model provenance (#1008): Birks form is a hypothesis until
  // material-specific validation closes the claim.
  std::string quenching_model_id = "birks_geant4";
  std::string quenching_model_status = "HYPOTHESIS";
  bool quenching_claims_authorized = false;
  // Secondary-production range threshold [mm] (issue #1089). Controls Geant4
  // production of gamma/e-/e+/proton secondaries — NOT optical-photon tracking.
  // Coupled to Birks: changing it alters the explicit delta-ray population and
  // thus the fitted kB (the "cut x kB coupling").
  double production_cut_mm = 0.1;
  // Hadronic/EM reference physics list (issue #1006). Empty means UNSET:
  // ParseArgs fails closed unless --physics-list is provided. Never
  // silently default to QGSP_BIC in scientific production.
  std::string physics_list = "";
  // Neutron tracking-time cut policy (#1091 / ADR-0005). Empty means UNSET:
  // ParseArgs fails closed unless --neutron-timecut-policy-id is provided.
  std::string neutron_timecut_policy_id = "";
  double neutron_time_cut_us = 0.0;
  bool neutron_tracking_time_cut_configured = false;
  std::string neutron_tracking_time_cut_status = "UNSET";
  std::string neutron_timecut_adr = "";
  bool neutron_timecut_claims_authorized = false;

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

  // --- Optical validation mode (issues #978/#980, G4-003) ---
  // Production default is STRICT (true): missing/malformed tables or unit/range
  // violations abort BEFORE event 0. Permissive fallback requires an explicit
  // --allow-optical-fallback (or CCB_ALLOW_OPTICAL_FALLBACK=1) and forces
  // authorising=false in run metadata.
  bool strict_optical = true;
  bool allow_optical_fallback = false;
  // authorising=false when fallback is enabled or any optical input fell back.
  bool authorising = true;
  bool optical_fallback_used = false;

  // Versioned constants ledger (#979) — path relative to CWD or absolute.
  std::string optical_constants_ledger = "optical/optical_constants_ledger.conf";

  // Material / coupling / WLS hypotheses (BLOCKED until hardware-sourced).
  // polystyrene_legacy = historic G4_POLYSTYRENE host (NOT verified BC-408).
  // vinyltoluene_pvt_hypothesis = G4_PLASTIC_SC_VINYLTOLUENE prior for BC-408 class.
  std::string scintillator_material = "polystyrene_legacy";
  std::string scintillator_material_status = "BLOCKED_UNVERIFIED_HARDWARE";
  // air_massless_placeholder | tio2_paint_hypothesis (#1005)
  std::string coating_material = "air_massless_placeholder";
  std::string coating_material_status = "BLOCKED_UNVERIFIED_HARDWARE";
  // WLS fluorescence multiplicity (#1088). Three mutually exclusive modes:
  //  geant4_default_one_secondary: WLSMEANNUMBERPHOTONS property ABSENT ->
  //    G4OpWLS re-emits exactly one secondary per absorption.
  //  geant4_poisson_mean: property set -> G4OpWLS samples Poisson(mu)
  //    secondaries per absorption (Geant4 11.2.2 samples Poisson whenever the
  //    property exists, even at mu=1: P(0)=0.368, P(>=2)=0.264).
  //  bernoulli_thinned: property absent; StackingAction kills each OpWLS
  //    re-emission with probability (1-q) -> Bernoulli(q) effective yield.
  double wls_mean_number_photons = 1.0;
  std::string wls_fluorescence_model = "geant4_default_one_secondary";
  std::string wls_fluorescence_status = "ASSUMPTION_UNIT_YIELD";
  // Bernoulli re-emission probability q for bernoulli_thinned. Y-11(K27)
  // quantum yield 0.70: Pla-Dalmau, Foster, Zhang, NIM A361 (1995) 192-196;
  // Bernoulli implementation precedent: Elpers et al., arXiv:1911.03790 sec. 4.
  double wls_fluorescence_yield = 0.70;
  // Direct Y-11 charged-particle light (#1035); 0 keeps current omission.
  double y11_direct_scint_yield_per_MeV = 0.0;
  std::string y11_direct_scint_status = "OMISSION_UNKNOWN_EXTERNAL";
  // Attenuation model-form tag (#1085)
  std::string y11_attenuation_form = "long_component_single_exponential";
  std::string y11_attenuation_form_status = "MANUFACTURER_LONG_COMPONENT_PRIOR";
  // TiO2 UNIFIED surface (#1086)
  std::string tio2_finish = "ground";
  double tio2_sigma_alpha = 0.1;
  double tio2_specular_lobe = 0.0;
  double tio2_specular_spike = 0.0;
  double tio2_backscatter = 0.0;
  std::string tio2_reflection_model_status = "EXPLICIT_LAMBERTIAN_HYPOTHESIS";
  // Scalar optical priors formerly hard-coded (#979)
  double scintillator_rindex = 1.59;
  double scintillation_yield_per_MeV = 10000.0;
  double scintillation_time_ns = 2.4;
  double y11_core_rindex = 1.59;
  double wls_time_constant_ns = 8.5;
  double clad_inner_rindex = 1.49;
  double clad_outer_rindex = 1.42;
  double coupling_grease_rindex = 1.46;
  double coupling_epoxy_rindex = 1.50;
  double tio2_paint_density_g_cm3 = 1.5;

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
