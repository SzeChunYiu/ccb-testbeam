// RunAction.hh — opens ONE output per invocation, defines the ntuples, and
// writes run-level provenance (seed, geometry hash, optical table hashes,
// config, git commit passed via env). Fixes the prototype defect where a
// BeamOn loop overwrote earlier energy points: this executable runs a single
// immutable config per invocation (see the blueprint "Run structure").
#ifndef CCB_RUNACTION_HH
#define CCB_RUNACTION_HH

#include "G4UserRunAction.hh"
#include "globals.hh"
#include "AppConfig.hh"
#include "OpticalTables.hh"
#include "ccb/sipm/Config.hh"

class G4Run;
struct EventData;

class RunAction : public G4UserRunAction {
 public:
  RunAction(const AppConfig& cfg, const OpticalTables& tables,
            const std::string& geometry_hash,
            const std::string& physics_hash,
            const std::string& optical_hash);
  ~RunAction() override;

  void BeginOfRunAction(const G4Run* run) override;
  void EndOfRunAction(const G4Run* run) override;

  // Called by EventAction at end of event to fill the per-event ntuple.
  void FillEvent(const EventData& e, int event_id);
  // GPU optical path: write the event's captured input-photon array to
  // <optical_out>/event_<id>.npy (sphoton (N,4,4) float32). No-op unless
  // cfg.gpu_optical.
  void WriteGpuPhotons(const EventData& e, int event_id);
  // CPU reference: dump the per-sensor arrival photons (sensor, wavelength,
  // time, path) to <optical_out>/cpu_event_<id>.npy, for the GPU-vs-CPU
  // parity diagnostic. No-op unless optical_out is set on a CPU run.
  void WriteCpuArrivals(const EventData& e, int event_id);

  // Persist the effective ccb-sipm-core configuration into the run sidecar (#977).
  void SetSipmDigitizerConfig(const ccb::sipm::ModelConfig& cfg);

  // Runtime digitizer diagnostics (#1069). A limit hit is fatal in EventAction;
  // these counters are recorded for the sidecar when a run still terminates.
  void NoteSipmEventDiagnostics(bool candidate_limit_reached,
                                std::size_t n_candidates_processed);

  const AppConfig& Config() const { return cfg_; }

 private:
  void DefineNtuples();
  void EnsureOpticalOutDir();                          // mkdir -p optical_out
  void WriteMetadataSidecar(const G4Run* run) const;  // <output>.meta.json

  AppConfig cfg_;
  OpticalTables tables_;
  std::string geometry_hash_;
  std::string physics_hash_;
  std::string optical_hash_;

  bool have_sipm_config_ = false;
  ccb::sipm::ModelConfig sipm_config_;
  std::size_t candidate_limit_hits_ = 0;
  std::size_t max_candidates_processed_ = 0;

  int nt_event_ = -1;   // per-event ntuple id
  int nt_photon_ = -1;  // per-photon ntuple id (calibration mode)
  int nt_neutron_ = -1; // per-step neutron diagnostics ntuple (#1091)
  std::string optical_out_dir_;  // resolved dir for GPU input-photon npy
};

#endif  // CCB_RUNACTION_HH
