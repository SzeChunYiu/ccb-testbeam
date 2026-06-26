"""Reference registry for MC-validation publication/wiki drafts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ccb_mc_validation.io.artifact_store import atomic_write_json


REFERENCE_RECORDS = [
    {
        "id": "REF-RUNBOOK",
        "type": "project-specification",
        "title": "CCB testbeam Codex MC validation completion thesis runbook",
        "citation": "Project runbook supplied in repository session; governs execution, reporting, thesis, release requirements.",
        "status": "AVAILABLE",
        "note": "Local operator-provided specification, not an external literature source.",
    },
    {
        "id": "REF-VALIDATION-ARTIFACTS",
        "type": "frozen-artifact",
        "title": "Selected LUNARC MC validation artifacted run",
        "citation": "Run 20260625T064500Z_full_input_artifacted, SLURM job 3316536, frozen validation artifacts under configured LUNARC artifact root.",
        "status": "AVAILABLE",
        "note": "Primary evidence for current MV1-MV3/MV9 artifact-summary claims.",
    },
    {
        "id": "REF-GEANT4-2003",
        "type": "simulation-toolkit-literature",
        "title": "GEANT4--a simulation toolkit",
        "citation": "S. Agostinelli et al., Nuclear Instruments and Methods in Physics Research A 506 (2003) 250-303, doi:10.1016/S0168-9002(03)01368-8.",
        "status": "AVAILABLE",
        "note": "Cites the detector-transport toolkit family used for MC truth/artifact interpretation; does not validate this project's geometry or digitizer by itself.",
    },
    {
        "id": "REF-GEANT4-2006",
        "type": "simulation-toolkit-literature",
        "title": "Geant4 developments and applications",
        "citation": "J. Allison et al., IEEE Transactions on Nuclear Science 53 (2006) 270-278, doi:10.1109/TNS.2006.869826.",
        "status": "AVAILABLE",
        "note": "Secondary Geant4 toolkit reference for development/application context; project-specific validation remains artifact-gated.",
    },
    {
        "id": "REF-PDG-RPP-2024",
        "type": "particle-data-review",
        "title": "Review of Particle Physics",
        "citation": "S. Navas et al. (Particle Data Group), Physical Review D 110 (2024) 030001, doi:10.1103/PhysRevD.110.030001.",
        "status": "AVAILABLE",
        "note": "General particle-physics and passage-through-matter reference; numerical claims still require project artifact evidence.",
    },
    {
        "id": "REF-BIRKS-1964",
        "type": "scintillation-literature",
        "title": "The Theory and Practice of Scintillation Counting",
        "citation": "J. B. Birks, The Theory and Practice of Scintillation Counting, Pergamon/Macmillan, 1964.",
        "status": "AVAILABLE",
        "note": "Background reference for scintillation response and quenching vocabulary; no Birks-constant fit is claimed from current artifacts.",
    },
    {
        "id": "REF-KNOLL-2010",
        "type": "detector-textbook",
        "title": "Radiation Detection and Measurement, 4th edition",
        "citation": "G. F. Knoll, Radiation Detection and Measurement, 4th ed., Wiley, 2010, ISBN 978-0-470-13148-0.",
        "status": "AVAILABLE",
        "note": "Detector instrumentation background reference for scintillators and radiation measurements; not a substitute for run-specific calibration.",
    },
    {
        "id": "REF-ROOT-1997",
        "type": "analysis-framework-literature",
        "title": "ROOT--An object oriented data analysis framework",
        "citation": "R. Brun and F. Rademakers, Nuclear Instruments and Methods in Physics Research A 389 (1997) 81-86, doi:10.1016/S0168-9002(97)00048-X.",
        "status": "AVAILABLE",
        "note": "Cites ROOT file/data-analysis framework context for raw-data handling; selector-count truth remains guarded by project checks.",
    },
    {
        "id": "REF-FINAL-BIBLIOGRAPHY-AUDIT",
        "type": "release-blocker",
        "title": "Final publication bibliography and claim-reference audit",
        "citation": "Blocked until every thesis/wiki claim maps to either a frozen project artifact, a curated internal note, or an external literature reference.",
        "status": "BLOCKED",
        "note": "Do not invent references; the registry now contains core external references, but final publication-grade bibliography coverage remains intentionally fail-closed.",
    },
]


def generate_reference_registry(run_root: Path) -> dict[str, Any]:
    """Write JSON and Markdown reference-registry artifacts."""

    run_root = Path(run_root)
    out_dir = run_root / "reports" / "mc_validation" / "references"
    out_dir.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(tz=timezone.utc).isoformat()
    blocked = [record for record in REFERENCE_RECORDS if record["status"] != "AVAILABLE"]
    payload: dict[str, Any] = {
        "status": "PASS",
        "scope": "reference-registry",
        "final_bibliography_status": "BLOCKED" if blocked else "PASS",
        "records": REFERENCE_RECORDS,
        "blocked_count": len(blocked),
        "generated_at": generated,
    }
    atomic_write_json(out_dir / "REFERENCE_REGISTRY.json", payload)
    lines = [
        "# MC validation reference registry",
        "",
        f"- **Status:** `{payload['status']}`",
        f"- **Final bibliography:** `{payload['final_bibliography_status']}`",
        f"- **Blocked reference count:** `{payload['blocked_count']}`",
        "",
        "| ID | Type | Status | Citation | Note |",
        "|---|---|---:|---|---|",
    ]
    for record in REFERENCE_RECORDS:
        lines.append(
            f"| {record['id']} | {record['type']} | {record['status']} | {record['citation']} | {record['note']} |"
        )
    (out_dir / "REFERENCE_REGISTRY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload
