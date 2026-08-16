#include "AppConfig.hh"
#include "NeutronTimecutPolicy.hh"

#include <cerrno>
#include <climits>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <sstream>

namespace {
bool eq(const char* a, const char* b) { return std::strcmp(a, b) == 0; }

// Checked double parse: rejects empty input, trailing garbage, errno range
// errors, and non-finite results (inf/nan).  Returns true on success.
bool parse_double(const char* s, double& out) {
  if (s == nullptr || *s == '\0') return false;
  errno = 0;
  char* end = nullptr;
  double val = std::strtod(s, &end);
  if (errno == ERANGE) return false;
  if (end == s || *end != '\0') return false;  // empty parse or trailing junk
  if (!std::isfinite(val)) return false;
  out = val;
  return true;
}

// Checked integer parse: rejects empty input, trailing garbage, errno range
// errors, and values outside [INT_MIN, INT_MAX].  Returns true on success.
bool parse_int(const char* s, int& out) {
  if (s == nullptr || *s == '\0') return false;
  errno = 0;
  char* end = nullptr;
  long val = std::strtol(s, &end, 10);
  if (errno == ERANGE) return false;
  if (end == s || *end != '\0') return false;  // empty parse or trailing junk
  if (val < INT_MIN || val > INT_MAX) return false;
  out = static_cast<int>(val);
  return true;
}

// Checked unsigned-64 parse: rejects empty input, trailing garbage, errno
// range errors, and negative values.  Returns true on success.
bool parse_ull(const char* s, unsigned long long& out) {
  if (s == nullptr || *s == '\0') return false;
  errno = 0;
  char* end = nullptr;
  // Reject a leading sign: strtoull silently wraps negatives, which is not
  // meaningful for a seed.
  if (*s == '-' || *s == '+') return false;
  unsigned long long val = std::strtoull(s, &end, 10);
  if (errno == ERANGE) return false;
  if (end == s || *end != '\0') return false;  // empty parse or trailing junk
  out = val;
  return true;
}
}  // namespace

void AppConfig::PrintUsage(const char* prog) {
  std::cout <<
    "Usage: " << prog << " [options]\n"
    "  CCB single-stave optical simulation (issue #796).\n\n"
    "  --particle NAME          proton|deuteron            (default proton)\n"
    "  --energy MEV             primary kinetic energy MeV  (default 100)\n"
    "  --nevents N              events this invocation      (default 1000)\n"
    "  --threads N              worker threads              (default 1)\n"
    "  --sipm-n-cells N        SiPM microcells (saturation) (default 3600)\n"
    "  --seed N                 RNG seed                    (default 1)\n"
    "  --hit-x CM               impact x (stave length)     (default 0)\n"
    "  --hit-y CM               impact y (width)            (default 0)\n"
    "  --theta DEG              polar tilt from +z          (default 0)\n"
    "  --phi DEG                azimuth of tilt             (default 0)\n"
    "  --allow-miss             permit primaries that miss the stave (#999)\n"
    "  --birks-kB VAL           Birks kB [mm/MeV]           (default 0.126)\n"
    "  --production-cut MM      secondary-production range threshold [mm]\n"
    "                           (default 0.1; gamma/e-/e+/p, NOT optical tracking)\n"
    "  --physics-list NAME     Geant4 reference physics list (REQUIRED;\n"
    "                           e.g. QGSP_BIC). No silent default (#1006)\n"
    "  --neutron-timecut-policy-id ID  Neutron tracking-time policy (REQUIRED;\n"
    "                           issue #1091 / ADR-0005)\n"
    "  --neutron-diagnostics    record neutron_steps ntuple: per-step neutron\n"
    "                           records + late (>1 us) scintillator deposits\n"
    "                           (#1091 ladder; validation runs only)\n"
    "  --reflectivity-scale V   TiO2 reflectivity scale     (default 1.0)\n"
    "  --attenuation-scale V    DEPRECATED — use --scintillator-absorption-scale\n"
    "                           and --y11-bulk-attenuation-scale instead.\n"
    "  --scintillator-absorption-scale V  scales scintillator self-absorption  (default 1.0)\n"
    "  --y11-bulk-attenuation-scale V     scales Y-11 bulk attenuation length  (default 1.0)\n"
    "  --pde-scale V            SiPM PDE scale              (default 1.0)\n"
    "  --collection-efficiency V  post-transport collection    (default 1.0)\n"
	    "  --optical-interface-model M  dry_butt|grease|epoxy|bonded|windowed\n"
	    "                               (default UNKNOWN_EXTERNAL)\n"
    "  --far-end MODE           absorb|open|mirror|instrumented (default instrumented)\n"
    "  --wls-time-profile P     exponential|delta           (default exponential)\n"
    "  --wls-fluorescence-model M  geant4_default_one_secondary|geant4_poisson_mean|bernoulli_thinned\n"
    "                               (default geant4_default_one_secondary)\n"
    "  --wls-fluorescence-yield Q  Bernoulli re-emission q for bernoulli_thinned (default 0.70)\n"
    "  --wls-mean-number-photons MU  Poisson mean for geant4_poisson_mean (default 1.0)\n"
    "  --mode MODE              optical                     (default; fast kernel not yet implemented)\n"
    "  --optical-dir DIR        optical CSV table directory (default optical)\n"
    "  --strict-optical         abort if required optical tables are missing/malformed (or CCB_STRICT_OPTICAL=1)\n"
    "  --output FILE            ntuple output (.root)       (default ccb_stave.root)\n"
    "  --macro FILE             run a macro then exit\n"
    "  --gpu-optical            GPU optical path: emit Opticks input photons,\n"
    "                           skip CPU optical transport (env CCB_GPU_OPTICAL=1)\n"
    "  --optical-out DIR        dir for per-event input-photon .npy\n"
    "                           (default: alongside --output)\n"
    "  --dump-gdml FILE         write production geometry to GDML and exit\n"
    "  -h, --help               this message\n";
}

