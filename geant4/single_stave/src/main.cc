// main.cc — CCB single-stave optical simulation entry point (issue #796).
//
// One immutable config per invocation -> one output file (blueprint "Run
// structure"). Batch/headless by default; visualization is an optional CMake
// target (CCB_ENABLE_VIS) and never a hard dependency of the physics build.
#include "AppConfig.hh"
#include "BeamIntersection.hh"
#include "DetectorConstruction.hh"
#include "PhysicsList.hh"
#include "ActionInitialization.hh"
#include "OpticalTables.hh"

#include "G4RunManagerFactory.hh"
#ifdef G4MULTITHREADED
#include "G4MTRunManager.hh"
#endif
#include "G4UImanager.hh"
#include "G4TransportationManager.hh"
#include "G4VPhysicalVolume.hh"
#include "G4GDMLParser.hh"
#include "Randomize.hh"

#ifdef CCB_ENABLE_VIS
#include "G4VisExecutive.hh"
#include "G4UIExecutive.hh"
#endif

#include <cstdlib>
#include <exception>
#include <iostream>
#include <string>

int main(int argc, char** argv) {
  AppConfig cfg;
  if (!cfg.ParseArgs(argc, argv)) {
    // --help prints usage and returns false; a parse error also returns false.
    return (argc > 1 && (std::string(argv[1]) == "-h" ||
                         std::string(argv[1]) == "--help")) ? 0 : 2;
  }

  // Issue #999 / ADR-0003: geometry-aware primary preflight using
  // DetectorConstruction extents (no duplicate limits in AppConfig).
  {
    const auto beam = ccb::ValidatePrimaryAgainstStave(cfg);
    std::cout << "CCB_BEAM_PREFLIGHT intersects=" << (beam.intersects ? 1 : 0)
              << " enters_neg_z=" << (beam.enters_neg_z_face ? 1 : 0)
              << " path_cm=" << beam.path_length_cm
              << " reason=" << beam.reason << std::endl;
    if (beam.reason != "ok" && !cfg.allow_miss) {
      std::cerr << "fatal: primary does not intersect the stave (#999): "
                << beam.reason
                << "\n       pass --allow-miss only for intentional miss studies\n";
      return 4;
    }
  }

  // Seed the master engine before constructing the run manager. In MT builds,
  // Geant4 derives per-event worker seeds from this master state so results are
  // reproducible independently of worker scheduling and thread count.
  CLHEP::HepRandom::setTheSeed(static_cast<long>(cfg.seed));

  // Load the action/provenance optical-table instance with the SAME strictness
  // requested for DetectorConstruction. Historically this call omitted
  // cfg.strict_optical, allowing SteppingAction::PdeAt() to receive an empty
  // sipm_pde curve and silently use its 40% fallback in a nominally strict run.
  OpticalTables tables;
  try {
    tables = OpticalTables::LoadDir(cfg.optical_dir, cfg.strict_optical);
    if (cfg.strict_optical) {
      const auto errors = tables.ValidateRequired({"sipm_pde"});
      if (!errors.empty()) {
        std::cerr << "fatal: strict action-level optical-table validation failed:\n";
        for (const auto& error : errors) {
          std::cerr << "  - " << error << '\n';
        }
        return 3;
      }
    }
  } catch (const std::exception& exc) {
    std::cerr << "fatal: optical-table initialization failed: " << exc.what() << '\n';
    return 3;
  }

  auto* runManager =
      G4RunManagerFactory::CreateRunManager(G4RunManagerType::Default);
#ifdef G4MULTITHREADED
  // Set this before Initialize(), when workers are created. Geant4 may ignore
  // the request when G4FORCENUMBEROFTHREADS is set, so read the effective value
  // back from the run manager and preserve both values in run provenance.
  if (auto* mt = dynamic_cast<G4MTRunManager*>(runManager)) {
    mt->SetNumberOfThreads(cfg.n_threads);
    cfg.n_threads_effective = mt->GetNumberOfThreads();
  } else {
    cfg.n_threads_effective = runManager->GetNumberOfThreads();
  }
#else
  cfg.n_threads_effective = runManager->GetNumberOfThreads();
#endif
  if (const char* forced = std::getenv("G4FORCENUMBEROFTHREADS")) {
    cfg.g4_force_number_of_threads = forced;
  }

  std::cout << "CCB_STAVE_START " << cfg.Describe() << std::endl;
  if (cfg.n_threads_effective != cfg.n_threads) {
    std::cerr << "warning: requested " << cfg.n_threads
              << " worker threads but Geant4 configured "
              << cfg.n_threads_effective;
    if (!cfg.g4_force_number_of_threads.empty()) {
      std::cerr << " (G4FORCENUMBEROFTHREADS="
                << cfg.g4_force_number_of_threads << ")";
    }
    std::cerr << std::endl;
  }

  auto* detector = new DetectorConstruction(cfg);
  runManager->SetUserInitialization(detector);
  runManager->SetUserInitialization(
      PhysicsList::Build("QGSP_BIC", cfg.production_cut_mm, cfg.wls_time_profile));
  // geometry_hash is deterministic (constructor), so actions can be set now.
  runManager->SetUserInitialization(
      new ActionInitialization(cfg, tables, detector->GeometryHash()));

  // Construct geometry + physics; prints the geometry report (OVERLAP_CHECK_PASS).
  runManager->Initialize();

  // Optional: serialize the PRODUCTION geometry to GDML (for Opticks ingestion)
  // and exit. The spike's dump_gdml promoted to a first-class main option, so
  // production geometry -> Opticks reproducibly (booleans + TiO2 preserved).
  if (!cfg.dump_gdml.empty()) {
    G4GDMLParser parser;
    parser.SetRegionExport(false);
    G4VPhysicalVolume* world =
        G4TransportationManager::GetTransportationManager()
            ->GetNavigatorForTracking()->GetWorldVolume();
    parser.Write(cfg.dump_gdml, world);
    std::cout << "CCB_GDML_WROTE " << cfg.dump_gdml
              << " world=" << world->GetName() << std::endl;
    delete runManager;
    return 0;
  }

  auto* ui = G4UImanager::GetUIpointer();
  auto apply_required = [&](const G4String& command) -> bool {
    const int status = ui->ApplyCommand(command);
    if (status != 0) {
      std::cerr << "fatal: Geant4 UI command failed with status " << status
                << ": " << command << '\n';
      return false;
    }
    return true;
  };

  if (!cfg.macro.empty()) {
#ifdef CCB_ENABLE_VIS
    // If a macro references vis, set up the vis manager.
    auto* vis = new G4VisExecutive();
    vis->Initialize();
#endif
    const bool macro_ok = apply_required("/control/execute " + cfg.macro);
#ifdef CCB_ENABLE_VIS
    delete vis;
#endif
    if (!macro_ok) {
      delete runManager;
      return 4;
    }
  } else {
    // Batch: run the configured number of events. Required UI setup commands
    // are fail-closed so an invalid Geant4 command cannot be ignored while the
    // process still advertises a successful scientific run.
    if (!apply_required("/run/verbose 0") ||
        !apply_required("/event/verbose 0") ||
        !apply_required("/tracking/verbose 0")) {
      delete runManager;
      return 4;
    }
    runManager->BeamOn(cfg.n_events);
  }

  delete runManager;
  std::cout << "CCB_STAVE_END" << std::endl;
  return 0;
}
