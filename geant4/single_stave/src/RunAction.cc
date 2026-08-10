#include "RunAction.hh"
#include "SimData.hh"
#include "NpyWriter.hh"

#include "G4Run.hh"
#include "G4AnalysisManager.hh"
#include "G4SystemOfUnits.hh"

#include <cstdlib>
#include <fstream>
#include <iostream>
#include <ctime>
#include <cstdio>
#include <string>
#include <sys/stat.h>

RunAction::RunAction(const AppConfig& cfg, const OpticalTables& tables,
                     const std::string& geometry_hash)
    : cfg_(cfg), tables_(tables), geometry_hash_(geometry_hash) {}

RunAction::~RunAction() = default;

void RunAction::DefineNtuples() {
  auto* am = G4AnalysisManager::Instance();
  am->SetVerboseLevel(0);
  // Merge worker-thread ntuples into ONE output file (MT runs otherwise emit
  // per-thread <output>_tN.root). Must be set before OpenFile.
  am->SetNtupleMerging(true);
  // A single output file, defined once — no per-energy overwrite.
  am->OpenFile(cfg_.output);

  // Per-event ntuple.
  nt_event_ = am->CreateNtuple("events", "single-stave per-event");
  am->CreateNtupleIColumn("event");
  am->CreateNtupleSColumn("particle");
  am->CreateNtupleDColumn("ke_MeV");
  am->CreateNtupleDColumn("edep_scint_MeV");       // quenched (visible)
  am->CreateNtupleDColumn("edep_scint_raw_MeV");   // unquenched
  am->CreateNtupleDColumn("track_len_scint_mm");
  am->CreateNtupleDColumn("entry_x_cm");
  am->CreateNtupleDColumn("entry_y_cm");
  am->CreateNtupleDColumn("entry_z_cm");
  am->CreateNtupleDColumn("exit_x_cm");
  am->CreateNtupleDColumn("exit_y_cm");
  am->CreateNtupleDColumn("exit_z_cm");
  am->CreateNtupleIColumn("n_scint_generated");
  am->CreateNtupleIColumn("n_wls_generated");
  am->CreateNtupleIColumn("n_cerenkov_generated");
  // Four conceptual channels (readout + three controls).
  am->CreateNtupleIColumn("arrival_readout");
  am->CreateNtupleIColumn("arrival_f1far");
  am->CreateNtupleIColumn("arrival_f2near");
  am->CreateNtupleIColumn("arrival_f2far");
  am->CreateNtupleIColumn("detected_readout");
  am->CreateNtupleIColumn("detected_f1far");
  am->CreateNtupleIColumn("detected_f2near");
  am->CreateNtupleIColumn("detected_f2far");
  am->CreateNtupleDColumn("pe_sat_readout");
  am->CreateNtupleDColumn("pe_sat_f1far");
  am->CreateNtupleDColumn("pe_sat_f2near");
  am->CreateNtupleDColumn("pe_sat_f2far");
  // SiPM core ADC (peak above baseline) per sensor (SIPM-P1-002).
  am->CreateNtupleDColumn("adc_readout");
  am->CreateNtupleDColumn("adc_f1far");
  am->CreateNtupleDColumn("adc_f2near");
  am->CreateNtupleDColumn("adc_f2far");
  am->FinishNtuple(nt_event_);

  // Per-photon ntuple (calibration mode: arrival wavelength/time preserved).
  if (cfg_.mode == SimMode::kOpticalCalibration) {
    nt_photon_ = am->CreateNtuple("photons", "per-photon arrivals");
    am->CreateNtupleIColumn("event");
    am->CreateNtupleIColumn("sensor");       // SensorId
    am->CreateNtupleDColumn("wavelength_nm");
    am->CreateNtupleDColumn("time_ns");
    am->CreateNtupleDColumn("path_len_mm");
    am->CreateNtupleIColumn("detected");
    am->FinishNtuple(nt_photon_);
  }
}

void RunAction::BeginOfRunAction(const G4Run*) {
  // Do not reseed here: in MT mode Geant4 assigns master-generated per-event
  // seeds to workers. The master seed is configured once in main.cc before the
  // run manager is constructed.
  if (IsMaster() || G4Threading::G4GetThreadId() < 0) {
    std::cout << "RUN_CONFIG " << cfg_.Describe() << " geometry_hash="
              << geometry_hash_ << std::endl;
  }
  DefineNtuples();
  if (cfg_.gpu_optical) {
    EnsureOpticalOutDir();
  }
}

