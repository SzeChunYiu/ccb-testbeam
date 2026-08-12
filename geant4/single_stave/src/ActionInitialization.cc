#include "ActionInitialization.hh"
#include "PrimaryGeneratorAction.hh"
#include "RunAction.hh"
#include "EventAction.hh"
#include "SteppingAction.hh"
#include "TrackingAction.hh"
#include "StackingAction.hh"

ActionInitialization::ActionInitialization(const AppConfig& cfg,
                                           const OpticalTables& tables,
                                           const std::string& geometry_hash,
                                           const std::string& physics_hash,
                                           const std::string& optical_hash)
    : cfg_(cfg), tables_(tables),
      geometry_hash_(geometry_hash), physics_hash_(physics_hash),
      optical_hash_(optical_hash) {}

void ActionInitialization::BuildForMaster() const {
  SetUserAction(new RunAction(cfg_, tables_, geometry_hash_, physics_hash_,
                              optical_hash_));
}

void ActionInitialization::Build() const {
  SetUserAction(new PrimaryGeneratorAction(cfg_));
  auto* run_action = new RunAction(cfg_, tables_, geometry_hash_, physics_hash_,
                                   optical_hash_);
  SetUserAction(run_action);
  auto* event_action = new EventAction(cfg_, tables_, run_action);
  SetUserAction(event_action);
  SetUserAction(new TrackingAction(event_action));
  SetUserAction(new SteppingAction(cfg_, tables_, event_action));
  SetUserAction(new StackingAction(cfg_));
}
