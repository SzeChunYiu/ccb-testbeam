#!/usr/bin/env python3
"""Compare simulated proton/deuteron deposited-energy dE/dx with NIST PSTAR.

The calculation is a diagnostic proxy, not an accepted stopping-power closure.
Simulation CSV ingestion is delegated to the repository's fail-closed canonical
validator so malformed or ambiguous event rows cannot be silently omitted.
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

DEFAULT_RHO = float(os.environ.get("CCB_POLYSTYRENE_RHO", "1.060"))
DEFAULT_TOL = float(os.environ.get("CCB_STOPPING_TOLERANCE_PCT", "10.0"))
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.audit.validate_stopping_power_sim_table import (  # noqa: E402
    QUENCHED_BASIS,
    RAW_BASIS,
    SimulationTableError,
    TOOL_VERSION as SIM_TABLE_VALIDATOR_VERSION,
    read_validated_simulation_table,
)

DEFAULT_REF = REPO_ROOT / "data" / "reference" / "stopping_power" / "pstar_polystyrene.csv"
REFERENCE_COLUMNS = (
    "energy_MeV",
    "electronic_MeV_cm2_g",
    "nuclear_MeV_cm2_g",
    "total_MeV_cm2_g",
)


class StoppingPowerInputError(ValueError):
    """Raised when a comparison would use invalid or unsupported inputs."""


def sha256_file(path: Path) -> str:
    """Return a lowercase SHA-256 digest for provenance."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_reference(path: Path) -> list[tuple[float, float, float, float]]:
    """Return a strictly validated PSTAR table in declared energy order."""
    try:
        with path.open() as handle:
            data_lines = [
                (line_no, line)
                for line_no, line in enumerate(handle, start=1)
                if line.strip() and not line.lstrip().startswith("#")
            ]
    except OSError as exc:
        raise StoppingPowerInputError(
            f"cannot read reference table {path}: {exc}"
        ) from exc
    if not data_lines:
        raise StoppingPowerInputError(f"reference table has no CSV header: {path}")

    header_line, header_text = data_lines[0]
    try:
        header = next(csv.reader([header_text]))
    except csv.Error as exc:
        raise StoppingPowerInputError(
            f"reference table {path} line {header_line} has an invalid CSV header"
        ) from exc
    missing = [column for column in REFERENCE_COLUMNS if column not in header]
    if missing:
        raise StoppingPowerInputError(
            f"reference table {path} line {header_line} is missing required "
            f"column(s): {', '.join(missing)}"
        )

    rows: list[tuple[float, float, float, float]] = []
    previous_energy: float | None = None
    reader = csv.DictReader([line for _, line in data_lines])
    for (line_no, _), row in zip(data_lines[1:], reader, strict=True):
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
        energy, electronic, nuclear, total = values
        if not all(math.isfinite(value) for value in values):
            raise StoppingPowerInputError(
                f"reference table {path} line {line_no} contains a nonfinite value"
            )
        if energy <= 0 or electronic < 0 or nuclear < 0 or total <= 0:
            raise StoppingPowerInputError(
                f"reference table {path} line {line_no} has nonphysical values "
                f"energy={energy!r}, electronic={electronic!r}, "
                f"nuclear={nuclear!r}, total={total!r}"
            )
        if previous_energy is not None and energy <= previous_energy:
            raise StoppingPowerInputError(
                f"reference table {path} line {line_no} energy {energy:g} MeV is not "
                f"strictly greater than previous energy {previous_energy:g} MeV"
            )
        rows.append((energy, electronic, nuclear, total))
        previous_energy = energy
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
    """Interpolate total stopping power in log-log space without extrapolation."""
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
    for index in range(len(table) - 1):
        e0, _, _, y0 = table[index]
        e1, _, _, y1 = table[index + 1]
        if e0 <= x <= e1:
            fraction = (math.log(x) - math.log(e0)) / (math.log(e1) - math.log(e0))
            return math.exp(math.log(y0) + fraction * (math.log(y1) - math.log(y0)))
    raise StoppingPowerInputError(
        f"failed to bracket reference lookup energy {x:g} MeV"
    )


def reference_for(particle: str, energy_mev: float, table) -> float:
    """Return the PSTAR-equivalent total stopping power for one species."""
    lookup_energy = reference_lookup_energy(particle, energy_mev)
    try:
        return interp_loglog(table, lookup_energy)
    except StoppingPowerInputError as exc:
        raise StoppingPowerInputError(
            f"{particle} energy {energy_mev:g} MeV maps to proton-equivalent "
            f"energy {lookup_energy:g} MeV: {exc}"
        ) from exc