void RunAction::EnsureOpticalOutDir() {
  // Resolve the output dir for GPU input-photon npy files.
  std::string dir = cfg_.optical_out;
  if (dir.empty()) {
    std::string out = cfg_.output;
    std::string::size_type slash = out.find_last_of('/');
    dir = (slash == std::string::npos) ? "optical_gpu"
                                        : out.substr(0, slash) + "/optical_gpu";
  }
  std::string::size_type pos = 0;
  while ((pos = dir.find('/', pos + 1)) != std::string::npos) {
    ::mkdir(dir.substr(0, pos).c_str(), 0775);
  }
  ::mkdir(dir.c_str(), 0775);
  optical_out_dir_ = dir;
}

void RunAction::WriteGpuPhotons(const EventData& e, int event_id) {
  // Emit captured scintillation photons as NumPy (N,4,4) float32 in Opticks
  // sphoton layout. Writes an empty (0,4,4) when none captured so the harness
  // still sees a file.
  if (optical_out_dir_.empty()) EnsureOpticalOutDir();
  const size_t n16 = e.gpu_photons.size();      // 16 floats per photon
  const size_t nph = n16 / 16;
  char path[512];
  std::snprintf(path, sizeof(path), "%s/event_%06d.npy",
                optical_out_dir_.c_str(), event_id);
  std::vector<size_t> shape = (nph > 0) ? std::vector<size_t>{nph, 4, 4}
                                        : std::vector<size_t>{0, 4, 4};
  CCB::write_npy_f32(path, e.gpu_photons.data(), shape);
  std::cout << "CCB_GPU_PHOTONS event=" << event_id
            << " n_photons=" << nph << " -> " << path << std::endl;
}

void RunAction::WriteCpuArrivals(const EventData& e, int event_id) {
  // CPU reference side of the parity diagnostic. Emits the named-sensor
  // arrival photons (pre-PDE, matching the GPU hit convention) as a NumPy
  // (M,4) float32 array: [sensor, wavelength_nm, time_ns, path_mm].
  if (optical_out_dir_.empty()) EnsureOpticalOutDir();
  std::vector<float> buf;
  buf.reserve(e.photons.size() * 4);
  for (const PhotonHit& p : e.photons) {
    buf.push_back(static_cast<float>(p.sensor));
    buf.push_back(static_cast<float>(p.wavelength_nm));
    buf.push_back(static_cast<float>(p.time_ns));
    buf.push_back(static_cast<float>(p.path_len_mm));
  }
  char path[512];
  std::snprintf(path, sizeof(path), "%s/cpu_event_%06d.npy",
                optical_out_dir_.c_str(), event_id);
  std::vector<size_t> shape = std::vector<size_t>{e.photons.size(), 4};
  CCB::write_npy_f32(path, buf.data(), shape);
}

void RunAction::FillEvent(const EventData& e, int event_id) {
  auto* am = G4AnalysisManager::Instance();
  int c = 0;
  am->FillNtupleIColumn(nt_event_, c++, event_id);
  am->FillNtupleSColumn(nt_event_, c++, cfg_.particle);
  am->FillNtupleDColumn(nt_event_, c++, cfg_.kinetic_energy_MeV);
  am->FillNtupleDColumn(nt_event_, c++, e.edep_scint_MeV);
  am->FillNtupleDColumn(nt_event_, c++, e.edep_scint_raw_MeV);
  am->FillNtupleDColumn(nt_event_, c++, e.track_len_scint_mm);
  am->FillNtupleDColumn(nt_event_, c++, e.entry[0]);
  am->FillNtupleDColumn(nt_event_, c++, e.entry[1]);
  am->FillNtupleDColumn(nt_event_, c++, e.entry[2]);
  am->FillNtupleDColumn(nt_event_, c++, e.exit[0]);
  am->FillNtupleDColumn(nt_event_, c++, e.exit[1]);
  am->FillNtupleDColumn(nt_event_, c++, e.exit[2]);
  am->FillNtupleIColumn(nt_event_, c++, (int)e.n_scint_generated);
  am->FillNtupleIColumn(nt_event_, c++, (int)e.n_wls_generated);
  am->FillNtupleIColumn(nt_event_, c++, (int)e.n_cerenkov_generated);
  for (int i = 0; i < kNSensors; ++i)
    am->FillNtupleIColumn(nt_event_, c++, (int)e.n_end_arrival[i]);
  for (int i = 0; i < kNSensors; ++i)
    am->FillNtupleIColumn(nt_event_, c++, (int)e.n_detected[i]);
  for (int i = 0; i < kNSensors; ++i)
    am->FillNtupleDColumn(nt_event_, c++, e.pe_saturated[i]);
  for (int i = 0; i < kNSensors; ++i)
    am->FillNtupleDColumn(nt_event_, c++, e.adc[i]);
  am->AddNtupleRow(nt_event_);

  if (cfg_.mode == SimMode::kOpticalCalibration && nt_photon_ >= 0) {
    for (const auto& p : e.photons) {
      int pc = 0;
      am->FillNtupleIColumn(nt_photon_, pc++, event_id);
      am->FillNtupleIColumn(nt_photon_, pc++, p.sensor);
      am->FillNtupleDColumn(nt_photon_, pc++, p.wavelength_nm);
      am->FillNtupleDColumn(nt_photon_, pc++, p.time_ns);
      am->FillNtupleDColumn(nt_photon_, pc++, p.path_len_mm);
      am->FillNtupleIColumn(nt_photon_, pc++, p.detected ? 1 : 0);
      am->AddNtupleRow(nt_photon_);
    }
  }
}

