#!/usr/bin/env python3
"""Compare simulated proton/deuteron dE/dx against a NIST PSTAR reference.

PURE-MATH, NO NETWORK (HARD RULE on LUNARC). The reference stopping-power table
is a static CSV committed to the repo (data/reference/stopping_power/
pstar_polystyrene.csv), fetched once on the Mac from the NIST PSTAR database.
This script only READS that local file -- it never opens a socket.

Method
------
* Simulated MASS stopping power, per (particle, energy):
    S_sim [MeV cm^2/g] = (sum edep_scint_raw_MeV / sum track_len_scint_mm)
                         * 10 [mm->cm] / rho [g/cm^3]
  The UNQUENCHED local energy deposit (edep_scint_raw_MeV) is used as a
  diagnostic proxy. It is not generally identical to the projectile's total
  energy loss when generated secondaries escape the scored volume.
* Reference (polystyrene, rho = 1.060 g/cm^3):
    proton   : linear interpolation of the PSTAR total table in log-log at E.
    deuteron : velocity scaling -- a deuteron of energy E has the same speed as
               a proton of energy E/2 (same charge z=1), so to leading order
               S_deuteron(E) ~= S_proton(E/2). This is the standard Bragg-rule/
               effective-charge approximation; NIST PSTAR has no deuteron table.
* Report: per-energy ratio S_sim/S_ref, delta %, and a numerical tolerance
  check (CCB_STOPPING_TOLERANCE_PCT, default 10%). This is DIAGNOSTIC_ONLY,
  not an accepted stopping-power closure.

Input (sim event CSV, comment lines starting with '#'): one row per event with
the sim's per-event columns. Flexible aliases are accepted:
    particle : particle
    energy   : ke_MeV | kinetic_energy_MeV | energy_MeV
    edep_raw : edep_scint_raw_MeV | edep_raw_MeV   (falls back to the quenched
                edep_scint_MeV with a warning -- that compares against the
                *quenched* yield, not raw PSTAR)
    track_len: track_len_scint_mm | track_length_scint_mm | track_length_scint_cm
                (a '_cm' column is auto-converted to mm)

If you only have ROOT ntuples, export them to CSV first (e.g. via uproot); this
script deliberately depends on the Python stdlib only so it runs anywhere.

Usage:
    python3 compare_stopping_power.py --sim events.csv \
        --reference data/reference/stopping_power/pstar_polystyrene.csv \
        --out stopping_power_compare.csv
    python3 compare_stopping_power.py --self-test
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import math
import os
import statistics
import sys
import tempfile
from pathlib import Path

# ---- defaults (all env-overridable; no magic numbers without an escape hatch) ----
DEFAULT_RHO = float(os.environ.get("CCB_POLYSTYRENE_RHO", "1.060"))  # g/cm^3
DEFAULT_TOL = float(os.environ.get("CCB_STOPPING_TOLERANCE_PCT", "10.0"))
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
DEFAULT_REF = REPO_ROOT / "data" / "reference" / "stopping_power" / "pstar_polystyrene.csv"


def sha256_file(path: Path) -> str:
    """Return a lowercase SHA-256 digest for provenance."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_reference(path: Path) -> list[tuple[float, float, float, float]]:
    """Return sorted [(energy_MeV, electronic, nuclear, total)] MeV cm^2/g."""
    rows = []
    with path.open() as f:
        rdr = csv.DictReader((ln for ln in f if not ln.lstrip().startswith("#")))
        for r in rdr:
            try:
                e = float(r["energy_MeV"])
                el = float(r["electronic_MeV_cm2_g"])
                nu = float(r["nuclear_MeV_cm2_g"])
                tot = float(r["total_MeV_cm2_g"])
            except (KeyError, ValueError):
                continue
            rows.append((e, el, nu, tot))
    if len(rows) < 2:
        sys.exit(f"reference table too small: {path}")
    rows.sort(key=lambda t: t[0])
    return rows


def interp_loglog(table: list[tuple[float, float, float, float]], x: float) -> float:
    """Linear interpolation in log-log of the total stopping power; clamp edges."""
    if x <= table[0][0]:
        return table[0][3]
    if x >= table[-1][0]:
        return table[-1][3]
    # find bracketing
    for i in range(len(table) - 1):
        e0, _, _, y0 = table[i]
        e1, _, _, y1 = table[i + 1]
        if e0 <= x <= e1:
            if y0 <= 0 or y1 <= 0:
                # fall back to linear where a log would break (shouldn't happen here)
                return y0 + (y1 - y0) * (x - e0) / (e1 - e0)
            t = (math.log(x) - math.log(e0)) / (math.log(e1) - math.log(e0))
            return math.exp(math.log(y0) + t * (math.log(y1) - math.log(y0)))
    return table[-1][3]


