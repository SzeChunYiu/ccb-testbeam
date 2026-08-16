// ccb_opticks_gpu.cc - OPTIONAL GPU optical-photon transport bridge (Opticks).
//
// Production use of the CCB->Opticks path. For each event, the CCB sim (run
// with --gpu-optical) has already captured the Geant4 Scintillation secondaries
// into an Opticks sphoton (N,4,4) npy. This bridge:
//   1. annotates the 4 SiPM discs as sensors (CCBSensorIdentifier),
//   2. ingests the production GDML -> CSGFoundry (sensor-annotated),
//   3. feeds the captured scintillation photons as Opticks INPUT_PHOTON
//      gensteps (explicit -- avoids the test-harness carrier auto-detect),
//   4. propagates them on GPU and collects the per-sensor hits.
//
// The Opticks build is referenced by path/env (OPTICKS_PREFIX); no Opticks
// source is vendored into ccb-testbeam. The CPU Geant4 reference is untouched.
#include "OPTICKS_LOG.hh"
#include "NP.hh"
#include "SEvt.hh"
#include "SEventConfig.hh"
#include "G4CXOpticks.hh"
#include "CCBSensorIdentifier.h"

#include <filesystem>
#include <iostream>
#include <string>
#include <vector>
#include <algorithm>

namespace fs = std::filesystem;

namespace {
std::vector<fs::path> list_events(const std::string& dir, int max_ev) {
  std::vector<fs::path> out;
  for (auto& e : fs::directory_iterator(dir))
    if (e.path().extension() == ".npy" &&
        e.path().filename().string().rfind("event_", 0) == 0)
      out.push_back(e.path());
  std::sort(out.begin(), out.end());
  if (max_ev > 0 && static_cast<int>(out.size()) > max_ev) out.resize(max_ev);
  return out;
}
}  // namespace

int main(int argc, char** argv) {
  OPTICKS_LOG(argc, argv);

  const std::string in_dir  = argc > 1 ? argv[1] : "optical_gpu";
  const std::string out_dir = argc > 2 ? argv[2] : "optical_gpu/gpu_hits";
  const int max_ev          = argc > 3 ? std::atoi(argv[3]) : 0;

  if (!fs::exists(in_dir)) {
    LOG(fatal) << "input photon dir not found: " << in_dir;
    return 2;
  }
  fs::create_directories(out_dir);

  // Input-photon running mode: SEvt will turn the captured scintillation
  // photons into the genstep source each event (createInputGenstep_simulate).
  SEventConfig::SetRunningMode("SRM_INPUT_PHOTON");
  // Hits are derived on HOST from the gathered photon array (QEvt::gatherHit
  // runs count_if_sphoton over evt->photon), so the photon component MUST be
  // gathered. SEventConfig::Initialize_Comp_Simulate_ recomputes the gather
  // and save masks from EventMode during QSim::init, so SetGatherComp alone is
  // overridden by the default Minimal EventMode (gather = HitComp only, no
  // photon array, gatherHit returns null). HitPhoton makes the masks include
  // PhotonComp, fixing the gather. (Equivalent: OPTICKS_EVENT_MODE=HitPhoton.)
  SEventConfig::SetEventMode("HitPhoton");

  // (1) sensor annotation + (2) GDML -> CSGFoundry.
  G4CXOpticks::SetSensorIdentifier(new CCBSensorIdentifier());
  G4CXOpticks::SetGeometry();
  SEvt* sev = SEvt::Get_EGPU();
  if (!sev) { LOG(fatal) << "no EGPU SEvt"; return 3; }

  const auto events = list_events(in_dir, max_ev);
  long total_in = 0, total_hit = 0;
  std::cout << "CCB_GPU_BRIDGE_BEGIN events=" << events.size()
            << " in=" << in_dir << " out=" << out_dir << std::endl;

  for (size_t i = 0; i < events.size(); ++i) {
    NP* ip = NP::Load(events[i].string().c_str());
    if (!ip || ip->num_values() == 0) {
      std::cout << "CCB_GPU_HIT event=" << i << " n_in=0 n_hit=0 (skip)"
                << std::endl;
      continue;
    }
    sev->setInputPhoton(ip);                 // (3) explicit scintillation gensteps
    G4CXOpticks::Get()->simulate(static_cast<int>(i), true);  // (4) GPU transport

    const int64_t nh = SEvt::GetNumHit_EGPU();
    total_in  += static_cast<long>(ip->shape[0]);
    total_hit += nh;
    if (NP* hit = sev->gatherHit()) {
      const std::string name = "gpu_hit_" + std::to_string(i) + ".npy";
      hit->save(out_dir.c_str(), name.c_str());
    }
    if (NP* ph = sev->gatherPhoton()) {
      const std::string name = "gpu_photon_" + std::to_string(i) + ".npy";
      ph->save(out_dir.c_str(), name.c_str());
    }
    std::cout << "CCB_GPU_HIT event=" << i
              << " n_in=" << ip->shape[0]
              << " n_hit=" << nh << std::endl;
  }

  std::cout << "CCB_GPU_BRIDGE_END total_in=" << total_in
            << " total_hit=" << total_hit
            << " efficiency=" << (total_in ? 100.0 * total_hit / total_in : 0.0)
            << "%" << std::endl;
  return 0;
}
