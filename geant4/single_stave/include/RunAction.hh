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

class G4Run;
struct EventData;

class RunAction : public G4UserRunAction {
 public:
  RunAction(const AppConfig& cfg, const OpticalTables& tables,
            const std::string& geometry_hash);
  ~RunAction() override;

  void BeginOfRunAction(const G4Run* run) override;
  void EndOfRunAction(const G4Run* run) override;

  // Called by EventAction at end of event to fill the per-event ntuple.
  void FillEvent(const EventData& e, int event_id);

  const AppConfig& Config() const { return cfg_; }

 private:
  void DefineNtuples();
  void WriteMetadataSidecar(const G4Run* run) const;  // <output>.meta.json

  AppConfig cfg_;
  OpticalTables tables_;
  std::string geometry_hash_;

  int nt_event_ = -1;   // per-event ntuple id
  int nt_photon_ = -1;  // per-photon ntuple id (calibration mode)
};

#endif  // CCB_RUNACTION_HH
