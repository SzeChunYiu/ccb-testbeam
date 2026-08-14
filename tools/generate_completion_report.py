#!/usr/bin/env python3
"""Generate the project-completion report skeleton + closure matrix.

Uses tools.ccbprov to create reports/project_completion_<UTCSTAMP>/ with a
machine-readable closure_matrix.csv/json and a run manifest. Run from repo root:

    python tools/generate_completion_report.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools.ccbprov.closure import ClosureRow, write_closure_matrix
from tools.ccbprov.manifest import RunManifest
from tools.ccbprov.report import init_report_dir


def rows() -> list[ClosureRow]:
    def acc(criterion, passed, evidence=None):
        return {"criterion": criterion, "passed": passed, "evidence": evidence}

    return [
        ClosureRow(
            task_id="CCB-796-CODE",
            status="DONE",
            issue="#796",
            dependencies=[],
            evidence=[
                "geant4/single_stave/ (11 headers + 12 sources)",
                "geant4/single_stave/tests/test_geometry_report_offline.py (5 passed)",
                "non-Geant4 core compiled + functionally verified (SHA-256 == system shasum)",
            ],
            acceptance=[
                acc("primary crosses 2.0 cm normal thickness (not 50 cm)", True,
                    "PrimaryGeneratorAction.cc: z0=-half_z-1mm, dir +z"),
                acc("fibres rotated along x, contained in bar, overlap-checked", True,
                    "DetectorConstruction.cc: rotateY(90deg); pSurfChk=true"),
                acc("photons counted at named sensor boundary, not fibre Edep", True,
                    "SteppingAction.cc + TrackingAction.cc"),
                acc("one immutable config per run -> one output (no overwrite)", True,
                    "RunAction.cc single OpenFile; main.cc single BeamOn"),
                acc("headless CMake independent of Qt", True,
                    "CMakeLists.txt CCB_ENABLE_VIS=OFF default; parses to Geant4 dep only"),
                acc("seed/geometry hash/optical-table sha256 in output meta", True,
                    "RunAction::WriteMetadataSidecar -> <output>.meta.json"),
            ],
            notes="Code complete + offline-verified. Compile/run is CCB-796-RUN.",
        ),
        ClosureRow(
            task_id="CCB-796-RUN",
            status="BLOCKED_COMPUTE",
            issue="#796",
            dependencies=["CCB-796-CODE"],
            evidence=["slurm/build.sh", "slurm/submit_calibration.sh", "slurm/points_example.csv"],
            acceptance=[
                acc("Geant4 build passes (module load Geant4; bash slurm/build.sh)", False,
                    "no Geant4 locally; runs on LUNARC"),
                acc("3 ctests green (geometry, proton smoke, geometry-report)", False, None),
                acc("calibration ntuples produced per grid point", False, None),
            ],
            notes="Needs LUNARC Geant4 + optical physics. All inputs staged.",
        ),
        ClosureRow(
            task_id="CCB-796-ANALYSIS",
            status="DONE",
            issue="#796",
            dependencies=[],
            evidence=[
                "scripts/single_stave/{make_single_stave_fixture,analyze_single_stave,extract_g4_entry_energies}.py",
                "tests/test_single_stave_analysis.py (9 passed)",
                "scripts/analyze_mc_stave_response.py (stub replaced -> forwarding CLI)",
            ],
            acceptance=[
                acc("analyzer accepts paths as args (no hard-coded LUNARC dirs)", True,
                    "argparse CLIs; verified end-to-end on fixture"),
                acc("photon-count inequality enforced (gen>=arrival>=detected)", True,
                    "test_analyze_rejects_inequality_violation"),
                acc("writes event + summary tables, result.json, manifest, figures", True,
                    "/tmp/f_report artifacts verified"),
            ],
            notes="Offline-tested. Real full-MC entry-energy extraction = CCB-796-ENTRY.",
        ),
        ClosureRow(
            task_id="CCB-796-ENTRY",
            status="BLOCKED_EXTERNAL",
            issue="#796",
            dependencies=["CCB-796-ANALYSIS"],
            evidence=["scripts/single_stave/extract_g4_entry_energies.py",
                      "synthetic-ROOT fixture test (test_extract_root_fixture_quantile_grid)"],
            acceptance=[
                acc("empirical stave-entry spectra per species/stave/angle from full MC", False,
                    "needs full-MC truth ROOT on fs10 (LUNARC)"),
                acc("quantile grid (5/16/50/84/95%) + Bragg structure", False, None),
            ],
            notes="Branch contract fixed offline (uproot bug patched); real tree on LUNARC.",
        ),
        ClosureRow(
            task_id="CCB-PROV",
            status="DONE",
            issue=None,
            dependencies=[],
            evidence=["tools/ccbprov/", "schemas/*.schema.json",
                      "tests/test_ccbprov.py (10 passed)"],
            acceptance=[
                acc("run manifest builder validates against schema", True, "test_manifest_to_dict_is_schema_valid"),
                acc("closure matrix writer (CSV+JSON), enum-validated", True, "test_write_closure_matrix_*"),
                acc("report dir init (REPORT/closure/manifest/commands/figures), no overwrite", True,
                    "test_init_report_dir_creates_artifacts_and_no_overwrite"),
            ],
            notes="Reproducibility substrate for every downstream run.",
        ),
        ClosureRow(
            task_id="CCB-DELTAE",
            status="SUPERSEDED",
            issue="#618",
            dependencies=[],
            evidence=["conflict_supervisor_deltaE_E.md",
                      "git history: existed at ca30589f, absent at d3b2beb"],
            acceptance=[
                acc("supervisor_deltaE_E.py present at audited commit", False,
                    "absent at d3b2beb; handoff defects doc references a superseded file"),
            ],
            notes="Stale handoff reference. eventno-join + Sample I/II fixes QUEUED (CCB-DELTAE-FIX).",
        ),
        ClosureRow(
            task_id="CCB-DELTAE-FIX",
            status="READY",
            issue="#618",
            dependencies=["CCB-DELTAE"],
            evidence=["scripts/*deltaE*/*.py joins on eventno alone (collision risk)"],
            acceptance=[
                acc("event key is (file_id, run, event) across all deltaE-E scripts", False, None),
                acc("Sample I/II inclusive/exclusive made explicit; thresholds applied", False, None),
                acc("deterministic seed; hexbin+quantiles; event tables emitted", False, None),
            ],
            notes="Needs data on LUNARC to validate; scoped and queued, not silently dropped.",
        ),
        ClosureRow(
            task_id="CCB-844-GEOM",
            status="BLOCKED_COMPUTE",
            issue="#844",
            dependencies=[],
            evidence=["geant4/configs/krakow.geoconf (referenced)"],
            acceptance=[
                acc("hash + inspect krakow_109_8-38deg_4-71deg.root deployed geometry", False,
                    "ROOT file + ROOT/VGM on LUNARC required"),
                acc("verify 8 B bars + 4 A bars, thickness, passive layers", False, None),
            ],
            notes="Geometry inventory + cross-section render pending LUNARC/ROOT.",
        ),
        ClosureRow(
            task_id="CCB-844-SCAN",
            status="BLOCKED_COMPUTE",
            issue="#844",
            dependencies=["CCB-844-GEOM"],
            evidence=[],
            acceptance=[
                acc("staged stopping-depth scan (overlap/geantino -> pilot -> final)", False, None),
                acc("chi2/ndf + likelihood GoF; do NOT reuse 11.12 g/cm2 as calibrated", False, None),
            ],
            notes="Depends on pinned deployed geometry and LUNARC compute.",
        ),
        ClosureRow(
            task_id="CCB-TIMING",
            status="BLOCKED_COMPUTE",
            issue=None,
            dependencies=[],
            evidence=["scripts/mv4_timing_study.py (1/A fix present in tree)"],
            acceptance=[
                acc("rerun with v2 gain (not 246 ADC/MeV); load anchors from result files", False, None),
                acc("report sigma68/RMS/core-sigma/tail-frac/chi2 + LORO spread", False, None),
            ],
            notes="Code present; closure requires rerun on LUNARC data + calibration cards.",
        ),
        ClosureRow(
            task_id="CCB-797-PAPER",
            status="IN_PROGRESS",
            issue="#797",
            dependencies=["CCB-796-RUN", "CCB-844-SCAN", "CCB-TIMING"],
            evidence=["paper/ (skeleton: outline, crosswalks, limitations; canonical claim ledger at docs/claim_ledger.csv)"],
            acceptance=[
                acc("every claim maps to result-file path + commit + uncertainty + status", False,
                    "claims populate as results land"),
            ],
            notes="Skeleton + claim ledger in place; content gated on the compute-blocked results.",
        ),
    ]


def main() -> int:
    report_dir = init_report_dir(REPO / "reports", "project_completion",
                                 utc_stamp="20260720T075158Z")
    csv_path = report_dir / "closure_matrix.csv"
    json_path = report_dir / "closure_matrix.json"
    write_closure_matrix(rows(), csv_path, json_path)

    mani = RunManifest(
        task_id="CCB-INFRA-20260720",
        command=["python", "tools/generate_completion_report.py"],
        seed_policy="fixed-seed offline infrastructure build",
    )
    mani.set_environment({"note": "LUNARC-independent infrastructure build"})
    mani.start()
    mani.add_output(str(csv_path))
    mani.add_output(str(json_path))
    mani.finish()
    mani.write(report_dir / "manifest.json")

    print(f"report dir: {report_dir}")
    print(f"closure rows: {len(rows())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