def _read_sim_with_summary(
    path: Path,
    allow_quenched_proxy: bool = False,
) -> tuple[list[tuple[str, float, float, float]], dict[str, object]]:
    try:
        return read_validated_simulation_table(
            path,
            allow_quenched_proxy=allow_quenched_proxy,
        )
    except SimulationTableError as exc:
        raise StoppingPowerInputError(str(exc)) from exc


def read_sim(
    path: Path,
    allow_quenched_proxy: bool = False,
) -> tuple[list[tuple[str, float, float, float]], str]:
    """Return canonical normalized rows using the shared fail-closed validator."""
    rows, summary = _read_sim_with_summary(path, allow_quenched_proxy)
    return rows, str(summary["energy_deposit_basis"])


def aggregate(
    sim_rows: list[tuple[str, float, float, float]],
    rho: float,
    energy_deposit_basis: str = RAW_BASIS,
) -> list[dict[str, object]]:
    """Group rows by canonical particle and rounded energy."""
    if not math.isfinite(rho) or rho <= 0:
        raise StoppingPowerInputError(
            f"material density must be finite and positive, got {rho!r} g/cm^3"
        )
    accumulator: dict[tuple[str, float], list[float]] = {}
    event_counts: dict[tuple[str, float], int] = {}
    energies: dict[tuple[str, float], list[float]] = {}
    for particle, energy, deposit, track_mm in sim_rows:
        key = (particle, round(energy, 1))
        totals = accumulator.setdefault(key, [0.0, 0.0])
        totals[0] += deposit
        totals[1] += track_mm
        event_counts[key] = event_counts.get(key, 0) + 1
        energies.setdefault(key, []).append(energy)

    output: list[dict[str, object]] = []
    for (particle, energy_bin), (deposit_sum, track_sum) in accumulator.items():
        if track_sum <= 0:
            raise StoppingPowerInputError(
                f"nonpositive aggregated track length for {particle} at {energy_bin:g} MeV"
            )
        mass_stopping = (deposit_sum / track_sum) * 10.0 / rho
        output.append(
            {
                "particle": particle,
                "energy_MeV": statistics.mean(energies[(particle, energy_bin)]),
                "n_events": event_counts[(particle, energy_bin)],
                "energy_deposit_basis": energy_deposit_basis,
                "raw_pstar_comparable": energy_deposit_basis == RAW_BASIS,
                "sim_total_MeV_cm2_g": mass_stopping,
            }
        )
    output.sort(key=lambda row: (str(row["particle"]), float(row["energy_MeV"])))
    return output