def reference_for(particle: str, energy_mev: float, table) -> float:
    """PSTAR-equivalent total stopping for the species."""
    if particle.lower().startswith("p"):
        return interp_loglog(table, energy_mev)
    if particle.lower().startswith("d"):
        # velocity scaling: deuteron(E) ~ proton(E/2)
        return interp_loglog(table, energy_mev / 2.0)
    sys.exit(f"unsupported particle '{particle}' (use proton|deuteron)")


def _pick(d: dict, aliases):
    for a in aliases:
        if a in d and d[a] not in (None, ""):
            return float(d[a])
    return None


def read_sim(path: Path):
    """Yield (particle, energy_MeV, edep_raw_MeV, track_len_mm)."""
    warned_quenched = False
    with path.open() as f:
        rdr = csv.DictReader((ln for ln in f if not ln.lstrip().startswith("#")))
        for r in rdr:
            part = (r.get("particle") or "").strip()
            if not part:
                continue
            e = _pick(r, ["ke_MeV", "kinetic_energy_MeV", "energy_MeV"])
            edep = _pick(r, ["edep_scint_raw_MeV", "edep_raw_MeV"])
            if edep is None:
                edep = _pick(r, ["edep_scint_MeV", "edep_MeV"])
                if edep is not None and not warned_quenched:
                    print("WARNING: edep_scint_raw_MeV absent -- using the QUENCHED "
                          "edep_scint_MeV; ratios vs raw PSTAR will look low.", file=sys.stderr)
                    warned_quenched = True
            tlen_mm = _pick(r, ["track_len_scint_mm", "track_length_scint_mm"])
            if tlen_mm is None:
                tlen_cm = _pick(r, ["track_length_scint_cm", "track_len_scint_cm"])
                tlen_mm = None if tlen_cm is None else tlen_cm * 10.0
            if e is None or edep is None or tlen_mm is None:
                continue
            if tlen_mm <= 0:
                continue
            yield part, e, edep, tlen_mm


def aggregate(sim_rows, rho: float):
    """Group by (particle, round(energy,1)); return list of dicts."""
    acc: dict[tuple[str, float], list[float]] = {}
    ncnt: dict[tuple[str, float], int] = {}
    emean: dict[tuple[str, float], list[float]] = {}
    for part, e, edep, tlen_mm in sim_rows:
        key = (part, round(e, 1))
        a = acc.setdefault(key, [0.0, 0.0])
        a[0] += edep
        a[1] += tlen_mm
        ncnt[key] = ncnt.get(key, 0) + 1
        emean.setdefault(key, []).append(e)
    out = []
    for (part, eb), (edep_sum, tlen_sum) in acc.items():
        if tlen_sum <= 0:
            continue
        dedx_mev_per_mm = edep_sum / tlen_sum
        mass = dedx_mev_per_mm * 10.0 / rho  # MeV cm^2/g
        out.append({
            "particle": part,
            "energy_MeV": statistics.mean(emean[(part, eb)]),
            "n_events": ncnt[(part, eb)],
            "sim_total_MeV_cm2_g": mass,
        })
    out.sort(key=lambda d: (d["particle"], d["energy_MeV"]))
    return out


