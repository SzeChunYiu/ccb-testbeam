#include "AppConfig.hh"

#include <cstring>
#include <cstdlib>
#include <iostream>
#include <sstream>

namespace {
bool eq(const char* a, const char* b) { return std::strcmp(a, b) == 0; }
}  // namespace

void AppConfig::PrintUsage(const char* prog) {
  std::cout <<
    "Usage: " << prog << " [options]\n"
    "  CCB single-stave optical simulation (issue #796).\n\n"
    "  --particle NAME          proton|deuteron            (default proton)\n"
    "  --energy MEV             primary kinetic energy MeV  (default 100)\n"
    "  --nevents N              events this invocation      (default 1000)\n"
    "  --threads N              worker threads              (default 1)\n"
    "  --seed N                 RNG seed                    (default 1)\n"
    "  --hit-x CM               impact x (stave length)     (default 0)\n"
    "  --hit-y CM               impact y (width)            (default 0)\n"
    "  --theta DEG              polar tilt from +z          (default 0)\n"
    "  --phi DEG                azimuth of tilt             (default 0)\n"
    "  --birks-kB VAL           Birks kB [mm/MeV]           (default 0.126)\n"
    "  --reflectivity-scale V   TiO2 reflectivity scale     (default 1.0)\n"
    "  --attenuation-scale V    Y-11 attenuation scale      (default 1.0)\n"
    "  --pde-scale V            SiPM PDE scale              (default 1.0)\n"
    "  --coupling V             fibre-end->sensor coupling  (default 1.0)\n"
    "  --far-end MODE           absorb|mirror               (default absorb)\n"
    "  --mode MODE              optical|fast                (default optical)\n"
    "  --optical-dir DIR        optical CSV table directory (default optical)\n"
    "  --output FILE            ntuple output (.root)       (default ccb_stave.root)\n"
    "  --macro FILE             run a macro then exit\n"
    "  -h, --help               this message\n";
}

std::string AppConfig::Describe() const {
  std::ostringstream os;
  os << "particle=" << particle
     << " KE_MeV=" << kinetic_energy_MeV
     << " nevents=" << n_events
     << " threads=" << n_threads
     << " seed=" << seed
     << " hit_x_cm=" << hit_x_cm
     << " hit_y_cm=" << hit_y_cm
     << " theta_deg=" << theta_deg
     << " phi_deg=" << phi_deg
     << " birks_kB=" << birks_kB_mm_per_MeV
     << " reflectivity_scale=" << reflectivity_scale
     << " attenuation_scale=" << attenuation_scale
     << " pde_scale=" << pde_scale
     << " coupling=" << coupling_efficiency
     << " far_end=" << (far_end_boundary_absorb ? "absorb" : "mirror")
     << " mode=" << (mode == SimMode::kOpticalCalibration ? "optical" : "fast")
     << " optical_dir=" << optical_dir
     << " output=" << output;
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
    else if (eq(a, "--energy"))            { if(!(v=need(i)))return false; kinetic_energy_MeV = std::atof(v); }
    else if (eq(a, "--nevents"))           { if(!(v=need(i)))return false; n_events = std::atoi(v); }
    else if (eq(a, "--threads"))           { if(!(v=need(i)))return false; n_threads = std::atoi(v); }
    else if (eq(a, "--seed"))              { if(!(v=need(i)))return false; seed = std::strtoull(v, nullptr, 10); }
    else if (eq(a, "--hit-x"))             { if(!(v=need(i)))return false; hit_x_cm = std::atof(v); }
    else if (eq(a, "--hit-y"))             { if(!(v=need(i)))return false; hit_y_cm = std::atof(v); }
    else if (eq(a, "--theta"))             { if(!(v=need(i)))return false; theta_deg = std::atof(v); }
    else if (eq(a, "--phi"))               { if(!(v=need(i)))return false; phi_deg = std::atof(v); }
    else if (eq(a, "--birks-kB"))          { if(!(v=need(i)))return false; birks_kB_mm_per_MeV = std::atof(v); }
    else if (eq(a, "--reflectivity-scale")){ if(!(v=need(i)))return false; reflectivity_scale = std::atof(v); }
    else if (eq(a, "--attenuation-scale")) { if(!(v=need(i)))return false; attenuation_scale = std::atof(v); }
    else if (eq(a, "--pde-scale"))         { if(!(v=need(i)))return false; pde_scale = std::atof(v); }
    else if (eq(a, "--coupling"))          { if(!(v=need(i)))return false; coupling_efficiency = std::atof(v); }
    else if (eq(a, "--far-end")) {
      if(!(v=need(i)))return false;
      if (eq(v, "absorb")) far_end_boundary_absorb = true;
      else if (eq(v, "mirror")) far_end_boundary_absorb = false;
      else { std::cerr << "error: --far-end must be absorb|mirror\n"; return false; }
    }
    else if (eq(a, "--mode")) {
      if(!(v=need(i)))return false;
      if (eq(v, "optical")) mode = SimMode::kOpticalCalibration;
      else if (eq(v, "fast")) mode = SimMode::kFastKernel;
      else { std::cerr << "error: --mode must be optical|fast\n"; return false; }
    }
    else if (eq(a, "--optical-dir")) { if(!(v=need(i)))return false; optical_dir = v; }
    else if (eq(a, "--output"))      { if(!(v=need(i)))return false; output = v; }
    else if (eq(a, "--macro"))       { if(!(v=need(i)))return false; macro = v; }
    else {
      std::cerr << "error: unknown argument '" << a << "'\n";
      PrintUsage(argv[0]);
      return false;
    }
  }
  // --- validation ---
  if (particle != "proton" && particle != "deuteron") {
    std::cerr << "error: --particle must be proton|deuteron\n"; return false;
  }
  if (kinetic_energy_MeV <= 0) { std::cerr << "error: --energy must be > 0\n"; return false; }
  if (n_events <= 0)           { std::cerr << "error: --nevents must be > 0\n"; return false; }
  if (n_threads <= 0)          { std::cerr << "error: --threads must be > 0\n"; return false; }
  if (coupling_efficiency < 0 || coupling_efficiency > 1) {
    std::cerr << "error: --coupling must be in [0,1]\n"; return false;
  }
  if (pde_scale < 0 || reflectivity_scale < 0 || attenuation_scale < 0) {
    std::cerr << "error: scale factors must be >= 0\n"; return false;
  }
  return true;
}
