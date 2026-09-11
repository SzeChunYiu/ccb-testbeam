// main.cc — CCB single-stave optical simulation entry point (issue #796).
//
// One immutable config per invocation -> one output file (blueprint "Run
// structure"). Batch/headless by default; visualization is an optional CMake
// target (CCB_ENABLE_VIS) and never a hard dependency of the physics build.
#include "AppConfig.hh"
#include "BeamIntersection.hh"
#include "BuildIdentity.hh"
#include "DetectorConstruction.hh"
#include "PhysicsList.hh"
#include "ActionInitialization.hh"
#include "OpticalTables.hh"

#include "G4RunManagerFactory.hh"
#ifdef G4MULTITHREADED
#include "G4MTRunManager.hh"
#endif
#include "G4UImanager.hh"
#include "G4Run.hh"
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
#include <filesystem>
#include <string>
#include <system_error>
#include <sstream>
#include <vector>

int main(int argc, char** argv) {
  // Provenance probe used by the authorising build receipt and campaign
  // verifier.  It exits before AppConfig/Geant4 initialization and reports the
  // exact running executable digest plus compile-time source/toolchain labels.
  if (argc == 2 && std::string(argv[1]) == "--build-provenance-json") {
    std::cout << ccb::build::RenderBuildIdentityJson() << '\n';
    return 0;
  }

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

    // Issue #1623: with per-event phase-space sampling the single nominal point
    // checked above is not the run. Validate the ENVELOPE -- every corner of the
    // sampled (x,y) rectangle at the extreme incidence angle -- so the ADR-0003
    // preflight cannot go vacuous once the beam is distributed.
    if (cfg.sample_position || cfg.sample_angle) {
      const double xs[2] = {cfg.sample_position ? cfg.hit_x_min_cm : cfg.hit_x_cm,
                            cfg.sample_position ? cfg.hit_x_max_cm : cfg.hit_x_cm};
      const double ys[2] = {cfg.sample_position ? cfg.hit_y_min_cm : cfg.hit_y_cm,
                            cfg.sample_position ? cfg.hit_y_max_cm : cfg.hit_y_cm};
      const double phis[4] = {0.0, 90.0, 180.0, 270.0};
      int checked = 0, missed = 0;
      double worst_path_cm = 1.0e300;
      std::string worst_reason = "ok";
      for (int ix = 0; ix < 2; ++ix) {
        for (int iy = 0; iy < 2; ++iy) {
          for (int ip = 0; ip < 4; ++ip) {
            AppConfig probe = cfg;
            probe.hit_x_cm = xs[ix];
            probe.hit_y_cm = ys[iy];
            if (cfg.sample_angle) {
              probe.theta_deg = cfg.theta_deg + cfg.theta_spread_deg;
              probe.phi_deg = phis[ip];
            } else if (ip > 0) {
              continue;  // no angular spread: one probe per corner is enough
            }
            const auto pb = ccb::ValidatePrimaryAgainstStave(probe);
            ++checked;
            if (pb.reason != "ok") { ++missed; worst_reason = pb.reason; }
            else if (pb.path_length_cm < worst_path_cm) worst_path_cm = pb.path_length_cm;
          }
        }
      }
      std::cout << "CCB_BEAM_ENVELOPE_PREFLIGHT profile=" << cfg.beam_profile_id
                << " corners_checked=" << checked
                << " corners_missing=" << missed
                << " min_path_cm=" << (missed == checked ? 0.0 : worst_path_cm)
                << " reason=" << (missed ? worst_reason : std::string("ok"))
                << std::endl;
      if (missed > 0 && !cfg.allow_miss) {
        std::cerr << "fatal: sampled phase-space envelope leaves the stave (#1623/#999): "
                  << missed << "/" << checked << " corner probes miss ("
                  << worst_reason << ")\n"
                  << "       tighten --hit-x-range/--hit-y-range/--theta-spread,"
                  << " or pass --allow-miss for an intentional miss study\n";
        return 4;
      }
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
    const std::vector<std::string> required_all = {
        "scintillator_emission", "scintillator_absorption",
        "y11_absorption", "y11_emission", "y11_bulk_attenuation",
        "tio2_reflectivity", "sipm_pde"};
    const auto errors = tables.ValidateRequired(required_all);
    if (!errors.empty()) {
      if (cfg.strict_optical) {
        std::cerr << "fatal: strict optical-table validation failed:\n";
        for (const auto& error : errors) {
          std::cerr << "  - " << error << '\n';
        }
        return 3;
      }
      // Permissive development path (#978): record non-authorising fallback.
      cfg.optical_fallback_used = true;
      cfg.authorising = false;
      std::cerr << "warning: optical-table validation failed; continuing with "
                   "allow-optical-fallback (authorising=false):\n";
      for (const auto& error : errors) {
        std::cerr << "  - " << error << '\n';
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
      PhysicsList::Build(cfg.physics_list, cfg.production_cut_mm, cfg.wls_time_profile));
  // geometry_hash is deterministic (constructor), so actions can be set now.
  runManager->SetUserInitialization(
      new ActionInitialization(cfg, tables,
                              detector->GeometryHash(),
                              detector->PhysicsHash(),
                              detector->OpticalHash()));

  // Construct geometry + physics; prints the geometry report (OVERLAP_CHECK_PASS).
  runManager->Initialize();

  // Issue #1091: make the QGSP_BIC neutron tracking-time cut explicit via the
  // Geant4 UI messenger (G4NeutronKiller /physics_engine/neutron/timeLimit).
  if (!cfg.neutron_tracking_time_cut_configured) {
    std::cerr << "fatal: neutron tracking-time cut is unset (#1091 fail-closed)\n";
    delete runManager;
    return 4;
  }
  {
    std::ostringstream neutron_cmd;
    neutron_cmd << "/physics_engine/neutron/timeLimit "
                << cfg.neutron_time_cut_us << " microsecond";
    auto* ui_neutron = G4UImanager::GetUIpointer();
    const int neutron_status = ui_neutron->ApplyCommand(neutron_cmd.str());
    if (neutron_status != 0) {
      std::cerr << "fatal: Geant4 neutron time-limit UI command failed with status "
                << neutron_status << ": " << neutron_cmd.str() << '\n';
      delete runManager;
      return 4;
    }
    std::cout << "CCB_NEUTRON_TIMECUT policy_id=" << cfg.neutron_timecut_policy_id
              << " time_cut_us=" << cfg.neutron_time_cut_us
              << " status=" << cfg.neutron_tracking_time_cut_status << std::endl;
  }

  // Optional: serialize the PRODUCTION geometry to GDML (for Opticks ingestion)
  // and exit. The spike's dump_gdml promoted to a first-class main option, so
  // production geometry -> Opticks reproducibly (booleans + TiO2 preserved).
  if (!cfg.dump_gdml.empty()) {
    G4GDMLParser parser;
    parser.SetRegionExport(false);
    G4VPhysicalVolume* world =
        G4TransportationManager::GetTransportationManager()
            ->GetNavigatorForTracking()->GetWorldVolume();
    // G4GDMLParser::Write raises a FATAL G4Exception ("File ... already
    // exists!") rather than overwriting, which aborts the process on SIGABRT.
    // That made --dump-gdml succeed exactly once per output path: the CTest
    // export case passed on a fresh build tree and died on every rerun. Remove
    // a stale file first so the export is idempotent, and fail cleanly (not on
    // a signal) if the path exists and cannot be cleared.
    {
      std::error_code ec;
      if (std::filesystem::exists(cfg.dump_gdml, ec)) {
        std::filesystem::remove(cfg.dump_gdml, ec);
        if (ec || std::filesystem::exists(cfg.dump_gdml)) {
          std::cerr << "fatal: --dump-gdml target '" << cfg.dump_gdml
                    << "' already exists and could not be replaced: "
                    << ec.message() << '\n';
          delete runManager;
          return 5;
        }
      }
    }
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
    const G4Run* current = runManager->GetCurrentRun();
    const int done = current ? current->GetNumberOfEvent() : -1;
    if (done != cfg.n_events) {
      std::cerr << "fatal: processed event count " << done
                << " != requested " << cfg.n_events << '\n';
      delete runManager;
      return 5;
    }
  }

  delete runManager;
  std::cout << "CCB_STAVE_END" << std::endl;
  return 0;
}
