#!/usr/bin/env python3
"""Fail-closed optical CSV semantic schema tests (issues #978/#980).

Mirrors the C++ OpticalTables property contract closely enough to catch
unit/range/malformed-row regressions without requiring a Geant4 rebuild.
"""
from __future__ import annotations

import argparse
import math
import re
import shutil
import tempfile
from pathlib import Path


SCHEMAS = {
    "scintillator_emission": ("nm", "rel", "nonneg"),
    "scintillator_absorption": ("nm", "cm", "poslen"),
    "y11_emission": ("nm", "rel", "nonneg"),
    "y11_absorption": ("nm", "mm", "poslen"),
    "y11_bulk_attenuation": ("nm", "cm", "poslen"),
    "tio2_reflectivity": ("nm", "frac", "unit"),
    "sipm_pde": ("nm", "frac", "unit"),
}


def normalize_unit(u: str) -> str:
    u = u.strip().lower()
    u = re.split(r"[\s(]", u, maxsplit=1)[0]
    if u in {"fraction", "probability"}:
        return "frac"
    if u in {"relative", "a.u.", "au"}:
        return "rel"
    return u


def load_csv(path: Path) -> dict:
    units_x = units_y = status = ""
    xs: list[float] = []
    ys: list[float] = []
    errors: list[str] = []
    for i, line in enumerate(path.read_text().splitlines(), 1):
        t = line.strip()
        if not t:
            continue
        if t.startswith("#"):
            if "units_x:" in t:
                units_x = t.split("units_x:", 1)[1].strip()
            elif "units_y:" in t:
                units_y = t.split("units_y:", 1)[1].strip()
            elif "status:" in t:
                status = t.split("status:", 1)[1].strip()
            continue
        parts = [p for p in re.split(r"[\s,]+", t.replace(",", " ")) if p]
        if len(parts) != 2:
            errors.append(f"line {i}: expected two columns, got {parts!r}")
            continue
        try:
            x = float(parts[0])
            y = float(parts[1])
        except ValueError:
            errors.append(f"line {i}: non-numeric {parts!r}")
            continue
        xs.append(x)
        ys.append(y)
    return {
        "units_x": units_x,
        "units_y": units_y,
        "status": status,
        "x": xs,
        "y": ys,
        "errors": errors,
    }


def validate(key: str, curve: dict) -> list[str]:
    errs = list(curve["errors"])
    if not curve["x"]:
        return [f"{key}: empty"]
    if not curve["units_x"]:
        errs.append(f"{key}: missing units_x")
    if not curve["units_y"]:
        errs.append(f"{key}: missing units_y")
    if not curve["status"]:
        errs.append(f"{key}: missing status")
    ux, uy, pol = SCHEMAS[key]
    if curve["units_x"] and normalize_unit(curve["units_x"]) != ux:
        errs.append(f"{key}: units_x {curve['units_x']!r} != {ux}")
    if curve["units_y"] and normalize_unit(curve["units_y"]) != uy:
        errs.append(f"{key}: units_y {curve['units_y']!r} != {uy}")
    for x, y in zip(curve["x"], curve["y"]):
        if not (math.isfinite(x) and math.isfinite(y)):
            errs.append(f"{key}: non-finite point")
            break
        if not (100.0 <= x <= 2000.0):
            errs.append(f"{key}: x out of wavelength window")
            break
        if pol == "unit" and not (0.0 <= y <= 1.0):
            errs.append(f"{key}: y {y} outside [0,1]")
            break
        if pol == "nonneg" and y < 0:
            errs.append(f"{key}: negative intensity")
            break
        if pol == "poslen" and not (y > 0):
            errs.append(f"{key}: non-positive length")
            break
    for i in range(1, len(curve["x"])):
        if curve["x"][i] <= curve["x"][i - 1]:
            errs.append(f"{key}: x not strictly ascending")
            break
    return errs


def assert_shipped_ok(optical_dir: Path) -> None:
    all_errs: list[str] = []
    for key in SCHEMAS:
        path = optical_dir / f"{key}.csv"
        assert path.is_file(), f"missing {path}"
        all_errs.extend(validate(key, load_csv(path)))
    if all_errs:
        raise AssertionError("shipped optical tables failed schema:\n" + "\n".join(all_errs))


def assert_negative_cases(optical_dir: Path) -> None:
    cases = [
        ("units_x: angstrom\nunits_y: frac\nstatus: BAD\n450, 0.4\n", "angstrom"),
        ("units_x: nm\nunits_y: percent\nstatus: BAD\n450, 40\n", "percent"),
        ("units_x: nm\nunits_y: cm\nstatus: BAD\n450, 0\n", "non-positive"),
        ("units_x: nm\nunits_y: frac\nstatus: BAD\n450, 1.2\n", "[0,1]"),
        ("units_x: nm\nunits_y: frac\nstatus: BAD\n450, 0.4, 9\n", "two columns"),
        ("units_x: nm\nunits_y: frac\nstatus: BAD\n450, 0.4\n450, 0.5\n", "ascending"),
    ]
    with tempfile.TemporaryDirectory(prefix="opt_schema_") as tmp:
        root = Path(tmp)
        for name, _ in SCHEMAS.items():
            shutil.copy(optical_dir / f"{name}.csv", root / f"{name}.csv")
        target = root / "sipm_pde.csv"
        for payload, expect in cases:
            # Rebuild header-like comments
            body = ""
            for line in payload.splitlines():
                if line.startswith("units_") or line.startswith("status"):
                    body += f"# {line}\n"
                else:
                    body += line + "\n"
            target.write_text(body)
            errs = validate("sipm_pde", load_csv(target))
            joined = " | ".join(errs).lower()
            if not errs:
                raise AssertionError(f"expected failure for case {expect!r}, got OK")
            # For absorption-like zero length case, swap property temporarily
            if expect == "non-positive":
                # validate against absorption schema semantics
                errs2 = validate("scintillator_absorption", load_csv(target))
                if not any("non-positive" in e.lower() or "positive" in e.lower() or "y " in e.lower() for e in errs2):
                    # sipm_pde with y=0 is valid for unit interval; dedicated check:
                    c = load_csv(target)
                    c["units_y"] = "cm"
                    errs3 = validate("scintillator_absorption", c)
                    if not errs3:
                        raise AssertionError("zero attenuation should fail")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--optical-dir", type=Path, required=True)
    args = ap.parse_args()
    assert_shipped_ok(args.optical_dir)
    assert_negative_cases(args.optical_dir)
    # ledger presence
    ledger = args.optical_dir / "optical_constants_ledger.conf"
    if not ledger.is_file():
        raise AssertionError(f"missing ledger {ledger}")
    print("OPTICAL_SCHEMA_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