std::string AppConfig::Describe() const {
  std::ostringstream os;
  os << "particle=" << particle
     << " KE_MeV=" << kinetic_energy_MeV
     << " nevents=" << n_events
     << " threads_requested=" << n_threads
     << " threads_effective=" << n_threads_effective
     << " g4_force_threads="
     << (g4_force_number_of_threads.empty() ? "unset" : g4_force_number_of_threads)
     << " seed=" << seed
     << " hit_x_cm=" << hit_x_cm
     << " hit_y_cm=" << hit_y_cm
     << " theta_deg=" << theta_deg
     << " phi_deg=" << phi_deg
     << " allow_miss=" << (allow_miss ? 1 : 0)
     << " birks_kB=" << birks_kB_mm_per_MeV
    << " quenching_model_id=" << quenching_model_id
    << " quenching_model_status=" << quenching_model_status
    << " quenching_claims_authorized=" << (quenching_claims_authorized ? "true" : "false")
     << " production_cut_mm=" << production_cut_mm
     << " physics_list=" << (physics_list.empty() ? "UNSET" : physics_list)
     << " neutron_timecut_policy_id=" << (neutron_timecut_policy_id.empty() ? "UNSET" : neutron_timecut_policy_id)
     << " neutron_time_cut_us=" << neutron_time_cut_us
     << " neutron_tracking_time_cut_configured=" << (neutron_tracking_time_cut_configured ? 1 : 0)
     << " neutron_diagnostics=" << (neutron_diagnostics ? 1 : 0)
     << " reflectivity_scale=" << reflectivity_scale
     << " attenuation_scale(deprecated)=" << attenuation_scale
     << " scintillator_absorption_scale=" << scintillator_absorption_scale
     << " y11_bulk_attenuation_scale=" << y11_bulk_attenuation_scale
     << " pde_scale=" << pde_scale
     << " collection_efficiency=" << collection_efficiency
	     << " optical_interface_model=" << optical_interface_model
     << " far_end=" << far_end_mode
     << " wls_time_profile=" << wls_time_profile
     << " wls_fluorescence_model=" << wls_fluorescence_model
     << " wls_fluorescence_yield=" << wls_fluorescence_yield
     << " mode=" << (mode == SimMode::kOpticalCalibration ? "optical" : "fast")
     << " optical_dir=" << optical_dir
     << " strict_optical=" << (strict_optical ? 1 : 0)
     << " output=" << output
     << " gpu_optical=" << (gpu_optical ? 1 : 0)
     << " optical_out=" << optical_out
     << " dump_gdml=" << dump_gdml;
  return os.str();
}

