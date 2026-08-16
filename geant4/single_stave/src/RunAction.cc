#include "RunAction.hh"
#include "SimData.hh"
#include "NpyWriter.hh"
#include "SipmDigitizerConfig.hh"

#include "G4Run.hh"
#include "G4AnalysisManager.hh"
#include "G4SystemOfUnits.hh"

#include "ccb/sipm/Digest.hh"
#include "ccb/sipm/ResponseSimulator.hh"

#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <stdexcept>
#include <iostream>
#include <ctime>
#include <cstdio>
#include <sstream>
#include <string>
#include <sys/stat.h>
#include <vector>

RunAction::RunAction(const AppConfig& cfg, const OpticalTables& tables,
                     const std::string& geometry_hash,
                     const std::string& physics_hash,
                     const std::string& optical_hash)
    : cfg_(cfg), tables_(tables),
      geometry_hash_(geometry_hash), physics_hash_(physics_hash),
      optical_hash_(optical_hash) {
  // Master and worker both materialise the effective digitizer config so the
  // metadata sidecar written on the master thread cannot miss #977 fields.
  SetSipmDigitizerConfig(BuildSipmDigitizerConfig(cfg_, tables_));
}

RunAction::~RunAction() = default;

void RunAction::SetSipmDigitizerConfig(const ccb::sipm::ModelConfig& cfg) {
  sipm_config_ = cfg;
  have_sipm_config_ = true;
}

