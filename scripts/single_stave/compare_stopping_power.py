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
    Reference lookup energies outside the committed PSTAR range are rejected;
    the tool never clamps to an endpoint or extrapolates silently. Reference
    rows must be complete, finite, physical, and strictly increasing in energy.
* Report: per-energy ratio S_sim/S_ref, delta %, and a numerical tolerance
  check (CCB_STOPPING_TOLERANCE_PCT, default 10%). This is DIAGNOSTIC_ONLY,
  not an accepted stopping-power closure.

Input (sim event CSV, comment lines starting with '#'): one row per event with
the sim's per-event columns. Flexible aliases are accepted:
    particle : particle
    energy   : ke_MeV | kinetic_energy_MeV | energy_MeV
    edep_raw : edep_scint_raw_MeV | edep_raw_MeV
    track_len: track_len_scint_mm | track_length_scint_mm | track_length_scint_cm
                (a '_cm' column is auto-converted to mm)

Quenched energy-deposit fields (edep_scint_MeV | edep_MeV) are rejected by
default because visible light yield is not raw energy loss and is not directly
comparable with PSTAR. ``--allow-quenched-proxy`` permits diagnostic output only:
results are labelled QUENCHED_PROXY, are never accepted as within tolerance, and
the process exits nonzero.

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
REFERENCE_COLUMNS = (
    "energy_MeV",
    "electronic_MeV_cm2_g",
    "nuclear_MeV_cm2_g",
    "total_MeV_cm2_g",
)
RAW_EDEP_ALIASES = ("edep_scint_raw_MeV", "edep_raw_MeV")
QUENCHED_EDEP_ALIASES = ("edep_scint_MeV", "edep_MeV")
RAW_BASIS = "UNQUENCHED_RAW"
QUENCHED_BASIS = "QUENCHED_PROXY"


class StoppingPowerInputError(ValueError):
    """Raised when a comparison would use undefined or out-of-range inputs."""