bool AppConfig::ParseArgs(int argc, char** argv) {
  auto need = [&](int& i) -> const char* {
    if (i + 1 >= argc) {
      std::cerr << "error: missing value for " << argv[i] << "\n";
      return nullptr;
    }
    return argv[++i];
  };
  for (int i = 1; i < argc; ++i) {
    const char* a = argv[i];
    const char* v = nullptr;
    if (eq(a, "-h") || eq(a, "--help")) { PrintUsage(argv[0]); return false; }
    else if (eq(a, "--particle"))          { if(!(v=need(i)))return false; particle = v; }
    else if (eq(a, "--energy"))            { if(!(v=need(i)))return false; double t; if(!parse_double(v,t)){std::cerr<<"error: --energy requires a finite number, got '"<<v<<"'\n";return false;} kinetic_energy_MeV = t; }
    else if (eq(a, "--nevents"))           { if(!(v=need(i)))return false; int t; if(!parse_int(v,t)){std::cerr<<"error: --nevents requires an integer, got '"<<v<<"'\n";return false;} n_events = t; }
    else if (eq(a, "--threads"))           { if(!(v=need(i)))return false; int t; if(!parse_int(v,t)){std::cerr<<"error: --threads requires an integer, got '"<<v<<"'\n";return false;} n_threads = t; }
    else if (eq(a, "--sipm-n-cells"))           { if(!(v=need(i)))return false; int t; if(!parse_int(v,t)){std::cerr<<"error: --sipm-n-cells requires an integer, got '"<<v<<"'\n";return false;} sipm_n_cells = t; }
    else if (eq(a, "--seed"))              { if(!(v=need(i)))return false; unsigned long long t; if(!parse_ull(v,t)){std::cerr<<"error: --seed requires a non-negative integer, got '"<<v<<"'\n";return false;} seed = t; }
    else if (eq(a, "--hit-x"))             { if(!(v=need(i)))return false; double t; if(!parse_double(v,t)){std::cerr<<"error: --hit-x requires a finite number, got '"<<v<<"'\n";return false;} hit_x_cm = t; }
    else if (eq(a, "--hit-y"))             { if(!(v=need(i)))return false; double t; if(!parse_double(v,t)){std::cerr<<"error: --hit-y requires a finite number, got '"<<v<<"'\n";return false;} hit_y_cm = t; }
    else if (eq(a, "--theta"))             { if(!(v=need(i)))return false; double t; if(!parse_double(v,t)){std::cerr<<"error: --theta requires a finite number, got '"<<v<<"'\n";return false;} theta_deg = t; }
    else if (eq(a, "--phi"))               { if(!(v=need(i)))return false; double t; if(!parse_double(v,t)){std::cerr<<"error: --phi requires a finite number, got '"<<v<<"'\n";return false;} phi_deg = t; }
    else if (eq(a, "--allow-miss"))        { allow_miss = true; }
    else if (eq(a, "--birks-kB"))          { if(!(v=need(i)))return false; double t; if(!parse_double(v,t)){std::cerr<<"error: --birks-kB requires a finite number, got '"<<v<<"'\n";return false;} birks_kB_mm_per_MeV = t; }
    else if (eq(a, "--production-cut"))    { if(!(v=need(i)))return false; double t; if(!parse_double(v,t)){std::cerr<<"error: --production-cut requires a finite number, got '"<<v<<"'\n";return false;} production_cut_mm = t; }
    else if (eq(a, "--physics-list"))     { if(!(v=need(i)))return false; physics_list = v; }
    else if (eq(a, "--neutron-timecut-policy-id")) { if(!(v=need(i)))return false; neutron_timecut_policy_id = v; }
    else if (eq(a, "--neutron-diagnostics"))         { neutron_diagnostics = true; }
    else if (eq(a, "--reflectivity-scale")){ if(!(v=need(i)))return false; double t; if(!parse_double(v,t)){std::cerr<<"error: --reflectivity-scale requires a finite number, got '"<<v<<"'\n";return false;} reflectivity_scale = t; }
    else if (eq(a, "--attenuation-scale")) { if(!(v=need(i)))return false; double t; if(!parse_double(v,t)){std::cerr<<"error: --attenuation-scale requires a finite number, got '"<<v<<"'\n";return false;} attenuation_scale = t; scintillator_absorption_scale = t; y11_bulk_attenuation_scale = t; }
    else if (eq(a, "--scintillator-absorption-scale")) { if(!(v=need(i)))return false; double t; if(!parse_double(v,t)){std::cerr<<"error: --scintillator-absorption-scale requires a finite number, got '"<<v<<"'\n";return false;} scintillator_absorption_scale = t; }
    else if (eq(a, "--y11-bulk-attenuation-scale")) { if(!(v=need(i)))return false; double t; if(!parse_double(v,t)){std::cerr<<"error: --y11-bulk-attenuation-scale requires a finite number, got '"<<v<<"'\n";return false;} y11_bulk_attenuation_scale = t; }
    else if (eq(a, "--pde-scale"))         { if(!(v=need(i)))return false; double t; if(!parse_double(v,t)){std::cerr<<"error: --pde-scale requires a finite number, got '"<<v<<"'\n";return false;} pde_scale = t; }
    else if (eq(a, "--collection-efficiency")) { if(!(v=need(i)))return false; double t; if(!parse_double(v,t)){std::cerr<<"error: --collection-efficiency requires a finite number, got '"<<v<<"'\n";return false;} collection_efficiency = t; }
	    else if (eq(a, "--optical-interface-model")) { if(!(v=need(i)))return false; optical_interface_model = v; }
    else if (eq(a, "--far-end")) {
      if(!(v=need(i)))return false;
      if (eq(v, "absorb") || eq(v, "open") || eq(v, "mirror") || eq(v, "instrumented"))
        far_end_mode = v;
      else { std::cerr << "error: --far-end must be absorb|open|mirror|instrumented\n"; return false; }
    }
    else if (eq(a, "--wls-time-profile")) {
      if(!(v=need(i)))return false;
      if (eq(v, "exponential")) wls_time_profile = "exponential";
      else if (eq(v, "delta")) wls_time_profile = "delta";
      else { std::cerr << "error: --wls-time-profile must be exponential|delta\n"; return false; }
    }
    else if (eq(a, "--wls-fluorescence-model")) {
      if(!(v=need(i)))return false;
      if (eq(v, "geant4_default_one_secondary") || eq(v, "geant4_poisson_mean") ||
          eq(v, "bernoulli_thinned"))
        wls_fluorescence_model = v;
      else { std::cerr << "error: --wls-fluorescence-model must be geant4_default_one_secondary|geant4_poisson_mean|bernoulli_thinned\n"; return false; }
    }
    else if (eq(a, "--wls-fluorescence-yield")) { if(!(v=need(i)))return false; double t; if(!parse_double(v,t)){std::cerr<<"error: --wls-fluorescence-yield requires a finite number, got '"<<v<<"'\n";return false;} wls_fluorescence_yield = t; }
    else if (eq(a, "--wls-mean-number-photons")) { if(!(v=need(i)))return false; double t; if(!parse_double(v,t)){std::cerr<<"error: --wls-mean-number-photons requires a finite number, got '"<<v<<"'\n";return false;} wls_mean_number_photons = t; }
    else if (eq(a, "--mode")) {
      if(!(v=need(i)))return false;
      if (eq(v, "optical")) mode = SimMode::kOpticalCalibration;
      else if (eq(v, "fast")) {
        std::cerr << "error: --mode fast (response kernel) is not implemented yet;"
                     " use --mode optical (kernel tracked as validation step 7).\n";
        return false;
      }
      else { std::cerr << "error: --mode must be optical|fast\n"; return false; }
    }
    else if (eq(a, "--optical-dir")) { if(!(v=need(i)))return false; optical_dir = v; }
    else if (eq(a, "--strict-optical")) { strict_optical = true; }
    else if (eq(a, "--output"))      { if(!(v=need(i)))return false; output = v; }
    else if (eq(a, "--macro"))       { if(!(v=need(i)))return false; macro = v; }
    else if (eq(a, "--gpu-optical")) { gpu_optical = true; }
    else if (eq(a, "--optical-out")) { if(!(v=need(i)))return false; optical_out = v; }
    else if (eq(a, "--dump-gdml"))   { if(!(v=need(i)))return false; dump_gdml = v; }
    else {
      std::cerr << "error: unknown argument '" << a << "'\n";
      PrintUsage(argv[0]);
      return false;
    }
  }
  // Env override: CCB_GPU_OPTICAL=1 enables the GPU optical path (factory flag).
  const char* gpu_env = std::getenv("CCB_GPU_OPTICAL");
  if (gpu_env && (eq(gpu_env, "1") || eq(gpu_env, "true") || eq(gpu_env, "yes")))
    gpu_optical = true;

  // --- validation ---
  if (particle != "proton" && particle != "deuteron") {
    std::cerr << "error: --particle must be proton|deuteron\n"; return false;
  }
  if (kinetic_energy_MeV <= 0) { std::cerr << "error: --energy must be > 0\n"; return false; }
  if (n_events <= 0)           { std::cerr << "error: --nevents must be > 0\n"; return false; }
  if (n_threads <= 0)          { std::cerr << "error: --threads must be > 0\n"; return false; }
  if (sipm_n_cells <= 0)      { std::cerr << "error: --sipm-n-cells must be > 0\n"; return false; }
  if (collection_efficiency < 0 || collection_efficiency > 1) {
    std::cerr << "error: --collection-efficiency must be in [0,1]\n"; return false;
  }
  // WLS fluorescence multiplicity contract (#1088): fail-closed mode/parameter
  // validation, and derive the status tag from the selected mode so run
  // metadata can never disagree with the actual multiplicity mechanism.
  if (wls_fluorescence_model != "geant4_default_one_secondary" &&
      wls_fluorescence_model != "geant4_poisson_mean" &&
      wls_fluorescence_model != "bernoulli_thinned") {
    std::cerr << "error: --wls-fluorescence-model must be geant4_default_one_secondary|geant4_poisson_mean|bernoulli_thinned\n";
    return false;
  }
  if (wls_fluorescence_model == "geant4_poisson_mean") {
    if (wls_mean_number_photons <= 0) {
      std::cerr << "error: --wls-mean-number-photons must be > 0 for geant4_poisson_mean\n";
      return false;
    }
    wls_fluorescence_status = "EXPLICIT_POISSON_MEAN";
  } else if (wls_fluorescence_model == "bernoulli_thinned") {
    if (wls_fluorescence_yield < 0.0 || wls_fluorescence_yield > 1.0) {
      std::cerr << "error: --wls-fluorescence-yield must be in [0,1] for bernoulli_thinned\n";
      return false;
    }
    wls_fluorescence_status = "EXTERNAL_QE_PRIOR";
  }
  if (pde_scale < 0 || reflectivity_scale < 0 || attenuation_scale < 0 ||
      scintillator_absorption_scale < 0 || y11_bulk_attenuation_scale < 0) {
    std::cerr << "error: scale factors must be >= 0\n"; return false;
  }
  if (production_cut_mm <= 0) { std::cerr << "error: --production-cut must be > 0\n"; return false; }
  if (physics_list.empty()) {
    std::cerr << "error: --physics-list is required (issue #1006 fail-closed; "
                 "no silent QGSP_BIC default)\n";
    return false;
  }
  {
    NeutronTimecutPolicy policy;
    std::string policy_error;
    if (!NeutronTimecutPolicy::Resolve(neutron_timecut_policy_id, policy,
                                       policy_error)) {
      std::cerr << "error: " << policy_error << "\n";
      return false;
    }
    neutron_time_cut_us = policy.time_cut_us;
    neutron_tracking_time_cut_status = policy.status;
    neutron_timecut_adr = policy.adr;
    neutron_timecut_claims_authorized = policy.claims_authorized;
    neutron_tracking_time_cut_configured = true;
  }
  // G4-003: env override for strict optical-table validation (production).
  if (!strict_optical) {
    if (const char* e = std::getenv("CCB_STRICT_OPTICAL")) {
      strict_optical = (std::strcmp(e, "1") == 0 || std::strcmp(e, "true") == 0 ||
                        std::strcmp(e, "TRUE") == 0 || std::strcmp(e, "yes") == 0);
    }
  }
  return true;
}
