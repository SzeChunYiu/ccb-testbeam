#include "AppConfig.hh"
#include "OpticalConstantsLedger.hh"

#include <cerrno>
#include <climits>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <fstream>
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
    "  --mode MODE              optical                     (default; fast kernel not yet implemented)\n"
    "  --optical-dir DIR        optical CSV table directory (default optical)\n"
    "  --strict-optical         fail-closed optical tables (DEFAULT)\n"
    "  --allow-optical-fallback  permissive tables; authorising=false\n"
    "  --optical-constants-ledger PATH  versioned constants ledger (#979)\n"
    "  --scintillator-material M polystyrene_legacy|vinyltoluene_pvt_hypothesis\n"
    "  --coating-material M     air_massless_placeholder|tio2_paint_hypothesis\n"
    "  --wls-mean-number-photons MU  Geant4 WLSMEANNUMBERPHOTONS (#1088)\n"
    "  --y11-direct-scint-yield Y  direct Y-11 scintillation yield/MeV (#1035)\n"
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
     << " production_cut_mm=" << production_cut_mm
     << " reflectivity_scale=" << reflectivity_scale
     << " attenuation_scale(deprecated)=" << attenuation_scale
     << " scintillator_absorption_scale=" << scintillator_absorption_scale
     << " y11_bulk_attenuation_scale=" << y11_bulk_attenuation_scale
     << " pde_scale=" << pde_scale
     << " collection_efficiency=" << collection_efficiency
	     << " optical_interface_model=" << optical_interface_model
     << " far_end=" << far_end_mode
     << " wls_time_profile=" << wls_time_profile
     << " mode=" << (mode == SimMode::kOpticalCalibration ? "optical" : "fast")
     << " optical_dir=" << optical_dir
     << " strict_optical=" << (strict_optical ? 1 : 0)
     << " allow_optical_fallback=" << (allow_optical_fallback ? 1 : 0)
     << " authorising=" << (authorising ? 1 : 0)
     << " scintillator_material=" << scintillator_material
     << " coating_material=" << coating_material
     << " wls_fluorescence_model=" << wls_fluorescence_model
     << " wls_mean_number_photons=" << wls_mean_number_photons
     << " y11_attenuation_form=" << y11_attenuation_form
     << " tio2_finish=" << tio2_finish
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
    else if (eq(a, "--strict-optical")) { strict_optical = true; allow_optical_fallback = false; }
    else if (eq(a, "--allow-optical-fallback")) {
      allow_optical_fallback = true;
      strict_optical = false;
      authorising = false;
    }
    else if (eq(a, "--optical-constants-ledger")) { if(!(v=need(i)))return false; optical_constants_ledger = v; }
    else if (eq(a, "--scintillator-material")) {
      if(!(v=need(i)))return false;
      if (eq(v, "polystyrene_legacy") || eq(v, "vinyltoluene_pvt_hypothesis"))
        scintillator_material = v;
      else {
        std::cerr << "error: --scintillator-material must be "
                     "polystyrene_legacy|vinyltoluene_pvt_hypothesis\n";
        return false;
      }
    }
    else if (eq(a, "--coating-material")) {
      if(!(v=need(i)))return false;
      if (eq(v, "air_massless_placeholder") || eq(v, "tio2_paint_hypothesis"))
        coating_material = v;
      else {
        std::cerr << "error: --coating-material must be "
                     "air_massless_placeholder|tio2_paint_hypothesis\n";
        return false;
      }
    }
    else if (eq(a, "--wls-mean-number-photons")) {
      if(!(v=need(i)))return false; double t;
      if(!parse_double(v,t)){std::cerr<<"error: --wls-mean-number-photons requires a finite number\n";return false;}
      wls_mean_number_photons = t;
      wls_fluorescence_model = "geant4_poisson_mean";
      wls_fluorescence_status = "CONFIGURED_POISSON_MEAN";
    }
    else if (eq(a, "--y11-direct-scint-yield")) {
      if(!(v=need(i)))return false; double t;
      if(!parse_double(v,t)){std::cerr<<"error: --y11-direct-scint-yield requires a finite number\n";return false;}
      y11_direct_scint_yield_per_MeV = t;
      y11_direct_scint_status = (t == 0.0) ? "OMISSION_UNKNOWN_EXTERNAL" : "HYPOTHESIS_NONZERO_DIRECT_YIELD";
    }
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
  if (pde_scale < 0 || reflectivity_scale < 0 || attenuation_scale < 0 ||
      scintillator_absorption_scale < 0 || y11_bulk_attenuation_scale < 0) {
    std::cerr << "error: scale factors must be >= 0\n"; return false;
  }
  if (production_cut_mm <= 0) { std::cerr << "error: --production-cut must be > 0\n"; return false; }
  // Explicit permissive opt-in (#978). Env CCB_ALLOW_OPTICAL_FALLBACK=1 forces
  // non-authorising fallback mode. CCB_STRICT_OPTICAL=0 also selects fallback.
  if (const char* e = std::getenv("CCB_ALLOW_OPTICAL_FALLBACK")) {
    if (std::strcmp(e, "1") == 0 || std::strcmp(e, "true") == 0 ||
        std::strcmp(e, "TRUE") == 0 || std::strcmp(e, "yes") == 0) {
      allow_optical_fallback = true;
      strict_optical = false;
      authorising = false;
    }
  }
  if (const char* e = std::getenv("CCB_STRICT_OPTICAL")) {
    if (std::strcmp(e, "0") == 0 || std::strcmp(e, "false") == 0 ||
        std::strcmp(e, "FALSE") == 0 || std::strcmp(e, "no") == 0) {
      allow_optical_fallback = true;
      strict_optical = false;
      authorising = false;
    } else if (std::strcmp(e, "1") == 0 || std::strcmp(e, "true") == 0 ||
               std::strcmp(e, "TRUE") == 0 || std::strcmp(e, "yes") == 0) {
      strict_optical = true;
      allow_optical_fallback = false;
    }
  }
  if (allow_optical_fallback) {
    strict_optical = false;
    authorising = false;
  }

  // Load versioned optical-constants ledger (#979) when present.
  {
    std::string ledger_path = optical_constants_ledger;
    // Prefer ledger inside optical_dir when the relative default is used.
    if (ledger_path == "optical/optical_constants_ledger.conf") {
      const std::string cand = optical_dir + "/optical_constants_ledger.conf";
      std::ifstream probe(cand);
      if (probe) ledger_path = cand;
    }
    OpticalConstantsLedger led = OpticalConstantsLedger::LoadFile(ledger_path);
    if (!led.load_errors.empty()) {
      for (const auto& err : led.load_errors) {
        std::cerr << (strict_optical ? "error[strict]: " : "warning: ") << err << "\n";
      }
      if (strict_optical && led.values.empty()) {
        std::cerr << "fatal: optical constants ledger required in strict mode\n";
        return false;
      }
    } else {
      optical_constants_ledger = ledger_path;
      scintillator_rindex = led.GetDouble("scintillator_rindex", scintillator_rindex);
      scintillation_yield_per_MeV = led.GetDouble("scintillation_yield_per_MeV", scintillation_yield_per_MeV);
      scintillation_time_ns = led.GetDouble("scintillation_time_ns", scintillation_time_ns);
      y11_core_rindex = led.GetDouble("y11_core_rindex", y11_core_rindex);
      wls_time_constant_ns = led.GetDouble("wls_time_constant_ns", wls_time_constant_ns);
      clad_inner_rindex = led.GetDouble("clad_inner_rindex", clad_inner_rindex);
      clad_outer_rindex = led.GetDouble("clad_outer_rindex", clad_outer_rindex);
      wls_mean_number_photons = led.GetDouble("wls_mean_number_photons", wls_mean_number_photons);
      wls_fluorescence_model = led.GetString("wls_fluorescence_model", wls_fluorescence_model);
      wls_fluorescence_status = led.GetString("wls_fluorescence_status", wls_fluorescence_status);
      y11_direct_scint_yield_per_MeV = led.GetDouble("y11_direct_scint_yield_per_MeV", y11_direct_scint_yield_per_MeV);
      y11_direct_scint_status = led.GetString("y11_direct_scint_status", y11_direct_scint_status);
      y11_attenuation_form = led.GetString("y11_attenuation_form", y11_attenuation_form);
      y11_attenuation_form_status = led.GetString("y11_attenuation_form_status", y11_attenuation_form_status);
      tio2_finish = led.GetString("tio2_finish", tio2_finish);
      tio2_sigma_alpha = led.GetDouble("tio2_sigma_alpha", tio2_sigma_alpha);
      tio2_specular_lobe = led.GetDouble("tio2_specular_lobe", tio2_specular_lobe);
      tio2_specular_spike = led.GetDouble("tio2_specular_spike", tio2_specular_spike);
      tio2_backscatter = led.GetDouble("tio2_backscatter", tio2_backscatter);
      tio2_reflection_model_status = led.GetString("tio2_reflection_model_status", tio2_reflection_model_status);
      coupling_grease_rindex = led.GetDouble("coupling_grease_rindex", coupling_grease_rindex);
      coupling_epoxy_rindex = led.GetDouble("coupling_epoxy_rindex", coupling_epoxy_rindex);
      tio2_paint_density_g_cm3 = led.GetDouble("tio2_paint_density_g_cm3", tio2_paint_density_g_cm3);
    }
  }
  if (wls_mean_number_photons < 0) {
    std::cerr << "error: wls_mean_number_photons must be >= 0\n"; return false;
  }
  if (y11_direct_scint_yield_per_MeV < 0) {
    std::cerr << "error: y11_direct_scint_yield_per_MeV must be >= 0\n"; return false;
  }
  return true;
}