def sha256_file(path: Path) -> str:
    """Return a lowercase SHA-256 digest for provenance."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_reference(path: Path) -> list[tuple[float, float, float, float]]:
    """Return a strictly validated PSTAR table in declared energy order."""
    try:
        with path.open() as f:
            data_lines = [
                (line_no, line)
                for line_no, line in enumerate(f, start=1)
                if line.strip() and not line.lstrip().startswith("#")
            ]
    except OSError as exc:
        raise StoppingPowerInputError(
            f"cannot read reference table {path}: {exc}"
        ) from exc
    if not data_lines:
        raise StoppingPowerInputError(f"reference table has no CSV header: {path}")

    header_line, header_text = data_lines[0]
    header = next(csv.reader([header_text]))
    missing = [column for column in REFERENCE_COLUMNS if column not in header]
    if missing:
        raise StoppingPowerInputError(
            f"reference table {path} line {header_line} is missing required "
            f"column(s): {', '.join(missing)}"
        )

    rows = []
    previous_energy = None
    rdr = csv.DictReader([line for _, line in data_lines])
    for (line_no, _), row in zip(data_lines[1:], rdr, strict=True):
        if None in row:
            raise StoppingPowerInputError(
                f"reference table {path} line {line_no} has excess fields"
            )
        try:
            values = tuple(float(row[column]) for column in REFERENCE_COLUMNS)
        except (KeyError, TypeError, ValueError) as exc:
            raise StoppingPowerInputError(
                f"reference table {path} line {line_no} has a missing or "
                "nonnumeric required value"
            ) from exc
        e, el, nu, tot = values
        if not all(math.isfinite(value) for value in values):
            raise StoppingPowerInputError(
                f"reference table {path} line {line_no} contains a nonfinite value"
            )
        if e <= 0 or el < 0 or nu < 0 or tot <= 0:
            raise StoppingPowerInputError(
                f"reference table {path} line {line_no} has nonphysical values "
                f"energy={e!r}, electronic={el!r}, nuclear={nu!r}, total={tot!r}"
            )
        if previous_energy is not None and e <= previous_energy:
            raise StoppingPowerInputError(
                f"reference table {path} line {line_no} energy {e:g} MeV is not "
                f"strictly greater than previous energy {previous_energy:g} MeV"
            )
        rows.append((e, el, nu, tot))
        previous_energy = e
    if len(rows) < 2:
        raise StoppingPowerInputError(
            f"reference table must contain at least two validated rows: {path}"
        )
    return rows


def reference_lookup_energy(particle: str, energy_mev: float) -> float:
    """Return the proton-equivalent PSTAR lookup energy for a particle."""
    normalized = particle.strip().lower()
    if normalized.startswith("p"):
        return energy_mev
    if normalized.startswith("d"):
        return energy_mev / 2.0
    raise StoppingPowerInputError(
        f"unsupported particle '{particle}' (use proton|deuteron)"
    )


def interp_loglog(table: list[tuple[float, float, float, float]], x: float) -> float:
    """Linear interpolation in log-log of total stopping power, without extrapolation."""
    if not math.isfinite(x) or x <= 0:
        raise StoppingPowerInputError(
            f"reference lookup energy must be finite and positive, got {x!r} MeV"
        )
    e_min = table[0][0]
    e_max = table[-1][0]
    if x < e_min or x > e_max:
        raise StoppingPowerInputError(
            f"reference lookup energy {x:g} MeV is outside the committed PSTAR "
            f"range [{e_min:g}, {e_max:g}] MeV"
        )
    if x == e_min:
        return table[0][3]
    if x == e_max:
        return table[-1][3]
    for i in range(len(table) - 1):
        e0, _, _, y0 = table[i]
        e1, _, _, y1 = table[i + 1]
        if e0 <= x <= e1:
            if y0 <= 0 or y1 <= 0:
                return y0 + (y1 - y0) * (x - e0) / (e1 - e0)
            t = (math.log(x) - math.log(e0)) / (math.log(e1) - math.log(e0))
            return math.exp(math.log(y0) + t * (math.log(y1) - math.log(y0)))
    raise StoppingPowerInputError(
        f"failed to bracket reference lookup energy {x:g} MeV"
    )


def reference_for(particle: str, energy_mev: float, table) -> float:
    """PSTAR-equivalent total stopping for the species."""
    lookup_energy = reference_lookup_energy(particle, energy_mev)
    try:
        return interp_loglog(table, lookup_energy)
    except StoppingPowerInputError as exc:
        raise StoppingPowerInputError(
            f"{particle} energy {energy_mev:g} MeV maps to proton-equivalent "
            f"energy {lookup_energy:g} MeV: {exc}"
        ) from exc


def _pick(d: dict, aliases):
    for alias in aliases:
        if alias in d and d[alias] not in (None, ""):
            return float(d[alias])
    return None


def read_sim(
    path: Path,
    allow_quenched_proxy: bool = False,
) -> tuple[list[tuple[str, float, float, float]], str]:
    """Return validated usable sim rows and one consistent energy-deposit basis."""
    try:
        with path.open() as f:
            data_lines = [
                (line_no, line)
                for line_no, line in enumerate(f, start=1)
                if line.strip() and not line.lstrip().startswith("#")
            ]
    except OSError as exc:
        raise StoppingPowerInputError(f"cannot read simulation table {path}: {exc}") from exc
    if not data_lines:
        raise StoppingPowerInputError(f"simulation table has no CSV header: {path}")

    rows: list[tuple[str, float, float, float]] = []
    used_bases: set[str] = set()
    rdr = csv.DictReader([line for _, line in data_lines])
    for (line_no, _), row in zip(data_lines[1:], rdr, strict=True):
        part = (row.get("particle") or "").strip()
        if not part:
            continue
        try:
            energy = _pick(row, ("ke_MeV", "kinetic_energy_MeV", "energy_MeV"))
            raw_edep = _pick(row, RAW_EDEP_ALIASES)
            quenched_edep = _pick(row, QUENCHED_EDEP_ALIASES)
            tlen_mm = _pick(row, ("track_len_scint_mm", "track_length_scint_mm"))
            if tlen_mm is None:
                tlen_cm = _pick(row, ("track_length_scint_cm", "track_len_scint_cm"))
                tlen_mm = None if tlen_cm is None else tlen_cm * 10.0
        except (TypeError, ValueError) as exc:
            raise StoppingPowerInputError(
                f"simulation table {path} line {line_no} has a nonnumeric required value"
            ) from exc

        if raw_edep is not None:
            edep = raw_edep
            basis = RAW_BASIS
        elif quenched_edep is not None:
            if not allow_quenched_proxy:
                raise StoppingPowerInputError(
                    f"simulation table {path} line {line_no} provides only quenched "
                    "energy deposit; raw PSTAR comparison requires edep_scint_raw_MeV "
                    "or edep_raw_MeV (use --allow-quenched-proxy for non-accepting "
                    "diagnostic output)"
                )
            edep = quenched_edep
            basis = QUENCHED_BASIS
        else:
            continue

        if energy is None or tlen_mm is None:
            continue
        if tlen_mm <= 0:
            continue
        rows.append((part, energy, edep, tlen_mm))
        used_bases.add(basis)

    if len(used_bases) > 1:
        raise StoppingPowerInputError(
            f"simulation table {path} mixes unquenched and quenched energy-deposit "
            "semantics; aggregate comparison is undefined"
        )
    basis = next(iter(used_bases), "UNKNOWN")
    return rows, basis


def aggregate(sim_rows, rho: float, energy_deposit_basis: str = RAW_BASIS):
    """Group by (particle, round(energy,1)); return list of dicts."""
    acc: dict[tuple[str, float], list[float]] = {}
    ncnt: dict[tuple[str, float], int] = {}
    emean: dict[tuple[str, float], list[float]] = {}
    for part, energy, edep, tlen_mm in sim_rows:
        key = (part, round(energy, 1))
        values = acc.setdefault(key, [0.0, 0.0])
        values[0] += edep
        values[1] += tlen_mm
        ncnt[key] = ncnt.get(key, 0) + 1
        emean.setdefault(key, []).append(energy)
    out = []
    for (part, energy_bin), (edep_sum, tlen_sum) in acc.items():
        if tlen_sum <= 0:
            continue
        dedx_mev_per_mm = edep_sum / tlen_sum
        mass = dedx_mev_per_mm * 10.0 / rho  # MeV cm^2/g
        out.append(
            {
                "particle": part,
                "energy_MeV": statistics.mean(emean[(part, energy_bin)]),
                "n_events": ncnt[(part, energy_bin)],
                "energy_deposit_basis": energy_deposit_basis,
                "raw_pstar_comparable": energy_deposit_basis == RAW_BASIS,
                "sim_total_MeV_cm2_g": mass,
            }
        )
    out.sort(key=lambda d: (d["particle"], d["energy_MeV"]))
    return out


def run_compare(
    sim_path: Path,
    ref_path: Path,
    rho: float,
    out_path: Path | None,
    tol_pct: float,
    allow_quenched_proxy: bool = False,
) -> tuple[list[dict], bool]:
    table = read_reference(ref_path)
    rows, basis = read_sim(sim_path, allow_quenched_proxy=allow_quenched_proxy)
    if not rows:
        raise StoppingPowerInputError(f"no usable sim events read from {sim_path}")
    agg = aggregate(rows, rho, energy_deposit_basis=basis)
    results = []
    all_pass = True
    ref_min = table[0][0]
    ref_max = table[-1][0]
    for result in agg:
        lookup_energy = reference_lookup_energy(
            result["particle"], result["energy_MeV"]
        )
        ref = reference_for(result["particle"], result["energy_MeV"], table)
        ratio = result["sim_total_MeV_cm2_g"] / ref if ref > 0 else float("nan")
        delta = (ratio - 1.0) * 100.0
        numeric_ok = abs(delta) <= tol_pct
        comparable = result["raw_pstar_comparable"]
        accepted_ok = numeric_ok and comparable
        all_pass = all_pass and accepted_ok
        result.update(
            {
                "reference_lookup_energy_MeV": lookup_energy,
                "reference_range_min_MeV": ref_min,
                "reference_range_max_MeV": ref_max,
                "reference_in_range": True,
                "ref_total_MeV_cm2_g": ref,
                "ratio": ratio,
                "delta_percent": delta,
                "numeric_within_tolerance": numeric_ok,
                "within_tolerance": accepted_ok,
            }
        )
        results.append(result)

    if out_path is not None:
        cols = [
            "particle",
            "energy_MeV",
            "reference_lookup_energy_MeV",
            "reference_range_min_MeV",
            "reference_range_max_MeV",
            "reference_in_range",
            "n_events",
            "energy_deposit_basis",
            "raw_pstar_comparable",
            "sim_total_MeV_cm2_g",
            "ref_total_MeV_cm2_g",
            "ratio",
            "delta_percent",
            "numeric_within_tolerance",
            "within_tolerance",
        ]
        with out_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            for result in results:
                writer.writerow(
                    {
                        key: (
                            f"{result[key]:.6g}"
                            if isinstance(result[key], float)
                            else result[key]
                        )
                        for key in cols
                    }
                )
        print(f"wrote {out_path}")

    print(
        "\nDeposited-energy proxy vs PSTAR (material=polystyrene, "
        f"rho={rho} g/cm^3, tolerance=+/-{tol_pct:g}%):"
    )
    print(
        f"{'particle':<9}{'E[MeV]':>9}{'n':>7}{'sim':>12}{'ref':>12}"
        f"{'ratio':>9}{'delta%':>9}  status"
    )
    for result in results:
        if not result["raw_pstar_comparable"]:
            status = "NONCOMPARABLE"
        else:
            status = "PASS" if result["within_tolerance"] else "FAIL"
        print(
            f"{result['particle']:<9}{result['energy_MeV']:>9.2f}"
            f"{result['n_events']:>7d}{result['sim_total_MeV_cm2_g']:>12.4f}"
            f"{result['ref_total_MeV_cm2_g']:>12.4f}{result['ratio']:>9.4f}"
            f"{result['delta_percent']:>9.2f}  {status}"
        )
    by_spec = {}
    for result in results:
        by_spec.setdefault(result["particle"], []).append(result["ratio"])
    for species, ratios in by_spec.items():
        print(
            f"  mean ratio [{species}] = {statistics.mean(ratios):.4f} "
            f"over {len(ratios)} energy point(s)"
        )
    if basis == QUENCHED_BASIS:
        print("ENERGY DEPOSIT BASIS: QUENCHED_PROXY")
        print("NUMERICAL TOLERANCE: NOT_ACCEPTED_QUENCHED_PROXY")
    else:
        print("ENERGY DEPOSIT BASIS: UNQUENCHED_RAW")
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
    cases = [
        ("proton", 60.0),
        ("proton", 100.0),
        ("proton", 150.0),
        ("deuteron", 100.0),
        ("deuteron", 200.0),
    ]

    with tempfile.TemporaryDirectory() as td:
        sim = Path(td) / "synthetic_events.csv"
        with sim.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "particle",
                    "ke_MeV",
                    "edep_scint_raw_MeV",
                    "track_len_scint_mm",
                ]
            )
            for part, energy in cases:
                ref_val = reference_for(part, energy, table)
                # Gives dE/dx = ref_val*rho/10 MeV/mm -> mass = ref_val.
                edep = ref_val * rho / 10.0
                for _ in range(40):
                    writer.writerow([part, energy, f"{edep:.6f}", "1.0"])
        print("=== self-test on synthetic events (expected ratio ~ 1.0) ===")
        results, ok = run_compare(sim, ref, rho, None, tol_pct=2.0)

    maxerr = max(abs(result["ratio"] - 1.0) for result in results)
    print(f"\nmax |ratio-1| = {maxerr:.2e}")
    if maxerr < 1e-6 and ok:
        print("SELF-TEST SCOPE: arithmetic and committed-reference path only")
        print("SELF-TEST: PASS")
        return 0
    print("SELF-TEST: FAIL")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--sim", type=Path, help="sim event CSV (per-event dE/dx columns)")
    parser.add_argument(
        "--reference",
        type=Path,
        default=DEFAULT_REF,
        help=f"PSTAR reference CSV (default {DEFAULT_REF})",
    )
    parser.add_argument(
        "--material-density",
        type=float,
        default=DEFAULT_RHO,
        help=f"scintillator density [g/cm^3] (default {DEFAULT_RHO})",
    )
    parser.add_argument("--out", type=Path, default=None, help="output report CSV")
    parser.add_argument(
        "--tolerance-pct",
        type=float,
        default=DEFAULT_TOL,
        help=f"pass/fail tolerance on delta%% (default {DEFAULT_TOL})",
    )
    parser.add_argument(
        "--allow-quenched-proxy",
        action="store_true",
        help=(
            "permit quenched visible-energy input for labelled, non-accepting "
            "diagnostic output; the command still exits nonzero"
        ),
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run a synthetic check against the selected reference table",
    )
    args = parser.parse_args(argv)

    try:
        if args.self_test:
            return self_test(args.reference)
        if not args.sim:
            parser.error("--sim is required (or use --self-test)")
        _, ok = run_compare(
            args.sim,
            args.reference,
            args.material_density,
            args.out,
            args.tolerance_pct,
            allow_quenched_proxy=args.allow_quenched_proxy,
        )
        return 0 if ok else 1
    except StoppingPowerInputError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