void RunAction::EndOfRunAction(const G4Run* run) {
  auto* am = G4AnalysisManager::Instance();
  am->Write();
  am->CloseFile();
  if (IsMaster() || G4Threading::G4GetThreadId() < 0) {
    WriteMetadataSidecar(run);
    std::cout << "RUN_DONE events=" << run->GetNumberOfEvent()
              << " output=" << cfg_.output << std::endl;
  }
}

void RunAction::WriteMetadataSidecar(const G4Run* run) const {
  // <output>.meta.json — provenance the analysis + manifest validators consume.
  const std::string meta = cfg_.output + ".meta.json";
  std::ofstream os(meta);
  if (!os) { std::cerr << "warning: cannot write " << meta << "\n"; return; }
  auto j = [](const std::string& s) -> std::string {
    // Fully robust JSON string escaping (RFC 8259).  Escapes \" \\ and all
    // control characters (< 0x20), using short forms for the common ones
    // (\n \r \t \b \f) and \uXXXX for the rest.
    std::string out;
    out.reserve(s.size() + 2);
    out += '"';
    for (unsigned char c : s) {
      switch (c) {
        case '"':  out += "\\\""; break;
        case '\\': out += "\\\\"; break;
        case '\n': out += "\\n"; break;
        case '\r': out += "\\r"; break;
        case '\t': out += "\\t"; break;
        case '\b': out += "\\b"; break;
        case '\f': out += "\\f"; break;
        default:
          if (c < 0x20) {
            char buf[8];
            std::snprintf(buf, sizeof(buf), "\\u%04x", c);
            out += buf;
          } else {
            out += static_cast<char>(c);
          }
      }
    }
    out += '"';
    return out;
  };
  const char* git = std::getenv("CCB_GIT_COMMIT");
  os << "{\n"
     << "  \"schema\": \"ccb-stave-run-meta/1\",\n"
     << "  \"git_commit\": " << j(git ? git : "unknown") << ",\n"
     << "  \"geometry_hash\": " << j(geometry_hash_) << ",\n"
     << "  \"seed\": " << cfg_.seed << ",\n"
     << "  \"threads_requested\": " << cfg_.n_threads << ",\n"
     << "  \"threads_effective\": " << cfg_.n_threads_effective << ",\n"
     << "  \"G4FORCENUMBEROFTHREADS\": "
     << j(cfg_.g4_force_number_of_threads.empty()
              ? "unset" : cfg_.g4_force_number_of_threads) << ",\n"
     << "  \"particle\": " << j(cfg_.particle) << ",\n"
     << "  \"kinetic_energy_MeV\": " << cfg_.kinetic_energy_MeV << ",\n"
     << "  \"n_events\": " << run->GetNumberOfEvent() << ",\n"
     << "  \"mode\": " << j(cfg_.mode == SimMode::kOpticalCalibration ? "optical" : "fast") << ",\n"
     << "  \"birks_kB_mm_per_MeV\": " << cfg_.birks_kB_mm_per_MeV << ",\n"
     << "  \"production_cut_mm\": " << cfg_.production_cut_mm << ",\n"
     << "  \"reflectivity_scale\": " << cfg_.reflectivity_scale << ",\n"
     << "  \"attenuation_scale\": " << cfg_.attenuation_scale << ",\n"
     << "  \"scintillator_absorption_scale\": " << cfg_.scintillator_absorption_scale << ",\n"
     << "  \"y11_bulk_attenuation_scale\": " << cfg_.y11_bulk_attenuation_scale << ",\n"
     << "  \"pde_scale\": " << cfg_.pde_scale << ",\n"
     << "  \"collection_efficiency\": " << cfg_.collection_efficiency << ",\n"
	     << "  \"optical_interface_model\": " << j(cfg_.optical_interface_model) << ",\n"
     << "  \"sipm_n_cells\": " << cfg_.sipm_n_cells << ",\n"
     << "  \"far_end_mode\": " << j(cfg_.far_end_mode) << ",\n"
     << "  \"optical_tables\": {\n";
  // Record each optical table path + hash.
  size_t k = 0, n = tables_.All().size();
  for (const auto& kv : tables_.All()) {
    os << "    " << j(kv.first) << ": {\"path\": " << j(kv.second.path)
       << ", \"sha256\": " << j(kv.second.sha256) << "}"
       << (++k < n ? "," : "") << "\n";
  }
  os << "  }\n}\n";
}