void RunAction::NoteSipmEventDiagnostics(bool candidate_limit_reached,
                                         std::size_t n_candidates_processed) {
  if (candidate_limit_reached) {
    ++candidate_limit_hits_;
  }
  if (n_candidates_processed > max_candidates_processed_) {
    max_candidates_processed_ = n_candidates_processed;
  }
}


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
  am->CreateNtupleDColumn("track_len_scint_mm");  // EVENT_TOTAL_NON_OPTICAL
  am->CreateNtupleDColumn("primary_edep_scint_MeV");
  am->CreateNtupleDColumn("primary_edep_scint_raw_MeV");
  am->CreateNtupleDColumn("primary_track_len_scint_mm");
  am->CreateNtupleIColumn("primary_track_id");
  am->CreateNtupleIColumn("primary_pdg");
  am->CreateNtupleDColumn("entry_x_cm");
  am->CreateNtupleDColumn("entry_y_cm");
  am->CreateNtupleDColumn("entry_z_cm");
  am->CreateNtupleDColumn("exit_x_cm");
  am->CreateNtupleDColumn("exit_y_cm");
  am->CreateNtupleDColumn("exit_z_cm");
  am->CreateNtupleIColumn("n_scint_generated");
  am->CreateNtupleIColumn("n_wls_generated");
  am->CreateNtupleIColumn("n_cerenkov_generated");
  am->CreateNtupleIColumn("n_wls_absorbed");      // ended by OpWLS (#1088)
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

  // #1091 ladder: sparse time-resolved neutron diagnostics.
  if (cfg_.neutron_diagnostics) {
    nt_neutron_ = am->CreateNtuple("neutron_steps",
                                   "per-step neutron / late-deposit records");
    am->CreateNtupleIColumn("event");
    am->CreateNtupleIColumn("kind");        // 0 neutron step, 1 late scint deposit
    am->CreateNtupleDColumn("t_ns");
    am->CreateNtupleDColumn("edep_MeV");
    am->CreateNtupleDColumn("ke_MeV");
    am->CreateNtupleIColumn("in_scint");
    am->CreateNtupleIColumn("pdg");
    am->FinishNtuple(nt_neutron_);
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
  am->FillNtupleDColumn(nt_event_, c++, e.primary_edep_scint_MeV);
  am->FillNtupleDColumn(nt_event_, c++, e.primary_edep_scint_raw_MeV);
  am->FillNtupleDColumn(nt_event_, c++, e.primary_track_len_scint_mm);
  am->FillNtupleIColumn(nt_event_, c++, e.primary_track_id);
  am->FillNtupleIColumn(nt_event_, c++, e.primary_pdg);
  am->FillNtupleDColumn(nt_event_, c++, e.entry[0]);
  am->FillNtupleDColumn(nt_event_, c++, e.entry[1]);
  am->FillNtupleDColumn(nt_event_, c++, e.entry[2]);
  am->FillNtupleDColumn(nt_event_, c++, e.exit[0]);
  am->FillNtupleDColumn(nt_event_, c++, e.exit[1]);
  am->FillNtupleDColumn(nt_event_, c++, e.exit[2]);
  am->FillNtupleIColumn(nt_event_, c++, (int)e.n_scint_generated);
  am->FillNtupleIColumn(nt_event_, c++, (int)e.n_wls_generated);
  am->FillNtupleIColumn(nt_event_, c++, (int)e.n_cerenkov_generated);
  am->FillNtupleIColumn(nt_event_, c++, (int)e.n_wls_absorbed);
  for (int i = 0; i < kNSensors; ++i)
    am->FillNtupleIColumn(nt_event_, c++, (int)e.n_end_arrival[i]);
  for (int i = 0; i < kNSensors; ++i)
    am->FillNtupleIColumn(nt_event_, c++, (int)e.n_detected[i]);
  for (int i = 0; i < kNSensors; ++i)
    am->FillNtupleDColumn(nt_event_, c++, e.pe_saturated[i]);
  for (int i = 0; i < kNSensors; ++i)
    am->FillNtupleDColumn(nt_event_, c++, e.adc[i]);
  am->AddNtupleRow(nt_event_);

  if (cfg_.neutron_diagnostics && nt_neutron_ >= 0) {
    for (const auto& n : e.neutron_steps) {
      int nc = 0;
      am->FillNtupleIColumn(nt_neutron_, nc++, event_id);
      am->FillNtupleIColumn(nt_neutron_, nc++, n.kind);
      am->FillNtupleDColumn(nt_neutron_, nc++, n.t_ns);
      am->FillNtupleDColumn(nt_neutron_, nc++, n.edep_MeV);
      am->FillNtupleDColumn(nt_neutron_, nc++, n.ke_MeV);
      am->FillNtupleIColumn(nt_neutron_, nc++, n.in_scint);
      am->FillNtupleIColumn(nt_neutron_, nc++, n.pdg);
      am->AddNtupleRow(nt_neutron_);
    }
  }

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
  if (!os) {
    std::cerr << "fatal: cannot write provenance sidecar " << meta << "\n";
    throw std::runtime_error("failed to write run metadata sidecar: " + meta);
  }
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
     << "  \"schema\": \"ccb-stave-run-meta/2\",\n"
     << "  \"git_commit\": " << j(git ? git : "unknown") << ",\n"
     << "  \"geometry_hash\": " << j(geometry_hash_) << ",\n"
     << "  \"physics_hash\": " << j(physics_hash_) << ",\n"
     << "  \"optical_hash\": " << j(optical_hash_) << ",\n"
     << "  \"track_len_scint_mm_scope\": \"EVENT_TOTAL_NON_OPTICAL\",\n"
     << "  \"primary_track_len_scint_mm_scope\": \"PRIMARY_PROJECTILE\",\n"
     << "  \"seed\": " << cfg_.seed << ",\n"
     << "  \"threads_requested\": " << cfg_.n_threads << ",\n"
     << "  \"threads_effective\": " << cfg_.n_threads_effective << ",\n"
     << "  \"G4FORCENUMBEROFTHREADS\": "
     << j(cfg_.g4_force_number_of_threads.empty()
              ? "unset" : cfg_.g4_force_number_of_threads) << ",\n"
     << "  \"particle\": " << j(cfg_.particle) << ",\n"
     << "  \"kinetic_energy_MeV\": " << cfg_.kinetic_energy_MeV << ",\n"
     << "  \"n_events_requested\": " << cfg_.n_events << ",\n"
     << "  \"n_events\": " << run->GetNumberOfEvent() << ",\n"
     << "  \"hit_x_cm\": " << cfg_.hit_x_cm << ",\n"
     << "  \"hit_y_cm\": " << cfg_.hit_y_cm << ",\n"
     << "  \"theta_deg\": " << cfg_.theta_deg << ",\n"
     << "  \"phi_deg\": " << cfg_.phi_deg << ",\n"
     << "  \"mode\": " << j(cfg_.mode == SimMode::kOpticalCalibration ? "optical" : "fast") << ",\n"
     << "  \"birks_kB_mm_per_MeV\": " << cfg_.birks_kB_mm_per_MeV << ",\n"
     << "  \"production_cut_mm\": " << cfg_.production_cut_mm << ",\n"
     << "  \"physics_list\": " << j(cfg_.physics_list) << ",\n"
     << "  \"neutron_tracking_time_cut_us\": " << cfg_.neutron_time_cut_us << ",\n"
     << "  \"neutron_tracking_time_cut_status\": " << j(cfg_.neutron_tracking_time_cut_status) << ",\n"
     << "  \"neutron_tracking_time_cut_configured\": " << (cfg_.neutron_tracking_time_cut_configured ? "true" : "false") << ",\n"
     << "  \"neutron_timecut_policy_id\": " << j(cfg_.neutron_timecut_policy_id) << ",\n"
     << "  \"neutron_time_cut_us\": " << cfg_.neutron_time_cut_us << ",\n"
     << "  \"neutron_timecut_adr\": " << j(cfg_.neutron_timecut_adr) << ",\n"
     << "  \"neutron_timecut_claims_authorized\": " << (cfg_.neutron_timecut_claims_authorized ? "true" : "false") << ",\n"
     << "  \"neutron_diagnostics\": " << (cfg_.neutron_diagnostics ? "true" : "false") << ",\n"
     << "  \"step_size_convergence_status\": \"BLOCKED_ISSUE_1095\",\n"
     << "  \"primary_vs_event_track_contract\": \"primary_* columns (#1007)\",\n"
     << "  \"reflectivity_scale\": " << cfg_.reflectivity_scale << ",\n"
     << "  \"attenuation_scale\": " << cfg_.attenuation_scale << ",\n"
     << "  \"scintillator_absorption_scale\": " << cfg_.scintillator_absorption_scale << ",\n"
     << "  \"y11_bulk_attenuation_scale\": " << cfg_.y11_bulk_attenuation_scale << ",\n"
     << "  \"pde_scale\": " << cfg_.pde_scale << ",\n"
     << "  \"collection_efficiency\": " << cfg_.collection_efficiency << ",\n"
	     << "  \"optical_interface_model\": " << j(cfg_.optical_interface_model) << ",\n"
     << "  \"sipm_n_cells\": " << cfg_.sipm_n_cells << ",\n"
     << "  \"sipm_overvoltage_V\": " << cfg_.sipm_overvoltage_V << ",\n"
     << "  \"wls_time_profile\": " << j(cfg_.wls_time_profile) << ",\n"
     << "  \"hrd_fibre_count_status\": \"UNRESOLVED_HARDWARE_CONTRADICTION\",\n"
     << "  \"authorising_light_collection_claims\": false,\n"
     << "  \"attenuation_identifiability_status\": \"UNRESOLVED\",\n"
     << "  \"authorising_attenuation_claims\": false,\n"
     << "  \"authorising_absolute_light_yield_claims\": false,\n"
     << "  \"strict_optical\": " << (cfg_.strict_optical ? "true" : "false") << ",\n"
     << "  \"far_end_mode\": " << j(cfg_.far_end_mode) << ",\n"
     << "  \"step_policy_id\": \"pin_qgsp_bic_inherited_em_stepfunction\",\n"
     << "  \"daq_digitizer_schema_id\": null,\n"
     << "  \"daq_digitizer_status\": \"BLOCKED_UNMEASURED_TRANSFER_FUNCTION\",\n"
     << "  \"allow_optical_fallback\": " << (cfg_.allow_optical_fallback ? "true" : "false") << ",\n"
     << "  \"authorising\": " << (cfg_.authorising ? "true" : "false") << ",\n"
     << "  \"optical_fallback_used\": " << (cfg_.optical_fallback_used ? "true" : "false") << ",\n"
     << "  \"optical_constants_ledger\": " << j(cfg_.optical_constants_ledger) << ",\n"
     << "  \"scintillator_material\": " << j(cfg_.scintillator_material) << ",\n"
     << "  \"scintillator_material_status\": " << j(cfg_.scintillator_material_status) << ",\n"
     << "  \"coating_material\": " << j(cfg_.coating_material) << ",\n"
     << "  \"coating_material_status\": " << j(cfg_.coating_material_status) << ",\n"
     << "  \"wls_mean_number_photons\": " << cfg_.wls_mean_number_photons << ",\n"
     << "  \"wls_fluorescence_yield\": " << cfg_.wls_fluorescence_yield << ",\n"
     << "  \"wls_fluorescence_model\": " << j(cfg_.wls_fluorescence_model) << ",\n"
     << "  \"wls_fluorescence_status\": " << j(cfg_.wls_fluorescence_status) << ",\n"
     << "  \"y11_direct_scint_yield_per_MeV\": " << cfg_.y11_direct_scint_yield_per_MeV << ",\n"
     << "  \"y11_direct_scint_status\": " << j(cfg_.y11_direct_scint_status) << ",\n"
     << "  \"y11_attenuation_form\": " << j(cfg_.y11_attenuation_form) << ",\n"
     << "  \"y11_attenuation_form_status\": " << j(cfg_.y11_attenuation_form_status) << ",\n"
     << "  \"tio2_finish\": " << j(cfg_.tio2_finish) << ",\n"
     << "  \"tio2_specular_lobe\": " << cfg_.tio2_specular_lobe << ",\n"
     << "  \"tio2_specular_spike\": " << cfg_.tio2_specular_spike << ",\n"
     << "  \"tio2_backscatter\": " << cfg_.tio2_backscatter << ",\n"
     << "  \"tio2_reflection_model_status\": " << j(cfg_.tio2_reflection_model_status) << ",\n"
     << "  \"gpu_optical\": " << (cfg_.gpu_optical ? "true" : "false") << ",\n"
     << "  \"optical_out\": " << j(cfg_.optical_out) << ",\n"
     << "  \"macro\": " << j(cfg_.macro) << ",\n"
     << "  \"output\": " << j(cfg_.output) << ",\n"
     << "  \"detector_response\": {\n"
     << "    \"adc_path\": \"ccb-sipm-core\",\n"
     << "    \"legacy_pe_path\": \"INDEPENDENT_DIAGNOSTIC_DRAW\",\n"
     << "    \"legacy_pe_note\": \"detected_*/pe_sat_* use a separate Bernoulli+analytic occupancy draw; not the latent state of adc_* (issue #1084)\"\n"
     << "  },\n"
     << "  \"optical_tables\": {\n";
  // Record each optical table path + hash + validation status (#978/#980).
  size_t k = 0, n = tables_.All().size();
  for (const auto& kv : tables_.All()) {
    os << "    " << j(kv.first) << ": {\"path\": " << j(kv.second.path)
       << ", \"sha256\": " << j(kv.second.sha256)
       << ", \"units_x\": " << j(kv.second.units_x)
       << ", \"units_y\": " << j(kv.second.units_y)
       << ", \"status\": " << j(kv.second.status_note)
       << ", \"validation_status\": " << j(kv.second.validation_status)
       << ", \"fallback_used\": false}"
       << (++k < n ? "," : "") << "\n";
  }
  os << "  }";

  // #977: persist effective ccb-sipm-core configuration + digest.
  if (have_sipm_config_) {
    ccb::sipm::ResponseSimulator probe(sipm_config_);
    const auto meta = probe.run_metadata();
    const std::string meta_json = meta.render_json();
    const std::vector<std::uint8_t> bytes(meta_json.begin(), meta_json.end());
    const std::string digest = ccb::sipm::Sha256Hex(bytes);
    const char* sipm_git = std::getenv("CCB_SIPM_CORE_COMMIT");
    const bool ov_label_matches =
        cfg_.sipm_overvoltage_V == sipm_config_.device_provenance.overvoltage_V;
    os << ",\n"
       << "  \"digitizer\": {\n"
       << "    \"validation_status\": \"OK\",\n"
       << "    \"requested_operating_point\": {\n"
       << "      \"overvoltage_V\": " << cfg_.sipm_overvoltage_V << ",\n"
       << "      \"temperature_C\": null,\n"
       << "      \"temperature_status\": \"PROFILE_FIXED_NOT_IN_APPCONFIG\"\n"
       << "    },\n"
       << "    \"effective_operating_point\": {\n"
       << "      \"overvoltage_V\": " << sipm_config_.device_provenance.overvoltage_V << ",\n"
       << "      \"temperature_C\": " << sipm_config_.device_provenance.temperature_C << "\n"
       << "    },\n"
       << "    \"operating_point_label_matches_effective\": "
       << (ov_label_matches ? "true" : "false") << ",\n"
       << "    \"operating_point_physics_mapping_status\": \"BLOCKED_ADR_SIPM_OPERATING_POINT_H1\",\n"
       << "    \"response_surface_id\": " << j(sipm_config_.device_provenance.profile_file) << ",\n"
       << "    \"ccb_sipm_core_commit\": " << j(sipm_git ? sipm_git : "unspecified") << ",\n"
       << "    \"digitizer_config_sha256\": " << j(digest) << ",\n"
       << "    \"cells_x\": " << sipm_config_.cells_x << ",\n"
       << "    \"cells_y\": " << sipm_config_.cells_y << ",\n"
       << "    \"active_width_mm\": " << sipm_config_.active_width_mm << ",\n"
       << "    \"active_height_mm\": " << sipm_config_.active_height_mm << ",\n"
       << "    \"number_of_cells\": " << sipm_config_.number_of_cells() << ",\n"
       << "    \"requested_sipm_n_cells\": " << cfg_.sipm_n_cells << ",\n"
       << "    \"pde_scale\": " << sipm_config_.pde_scale << ",\n"
       << "    \"coupling_efficiency\": " << sipm_config_.coupling_efficiency << ",\n"
       << "    \"recovery_time_ns\": " << sipm_config_.recovery_time_ns << ",\n"
       << "    \"dark_count_rate_hz\": " << sipm_config_.dark_count_rate_hz << ",\n"
       << "    \"enable_dark_counts\": " << (sipm_config_.enable_dark_counts ? "true" : "false") << ",\n"
       << "    \"prompt_crosstalk_probability\": " << sipm_config_.prompt_crosstalk_probability << ",\n"
       << "    \"enable_delayed_crosstalk\": "
       << (sipm_config_.enable_delayed_crosstalk ? "true" : "false") << ",\n"
       << "    \"delayed_crosstalk_probability\": " << sipm_config_.delayed_crosstalk_probability << ",\n"
       << "    \"afterpulse_fast_probability\": " << sipm_config_.afterpulse_fast_probability << ",\n"
       << "    \"afterpulse_slow_probability\": " << sipm_config_.afterpulse_slow_probability << ",\n"
       << "    \"dead_time_ns\": " << sipm_config_.dead_time_ns << ",\n"
       << "    \"sptr_sigma_ns\": " << sipm_config_.sptr_sigma_ns << ",\n"
       << "    \"electronics_noise_sigma_pe\": " << sipm_config_.electronics_noise_sigma_pe << ",\n"
       << "    \"shaper_integrator_stages\": " << sipm_config_.shaper_integrator_stages << ",\n"
       << "    \"pulse_decay_ns\": " << sipm_config_.pulse_decay_ns << ",\n"
       << "    \"adc_bits\": " << sipm_config_.adc_bits << ",\n"
       << "    \"adc_lsb_pe\": " << sipm_config_.adc_lsb_pe << ",\n"
       << "    \"baseline_adc\": " << sipm_config_.baseline_adc << ",\n"
       << "    \"sample_dt_ns\": " << sipm_config_.sample_dt_ns << ",\n"
       << "    \"window_start_ns\": " << sipm_config_.window_start_ns << ",\n"
       << "    \"window_end_ns\": " << sipm_config_.window_end_ns << ",\n"
       << "    \"history_start_ns\": " << sipm_config_.history_start_ns << ",\n"
       << "    \"max_candidates\": " << sipm_config_.max_candidates << ",\n"
       << "    \"candidate_limit_hits\": " << candidate_limit_hits_ << ",\n"
       << "    \"max_candidates_processed\": " << max_candidates_processed_ << ",\n"
       << "    \"overvoltage_V\": " << sipm_config_.device_provenance.overvoltage_V << ",\n"
       << "    \"temperature_C\": " << sipm_config_.device_provenance.temperature_C << ",\n"
       << "    \"device_name\": " << j(sipm_config_.device_provenance.device_name) << ",\n"
       << "    \"calibration_status\": " << j(sipm_config_.device_provenance.calibration_status) << ",\n"
       << "    \"impulse_model\": " << j(sipm_config_.impulse_model) << ",\n"
       << "    \"impulse_response_status\": " << j(meta.electronics.impulse_response_status) << ",\n"
       << "    \"shaper_model\": " << j(meta.electronics.shaper_model) << ",\n"
       << "    \"measured_impulse_source_hash\": " << j(meta.electronics.measured_impulse_source_hash) << ",\n"
       << "    \"effective_kernel_hash\": " << j(meta.electronics.effective_kernel_hash) << ",\n"
       << "    \"authorising_measured_electronics_claims\": false,\n"
       << "    \"trigger_recovery_model\": " << j(sipm_config_.trigger_recovery_model) << ",\n"
       << "    \"gain_recovery_model\": " << j(sipm_config_.gain_recovery_model) << ",\n"
       << "    \"core_run_metadata_json\": " << j(meta_json) << ",\n"
       << "    \"waveform_persistence\": \"PEAK_ONLY_DISCARDED\",\n"
       << "    \"daq_digitizer_schema\": \"UNSET\",\n"
       << "    \"authorising_waveform_claims\": false,\n"
       << "    \"internal_sample_dt_ns\": " << sipm_config_.sample_dt_ns << ",\n"
       << "    \"internal_window_start_ns\": " << sipm_config_.window_start_ns << ",\n"
       << "    \"internal_window_end_ns\": " << sipm_config_.window_end_ns << ",\n"
       << "    \"waveform_bridge_note\": \"Full DAQ-sampled waveform persistence requires a versioned HRD schema (#1009/#952/#993); peak-only adc_* must not authorise pulse-shape claims\"\n"
       << "  }";
  } else {
    os << ",\n"
       << "  \"digitizer\": {\"validation_status\": \"MISSING\"}";
  }
  os << "\n}\n";
}