def run_compare(sim_path: Path, ref_path: Path, rho: float, out_path: Path | None,
                tol_pct: float) -> tuple[list[dict], bool]:
    table = read_reference(ref_path)
    rows = list(read_sim(sim_path))
    if not rows:
        sys.exit(f"no usable sim events read from {sim_path}")
    agg = aggregate(rows, rho)
    results = []
    all_pass = True
    for d in agg:
        ref = reference_for(d["particle"], d["energy_MeV"], table)
        ratio = d["sim_total_MeV_cm2_g"] / ref if ref > 0 else float("nan")
        delta = (ratio - 1.0) * 100.0
        ok = abs(delta) <= tol_pct
        all_pass = all_pass and ok
        d.update({
            "ref_total_MeV_cm2_g": ref,
            "ratio": ratio,
            "delta_percent": delta,
            "within_tolerance": ok,
        })
        results.append(d)

    if out_path is not None:
        cols = ["particle", "energy_MeV", "n_events", "sim_total_MeV_cm2_g",
                "ref_total_MeV_cm2_g", "ratio", "delta_percent", "within_tolerance"]
        with out_path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for d in results:
                w.writerow({k: (f"{d[k]:.6g}" if isinstance(d[k], float) else d[k]) for k in cols})
        print(f"wrote {out_path}")

    print(f"\nDeposited-energy proxy vs PSTAR (material=polystyrene, "
          f"rho={rho} g/cm^3, tolerance=+/-{tol_pct:g}%):")
    print(f"{'particle':<9}{'E[MeV]':>9}{'n':>7}{'sim':>12}{'ref':>12}"
          f"{'ratio':>9}{'delta%':>9}  ok")
    for d in results:
        print(f"{d['particle']:<9}{d['energy_MeV']:>9.2f}{d['n_events']:>7d}"
              f"{d['sim_total_MeV_cm2_g']:>12.4f}{d['ref_total_MeV_cm2_g']:>12.4f}"
              f"{d['ratio']:>9.4f}{d['delta_percent']:>9.2f}  "
              f"{'PASS' if d['within_tolerance'] else 'FAIL'}")
    by_spec = {}
    for d in results:
        by_spec.setdefault(d["particle"], []).append(d["ratio"])
    for sp, rs in by_spec.items():
        print(f"  mean ratio [{sp}] = {statistics.mean(rs):.4f} over {len(rs)} energy point(s)")
    print("NUMERICAL TOLERANCE:", "PASS" if all_pass and results else "FAIL")
    print("SCIENTIFIC STATUS: DIAGNOSTIC_ONLY")
    return results, all_pass and bool(results)


def self_test(ref_path: Path | None = None) -> int:
    """Build synthetic events against the selected committed reference table."""
    ref = DEFAULT_REF if ref_path is None else ref_path
    if not ref.is_file():
        print(f"SELF-TEST: FAIL (reference table not found: {ref})", file=sys.stderr)
        return 1

    table = read_reference(ref)
    ref_hash = sha256_file(ref)
    print(f"reference={ref.resolve()} sha256={ref_hash} rows={len(table)}")
    rho = DEFAULT_RHO
    cases = [("proton", 60.0), ("proton", 100.0), ("proton", 150.0),
             ("deuteron", 100.0), ("deuteron", 200.0)]

    with tempfile.TemporaryDirectory() as td:
        sim = Path(td) / "synthetic_events.csv"
        with sim.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["particle", "ke_MeV", "edep_scint_raw_MeV",
                        "track_len_scint_mm"])
            for part, e in cases:
                ref_val = reference_for(part, e, table)
                # Gives dE/dx = ref_val*rho/10 MeV/mm -> mass = ref_val.
                edep = ref_val * rho / 10.0
                for _ in range(40):
                    w.writerow([part, e, f"{edep:.6f}", "1.0"])
        print("=== self-test on synthetic events (expected ratio ~ 1.0) ===")
        results, ok = run_compare(sim, ref, rho, None, tol_pct=2.0)

    maxerr = max(abs(d["ratio"] - 1.0) for d in results)
    print(f"\nmax |ratio-1| = {maxerr:.2e}")
    if maxerr < 1e-6 and ok:
        print("SELF-TEST SCOPE: arithmetic and committed-reference path only")
        print("SELF-TEST: PASS")
        return 0
    print("SELF-TEST: FAIL")
    return 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sim", type=Path, help="sim event CSV (per-event dE/dx columns)")
    p.add_argument("--reference", type=Path, default=DEFAULT_REF,
                   help=f"PSTAR reference CSV (default {DEFAULT_REF})")
    p.add_argument("--material-density", type=float, default=DEFAULT_RHO,
                   help=f"scintillator density [g/cm^3] (default {DEFAULT_RHO})")
    p.add_argument("--out", type=Path, default=None, help="output report CSV")
    p.add_argument("--tolerance-pct", type=float, default=DEFAULT_TOL,
                   help=f"pass/fail tolerance on delta%% (default {DEFAULT_TOL})")
    p.add_argument("--self-test", action="store_true",
                   help="run a synthetic check against the selected reference table")
    args = p.parse_args(argv)

    if args.self_test:
        return self_test(args.reference)
    if not args.sim:
        p.error("--sim is required (or use --self-test)")
    _, ok = run_compare(args.sim, args.reference, args.material_density,
                        args.out, args.tolerance_pct)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
