#!/usr/bin/env python3
"""Fail closed on production p+d source-model configuration drift.

Repository-level checks only: this verifies source metadata/table byte identity and
that tracked Krakow production macros configure the source-bound cross section.
It does not prove which bytes a remote executable opened at runtime; runtime
receipt binding remains #1608.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "geant4/src_patch"
SOURCE = PATCH / "sigma_pd_cm_190.source.json"
MODEL = PATCH / "scattering_source_model_v1.json"
TABLE = PATCH / "sigma_pd_cm_190.txt"
MACROS = [
    ROOT / "geant4/macros/run_krakow.mac",
    ROOT / "geant4/macros/run_krakow_100k.mac",
    ROOT / "geant4/macros/run_krakow_2m.mac",
]
CS_RE = re.compile(r"^\s*/ElGen/CSFile\s+(\S+)\s*$", re.MULTILINE)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    errors: list[str] = []
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    model = json.loads(MODEL.read_text(encoding="utf-8"))
    table_hash = sha256(TABLE)

    expected_source_hash = str(source.get("data_sha256", ""))
    expected_model_hash = str(model.get("cross_section_table", {}).get("sha256", ""))
    if table_hash != expected_source_hash:
        errors.append(
            f"table bytes {table_hash} disagree with source sidecar {expected_source_hash}"
        )
    if table_hash != expected_model_hash:
        errors.append(
            f"table bytes {table_hash} disagree with source-model declaration {expected_model_hash}"
        )
    if source.get("reaction") != model.get("reaction"):
        errors.append("source/model reaction identity mismatch")
    if float(source.get("incident_proton_kinetic_energy_MeV", -1)) != float(
        model.get("incident_proton_kinetic_energy_MeV", -2)
    ):
        errors.append("source/model incident-energy identity mismatch")
    if model.get("target_polar_angle_density") != (
        "p(theta_cm) proportional to (dσ/dΩ)(theta_cm) * sin(theta_cm)"
    ):
        errors.append("unexpected source angular-density contract")
    if model.get("source_model_status") != (
        "NOMINAL_TRUTH_REFERENCE_NONAUTHORISING_FOR_DETECTOR_CLAIMS"
    ):
        errors.append("source model must remain non-authorising for detector claims")

    for macro in MACROS:
        text = macro.read_text(encoding="utf-8")
        matches = CS_RE.findall(text)
        if len(matches) != 1:
            errors.append(f"{macro.relative_to(ROOT)} must configure exactly one /ElGen/CSFile")
            continue
        configured = matches[0]
        if configured.lower() == "null":
            errors.append(f"{macro.relative_to(ROOT)} enables forbidden uniform-CM fallback")
        if Path(configured).name != TABLE.name:
            errors.append(
                f"{macro.relative_to(ROOT)} uses {configured!r}, expected source-bound {TABLE.name!r}"
            )
        if "/ElGen/E 190." not in text and "/ElGen/E 190 " not in text:
            errors.append(f"{macro.relative_to(ROOT)} is not explicitly configured at 190 MeV")

    if errors:
        print("SCATTERING_SOURCE_CONTRACT: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("SCATTERING_SOURCE_CONTRACT: PASS")
    print(f"table_sha256={table_hash}")
    print("All tracked Krakow production macros request the source-bound 190 MeV p+d table.")
    print("Runtime opened-file identity and cross-section uncertainty propagation remain unvalidated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
