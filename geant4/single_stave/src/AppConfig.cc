#include "AppConfig.hh"

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
    "  --birks-kB VAL           Birks kB [mm/MeV]           (default 0.126)\n"
    "  --production-cut MM      secondary-production range threshold [mm]\n"
    "                           (default 0.1; gamma/e-/e+/p, NOT optical tracking)\n"
    "  --reflectivity-scale V   TiO2 reflectivity scale     (default 1.0)\n"
    "  --attenuation-scale V    Y-11 attenuation scale      (default 1.0)\n"
    "  --pde-scale V            SiPM PDE scale              (default 1.0)\n"
    "  --collection-efficiency V  post-transport collection    (default 1.0)\n"
	    "  --optical-interface-model M  dry_butt|grease|epoxy|bonded|windowed\n"
	    "                               (default UNKNOWN_EXTERNAL)\n"
    "  --far-end MODE           absorb|open|mirror|instrumented (default instrumented)\n"
    "  --wls-time-profile P     exponential|delta           (default exponential)\n"
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
     << " birks_kB=" << birks_kB_mm_per_MeV
     << " production_cut_mm=" << production_cut_mm
     << " reflectivity_scale=" << reflectivity_scale
     << " attenuation_scale=" << attenuation_scale
     << " pde_scale=" << pde_scale
     << " collection_efficiency=" << collection_efficiency
	     << " optical_interface_model=" << optical_interface_model
     << " far_end=" << far_end_mode
     << " wls_time_profile=" << wls_time_profile
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
    else if (eq(a, "--birks-kB"))          { if(!(v=need(i)))return false; double t; if(!parse_double(v,t)){std::cerr<<"error: --birks-kB requires a finite number, got '"<<v<<"'\n";return false;} birks_kB_mm_per_MeV = t; }
    else if (eq(a, "--production-cut"))    { if(!(v=need(i)))return false; double t; if(!parse_double(v,t)){std::cerr<<"error: --production-cut requires a finite number, got '"<<v<<"'\n";return false;} production_cut_mm = t; }
    else if (eq(a, "--reflectivity-scale")){ if(!(v=need(i)))return false; double t; if(!parse_double(v,t)){std::cerr<<"error: --reflectivity-scale requires a finite number, got '"<<v<<"'\n";return false;} reflectivity_scale = t; }
    else if (eq(a, "--attenuation-scale")) { if(!(v=need(i)))return false; double t; if(!parse_double(v,t)){std::cerr<<"error: --attenuation-scale requires a finite number, got '"<<v<<"'\n";return false;} attenuation_scale = t; }
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
  if (pde_scale < 0 || reflectivity_scale < 0 || attenuation_scale < 0) {
    std::cerr << "error: scale factors must be >= 0\n"; return false;
  }
  if (production_cut_mm <= 0) { std::cerr << "error: --production-cut must be > 0\n"; return false; }
  // G4-003: env override for strict optical-table validation (production).
  if (!strict_optical) {
    if (const char* e = std::getenv("CCB_STRICT_OPTICAL")) {
      strict_optical = (std::strcmp(e, "1") == 0 || std::strcmp(e, "true") == 0 ||
                        std::strcmp(e, "TRUE") == 0 || std::strcmp(e, "yes") == 0);
    }
  }
  return true;
}