def run_compare(
    sim_path: Path,
    ref_path: Path,
    rho: float,
    out_path: Path | None,
    tol_pct: float,
    allow_quenched_proxy: bool = False,
) -> tuple[list[dict[str, object]], bool]:
    """Run a validated diagnostic comparison and optionally write a CSV report."""
    if not math.isfinite(tol_pct) or tol_pct < 0:
        raise StoppingPowerInputError(
            f"tolerance must be finite and nonnegative, got {tol_pct!r}%"
        )
    table = read_reference(ref_path)
    rows, sim_summary = _read_sim_with_summary(sim_path, allow_quenched_proxy)
    basis = str(sim_summary["energy_deposit_basis"])
    aggregated = aggregate(rows, rho, energy_deposit_basis=basis)
    results: list[dict[str, object]] = []
    all_pass = True
    ref_min = table[0][0]
    ref_max = table[-1][0]
    for result in aggregated:
        energy = float(result["energy_MeV"])
        particle = str(result["particle"])
        lookup_energy = reference_lookup_energy(particle, energy)
        reference = reference_for(particle, energy, table)
        ratio = float(result["sim_total_MeV_cm2_g"]) / reference
        delta = (ratio - 1.0) * 100.0
        numeric_ok = abs(delta) <= tol_pct
        comparable = bool(result["raw_pstar_comparable"])
        accepted_ok = numeric_ok and comparable
        all_pass = all_pass and accepted_ok
        result.update(
            {
                "simulation_input_sha256": sim_summary["input_sha256"],
                "simulation_input_bytes": sim_summary["input_bytes"],
                "simulation_rows_validated": sim_summary["rows_validated"],
                "simulation_validator_version": sim_summary["tool_version"],
                "reference_lookup_energy_MeV": lookup_energy,
                "reference_range_min_MeV": ref_min,
                "reference_range_max_MeV": ref_max,
                "reference_in_range": True,
                "ref_total_MeV_cm2_g": reference,
                "ratio": ratio,
                "delta_percent": delta,
                "numeric_within_tolerance": numeric_ok,
                "within_tolerance": accepted_ok,
            }
        )
        results.append(result)

    if out_path is not None:
        columns = [
            "particle",
            "energy_MeV",
            "reference_lookup_energy_MeV",
            "reference_range_min_MeV",
            "reference_range_max_MeV",
            "reference_in_range",
            "n_events",
            "energy_deposit_basis",
            "raw_pstar_comparable",
            "simulation_input_sha256",
            "simulation_input_bytes",
            "simulation_rows_validated",
            "simulation_validator_version",
            "sim_total_MeV_cm2_g",
            "ref_total_MeV_cm2_g",
            "ratio",
            "delta_percent",
            "numeric_within_tolerance",
            "within_tolerance",
        ]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            for result in results:
                writer.writerow(
                    {
                        key: (
                            f"{result[key]:.6g}"
                            if isinstance(result[key], float)
                            else result[key]
                        )
                        for key in columns
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
        status = (
            "NONCOMPARABLE"
            if not result["raw_pstar_comparable"]
            else ("PASS" if result["within_tolerance"] else "FAIL")
        )
        print(
            f"{result['particle']:<9}{result['energy_MeV']:>9.2f}"
            f"{result['n_events']:>7d}{result['sim_total_MeV_cm2_g']:>12.4f}"
            f"{result['ref_total_MeV_cm2_g']:>12.4f}{result['ratio']:>9.4f}"
            f"{result['delta_percent']:>9.2f}  {status}"
        )
    grouped: dict[str, list[float]] = {}
    for result in results:
        grouped.setdefault(str(result["particle"]), []).append(float(result["ratio"]))
    for species, ratios in grouped.items():
        print(
            f"  mean ratio [{species}] = {statistics.mean(ratios):.4f} "
            f"over {len(ratios)} energy point(s)"
        )
    print(
        f"SIM INPUT VALIDATION: rows={sim_summary['rows_validated']} "
        f"sha256={sim_summary['input_sha256']} validator={SIM_TABLE_VALIDATOR_VERSION}"
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
    reference_path = DEFAULT_REF if ref_path is None else ref_path
    if not reference_path.is_file():
        print(
            f"SELF-TEST: FAIL (reference table not found: {reference_path})",
            file=sys.stderr,
        )
        return 1
    table = read_reference(reference_path)
    print(
        f"reference={reference_path.resolve()} sha256={sha256_file(reference_path)} "
        f"rows={len(table)}"
    )
    cases = [
        ("proton", 60.0),
        ("proton", 100.0),
        ("proton", 150.0),
        ("deuteron", 100.0),
        ("deuteron", 200.0),
    ]
    with tempfile.TemporaryDirectory() as directory:
        simulation_path = Path(directory) / "synthetic_events.csv"
        with simulation_path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                ["particle", "ke_MeV", "edep_scint_raw_MeV", "track_len_scint_mm"]
            )
            for particle, energy in cases:
                reference = reference_for(particle, energy, table)
                deposit = reference * DEFAULT_RHO / 10.0
                for _ in range(40):
                    writer.writerow([particle, energy, f"{deposit:.9f}", "1.0"])
        print("=== self-test on synthetic events (expected ratio ~ 1.0) ===")
        results, ok = run_compare(
            simulation_path,
            reference_path,
            DEFAULT_RHO,
            None,
            tol_pct=2.0,
        )
    max_error = max(abs(float(result["ratio"]) - 1.0) for result in results)
    print(f"\nmax |ratio-1| = {max_error:.2e}")
    if max_error < 1e-6 and ok:
        print("SELF-TEST SCOPE: arithmetic and committed-reference path only")
        print("SELF-TEST: PASS")
        return 0
    print("SELF-TEST: FAIL")
    return 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sim", type=Path, help="sim event CSV")
    parser.add_argument("--reference", type=Path, default=DEFAULT_REF)
    parser.add_argument("--material-density", type=float, default=DEFAULT_RHO)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--tolerance-pct", type=float, default=DEFAULT_TOL)
    parser.add_argument(
        "--allow-quenched-proxy",
        action="store_true",
        help="permit labelled, non-accepting quenched diagnostic output",
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.self_test:
            return self_test(args.reference)
        if not args.sim:
            raise StoppingPowerInputError("--sim is required (or use --self-test)")
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
