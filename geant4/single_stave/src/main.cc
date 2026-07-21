// main.cc — CCB single-stave optical simulation entry point (issue #796).
//
// One immutable config per invocation -> one output file (blueprint "Run
// structure"). Batch/headless by default; visualization is an optional CMake
// target (CCB_ENABLE_VIS) and never a hard dependency of the physics build.
#include "AppConfig.hh"
#include "DetectorConstruction.hh"
#include "PhysicsList.hh"
#include "ActionInitialization.hh"
#include "OpticalTables.hh"

#include "G4RunManagerFactory.hh"
#include "G4UImanager.hh"
#include "Randomize.hh"

#ifdef CCB_ENABLE_VIS
#include "G4VisExecutive.hh"
#include "G4UIExecutive.hh"
#endif

#include <iostream>

int main(int argc, char** argv) {
  AppConfig cfg;
  if (!cfg.ParseArgs(argc, argv)) {
    // --help prints usage and returns false; a parse error also returns false.
    return (argc > 1 && (std::string(argv[1]) == "-h" ||
                         std::string(argv[1]) == "--help")) ? 0 : 2;
  }

  std::cout << "CCB_STAVE_START " << cfg.Describe() << std::endl;

  // Seed the master engine before constructing the run manager. In MT builds,
  // Geant4 derives per-event worker seeds from this master state so results are
  // reproducible independently of worker scheduling and thread count.
  CLHEP::HepRandom::setTheSeed(static_cast<long>(cfg.seed));

  // Load versioned optical tables once (hashes recorded in output metadata).
  OpticalTables tables = OpticalTables::LoadDir(cfg.optical_dir);

  auto* runManager =
      G4RunManagerFactory::CreateRunManager(G4RunManagerType::Default);

  auto* detector = new DetectorConstruction(cfg);
  runManager->SetUserInitialization(detector);
  runManager->SetUserInitialization(PhysicsList::Build("QGSP_BIC"));
  // geometry_hash is deterministic (constructor), so actions can be set now.
  runManager->SetUserInitialization(
      new ActionInitialization(cfg, tables, detector->GeometryHash()));

  // Construct geometry + physics; prints the geometry report (OVERLAP_CHECK_PASS).
  runManager->Initialize();

  auto* ui = G4UImanager::GetUIpointer();

  if (!cfg.macro.empty()) {
#ifdef CCB_ENABLE_VIS
    // If a macro references vis, set up the vis manager.
    auto* vis = new G4VisExecutive();
    vis->Initialize();
#endif
    ui->ApplyCommand("/control/execute " + cfg.macro);
#ifdef CCB_ENABLE_VIS
    delete vis;
#endif
  } else {
    // Batch: run the configured number of events.
    ui->ApplyCommand("/run/verbose 0");
    ui->ApplyCommand("/event/verbose 0");
    ui->ApplyCommand("/tracking/verbose 0");
    runManager->BeamOn(cfg.n_events);
  }

  delete runManager;
  std::cout << "CCB_STAVE_END" << std::endl;
  return 0;
}
