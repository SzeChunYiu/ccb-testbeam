#!/usr/bin/env python3
"""Compare simulated proton/deuteron deposited-energy dE/dx with NIST PSTAR.

The calculation is a diagnostic proxy, not an accepted stopping-power closure.

track_len_scint_mm / edep_scint_raw_MeV on current Geant4 outputs are event totals
over non-optical tracks (#1007), so PSTAR primary comparisons remain
physics_comparable=False until primary-only estimators exist.
Simulation and PSTAR CSV ingestion both use repository fail-closed validators.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import math
import os
import sys
import tempfile
from pathlib import Path

DEFAULT_RHO = float(os.environ.get("CCB_POLYSTYRENE_RHO", "1.060"))
DEFAULT_TOL = float(os.environ.get("CCB_STOPPING_TOLERANCE_PCT", "10.0"))
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.audit.validate_pstar_component_sum import (  # noqa: E402
    PstarComponentError,
    TOOL_VERSION as PSTAR_VALIDATOR_VERSION,
    read_validated_pstar_table,
)
from tools.audit.validate_stopping_power_sim_table import (  # noqa: E402
    QUENCHED_BASIS,
    RAW_BASIS,
    SimulationTableError,
    TOOL_VERSION as SIM_TABLE_VALIDATOR_VERSION,
    read_validated_simulation_table,
)
from scripts.lane07.stopping_power_track_scope import (  # noqa: E402
    resolve_table_track_scope,
)

DEFAULT_REF = REPO_ROOT / "data" / "reference" / "stopping_power" / "pstar_polystyrene.csv"
PstarRow = tuple[float, float, float, float]
ENERGY_GROUPING = "EXACT_CONFIGURED_ENERGY"
MASS_STOPPING_ESTIMATOR = "RATIO_OF_SUMS_TRACK_LENGTH_WEIGHTED"
PRIMARY_VS_EVENT_TOTAL_STATUS = "EVENT_TOTAL_NOT_PRIMARY_STOPPING_POWER"
AUDIT_ISSUE_1007 = 1007
SUMMATION_METHOD = "MATH_FSUM_PER_GROUP"
DIRECT_PROTON_REFERENCE = "DIRECT_PSTAR_PROTON"
DEUTERON_REFERENCE_PROXY = "VELOCITY_SCALED_PROTON_PROXY"
UNCERTAINTY_METHOD = "NOT_EVALUATED"
REPORT_FLOAT_SERIALIZATION = "PYTHON_REPR_ROUND_TRIP"
CROSS_ENERGY_COMBINATION_POLICY = (
    "NO_CROSS_ENERGY_COMBINATION_WITHOUT_UNCERTAINTY_MODEL"
)
REPORT_PUBLICATION_POLICY = "NO_INPUT_OUTPUT_ALIAS_AND_ATOMIC_REPORT_WRITE"
REPORT_COLUMNS = [
    "particle",
    "energy_MeV",
    "energy_grouping",
    "reference_basis",
    "reference_direct_pstar_comparable",
    "physics_comparable",
    "reference_lookup_energy_MeV",
    "reference_range_min_MeV",
    "reference_range_max_MeV",
    "reference_in_range",
    "n_events",
    "energy_deposit_basis",
    "track_length_scope",
    "primary_track_identity",
    "pstar_primary_identity_ok",
    "raw_pstar_comparable",
    "track_scope",
    "primary_pstar_scope_comparable",
    "pstar_acceptance_gate",
    "deposit_sum_MeV",
    "track_length_sum_mm",
    "material_density_g_cm3",
    "mass_stopping_estimator",
    "summation_method",
    "simulation_input_sha256",
    "simulation_input_bytes",
    "simulation_rows_validated",
    "simulation_validator_version",
    "reference_input_sha256",
    "reference_input_bytes",
    "reference_rows_validated",
    "reference_validator_version",
    "reference_component_identity",
    "reference_component_consistent",
    "sim_total_MeV_cm2_g",
    "ref_total_MeV_cm2_g",
    "ratio",
    "delta_percent",
    "tolerance_percent",
    "numeric_within_tolerance",
    "uncertainty_method",
    "uncertainty_evaluated",
    "cross_energy_combination_policy",
    "report_publication_policy",
    "acceptance_status",
    "within_tolerance",
    "report_float_serialization",
]


class StoppingPowerInputError(ValueError):
    """Raised when a comparison would use invalid or unsupported inputs."""


def _serialize_report_value(value: object) -> object:
    """Serialize floats without losing their Python round-trip identity."""
    if isinstance(value, float):
        if not math.isfinite(value):
            raise StoppingPowerInputError(
                f"report output cannot serialize nonfinite float {value!r}"
            )
        return repr(value)
    return value


def _resolved_path(path: Path) -> Path:
    """Resolve a path without requiring the final component to exist."""
    return path.expanduser().resolve(strict=False)


def _paths_alias(left: Path, right: Path) -> bool:
    """Return whether resolved paths name the same file, including hard links."""
    if left == right:
        return True
    try:
        return left.exists() and right.exists() and os.path.samefile(left, right)
    except OSError:
        return False


def _validate_output_path(out_path: Path, sim_path: Path, ref_path: Path) -> Path:
    """Reject report paths that could overwrite either validated input."""
    resolved_output = _resolved_path(out_path)
    inputs = {
        "simulation input": _resolved_path(sim_path),
        "PSTAR reference input": _resolved_path(ref_path),
    }
    for label, resolved_input in inputs.items():
        if _paths_alias(resolved_output, resolved_input):
            raise StoppingPowerInputError(
                f"report output path {resolved_output} aliases {label} {resolved_input}"
            )
    return resolved_output


def _sha256_path(path: Path) -> str:
    """Return the SHA-256 digest of one completed file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_report_atomically(
    out_path: Path,
    columns: list[str],
    results: list[dict[str, object]],
) -> dict[str, object]:
    """Serialize completely, then atomically publish a same-directory report."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            prefix=f".{out_path.name}.",
            suffix=".tmp",
            dir=out_path.parent,
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            for result in results:
                writer.writerow(
                    {key: _serialize_report_value(result[key]) for key in columns}
                )
            handle.flush()
            os.fsync(handle.fileno())
        report_bytes = temp_path.stat().st_size
        report_sha256 = _sha256_path(temp_path)
        os.replace(temp_path, out_path)
        temp_path = None
    except Exception as exc:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise StoppingPowerInputError(
            f"failed to publish report atomically to {out_path}: {exc}"
        ) from exc
    return {
        "report_output_path": str(out_path),
        "report_output_bytes": report_bytes,
        "report_output_sha256": report_sha256,
        "report_atomic_publication": True,
        "report_input_alias_checked": True,
        "report_publication_policy": REPORT_PUBLICATION_POLICY,
    }


def _read_reference_with_summary(
    path: Path,
) -> tuple[list[PstarRow], dict[str, object]]:
    try:
        return read_validated_pstar_table(path)
    except PstarComponentError as exc:
        raise StoppingPowerInputError(str(exc)) from exc


def read_reference(path: Path) -> list[PstarRow]:
    """Return canonical rows after structural and component-sum validation."""
    rows, _ = _read_reference_with_summary(path)
    return rows


def reference_basis(particle: str) -> str:
    """Return the provenance basis used for the reference stopping power."""
    normalized = particle.strip().lower()
    if normalized.startswith("p"):
        return DIRECT_PROTON_REFERENCE
    if normalized.startswith("d"):
        return DEUTERON_REFERENCE_PROXY
    raise StoppingPowerInputError(
        f"unsupported particle '{particle}' (use proton|deuteron)"
    )


def reference_lookup_energy(particle: str, energy_mev: float) -> float:
    """Return the proton-equivalent PSTAR lookup energy for a particle."""
    basis = reference_basis(particle)
    if basis == DIRECT_PROTON_REFERENCE:
        return energy_mev
    return energy_mev / 2.0


def interp_loglog(table: list[PstarRow], x: float) -> float:
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
    raise StoppingPowerInputError(f"failed to bracket reference lookup energy {x:g} MeV")


def reference_for(particle: str, energy_mev: float, table: list[PstarRow]) -> float:
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
    """Group rows by particle/energy with compensated, order-stable sums."""
    if not math.isfinite(rho) or rho <= 0:
        raise StoppingPowerInputError(
            f"material density must be finite and positive, got {rho!r} g/cm^3"
        )
    accumulator: dict[tuple[str, float], tuple[list[float], list[float]]] = {}
    for particle, energy, deposit, track_mm in sim_rows:
        key = (particle, energy)
        deposits, tracks = accumulator.setdefault(key, ([], []))
        deposits.append(deposit)
        tracks.append(track_mm)

    output: list[dict[str, object]] = []
    for (particle, energy), (deposits, tracks) in accumulator.items():
        deposit_sum = math.fsum(deposits)
        track_sum = math.fsum(tracks)
        if track_sum <= 0:
            raise StoppingPowerInputError(
                f"nonpositive aggregated track length for {particle} at {energy:g} MeV"
            )
        mass_stopping = (deposit_sum / track_sum) * 10.0 / rho
        output.append(
            {
                "particle": particle,
                "energy_MeV": energy,
                "energy_grouping": ENERGY_GROUPING,
                "n_events": len(deposits),
                "energy_deposit_basis": energy_deposit_basis,
                "raw_pstar_comparable": energy_deposit_basis == RAW_BASIS,
                "deposit_sum_MeV": deposit_sum,
                "track_length_sum_mm": track_sum,
                "material_density_g_cm3": rho,
                "mass_stopping_estimator": MASS_STOPPING_ESTIMATOR,
                "summation_method": SUMMATION_METHOD,
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
    allow_deuteron_proxy: bool = False,
) -> tuple[list[dict[str, object]], bool]:
    """Run a validated diagnostic comparison and optionally write a CSV report."""
    if not math.isfinite(tol_pct) or tol_pct < 0:
        raise StoppingPowerInputError(
            f"tolerance must be finite and nonnegative, got {tol_pct!r}%"
        )
    resolved_output = (
        _validate_output_path(out_path, sim_path, ref_path)
        if out_path is not None
        else None
    )
    table, ref_summary = _read_reference_with_summary(ref_path)
    rows, sim_summary = _read_sim_with_summary(sim_path, allow_quenched_proxy)
    has_deuteron = any(particle == "deuteron" for particle, *_ in rows)
    if has_deuteron and not allow_deuteron_proxy:
        raise StoppingPowerInputError(
            "deuteron comparison maps E to proton PSTAR at E/2 using an "
            "unvalidated equal-velocity proxy; use --allow-deuteron-proxy only "
            "for labelled, non-accepting diagnostics"
        )
    basis = str(sim_summary["energy_deposit_basis"])
    # Main #1007 provenance from validator summary.
    track_scope = str(sim_summary.get("track_length_scope", "EVENT_TOTAL_ALL_NON_OPTICAL"))
    primary_ok = bool(sim_summary.get("pstar_primary_identity_ok", False))
    # Lane07 Wave C extras coexist with main keys.
    scope_meta = resolve_table_track_scope(sim_summary)
    aggregated = aggregate(rows, rho, energy_deposit_basis=basis)
    results: list[dict[str, object]] = []
    all_pass = True
    ref_min = table[0][0]
    ref_max = table[-1][0]
    for result in aggregated:
        energy = float(result["energy_MeV"])
        particle = str(result["particle"])
        ref_basis = reference_basis(particle)
        direct_reference = ref_basis == DIRECT_PROTON_REFERENCE
        lookup_energy = reference_lookup_energy(particle, energy)
        reference = reference_for(particle, energy, table)
        ratio = float(result["sim_total_MeV_cm2_g"]) / reference
        delta = (ratio - 1.0) * 100.0
        numeric_ok = abs(delta) <= tol_pct
        raw_comparable = bool(result["raw_pstar_comparable"])
        # Deposit/reference basis comparable (may still be wrong track-scope).
        physics_comparable = raw_comparable and direct_reference
        result["track_length_scope"] = track_scope
        result["primary_track_identity"] = bool(
            sim_summary.get("primary_track_identity", False)
        )
        result["pstar_primary_identity_ok"] = primary_ok
        # Lane07 Wave C track-scope extras (fail-closed annotations).
        # Prefer explicit CSV label when present; else normalized scope_meta.
        result["track_scope"] = sim_summary.get("track_scope") or scope_meta["track_scope"]
        result["primary_pstar_scope_comparable"] = bool(
            scope_meta["primary_pstar_scope_comparable"]
        )
        result["pstar_acceptance_gate"] = scope_meta["pstar_acceptance_gate"]
        uncertainty_evaluated = False
        # Authorizing acceptance also requires primary-track identity (#1007).
        accepted_ok = (
            numeric_ok
            and physics_comparable
            and primary_ok
            and uncertainty_evaluated
        )
        if not physics_comparable:
            acceptance_status = "NONCOMPARABLE_INPUT_OR_REFERENCE"
        elif not primary_ok:
            acceptance_status = "NONCOMPARABLE_EVENT_TOTAL_TRACK_SCOPE"
        elif not numeric_ok:
            acceptance_status = "POINT_ESTIMATE_OUTSIDE_TOLERANCE"
        else:
            acceptance_status = "NOT_ACCEPTED_NO_UNCERTAINTY"
        all_pass = all_pass and accepted_ok
        result.update(
            {
                "simulation_input_sha256": sim_summary["input_sha256"],
                "simulation_input_bytes": sim_summary["input_bytes"],
                "simulation_rows_validated": sim_summary["rows_validated"],
                "simulation_validator_version": sim_summary["tool_version"],
                "reference_input_sha256": ref_summary["input_sha256"],
                "reference_input_bytes": ref_summary["input_bytes"],
                "reference_rows_validated": ref_summary["rows_validated"],
                "reference_validator_version": ref_summary["tool_version"],
                "reference_component_identity": ref_summary["component_identity"],
                "reference_component_consistent": ref_summary[
                    "all_rows_component_consistent"
                ],
                "reference_basis": ref_basis,
                "reference_direct_pstar_comparable": direct_reference,
                "physics_comparable": physics_comparable,
                "reference_lookup_energy_MeV": lookup_energy,
                "reference_range_min_MeV": ref_min,
                "reference_range_max_MeV": ref_max,
                "reference_in_range": True,
                "ref_total_MeV_cm2_g": reference,
                "ratio": ratio,
                "delta_percent": delta,
                "tolerance_percent": tol_pct,
                "numeric_within_tolerance": numeric_ok,
                "uncertainty_method": UNCERTAINTY_METHOD,
                "uncertainty_evaluated": uncertainty_evaluated,
                "cross_energy_combination_policy": CROSS_ENERGY_COMBINATION_POLICY,
                "report_publication_policy": REPORT_PUBLICATION_POLICY,
                "acceptance_status": acceptance_status,
                "within_tolerance": accepted_ok,
                "report_float_serialization": REPORT_FLOAT_SERIALIZATION,
            }
        )
        results.append(result)

    if resolved_output is not None:
        report_summary = _write_report_atomically(
            resolved_output,
            REPORT_COLUMNS,
            results,
        )
        for result in results:
            result.update(report_summary)
        print(f"wrote {resolved_output}")
        print(
            f"REPORT OUTPUT VALIDATION: bytes={report_summary['report_output_bytes']} "
            f"sha256={report_summary['report_output_sha256']} "
            f"policy={REPORT_PUBLICATION_POLICY}"
        )

    print(
        "\nDeposited-energy proxy vs PSTAR (material=polystyrene, "
        f"rho={rho} g/cm^3, tolerance=+/-{tol_pct:g}%):"
    )
    print(
        f"{'particle':<9}{'E[MeV]':>18}{'n':>7}{'sim':>12}{'ref':>12}"
        f"{'ratio':>9}{'delta%':>9}  status"
    )
    for result in results:
        status = (
            "NONCOMPARABLE"
            if not result["physics_comparable"]
            else ("POINT_ONLY" if result["numeric_within_tolerance"] else "FAIL")
        )
        energy_text = repr(float(result["energy_MeV"]))
        print(
            f"{result['particle']:<9}{energy_text:>18}"
            f"{result['n_events']:>7d}{result['sim_total_MeV_cm2_g']:>12.4f}"
            f"{result['ref_total_MeV_cm2_g']:>12.4f}{result['ratio']:>9.4f}"
            f"{result['delta_percent']:>9.2f}  {status}"
        )
    grouped: dict[str, list[float]] = {}
    for result in results:
        grouped.setdefault(str(result["particle"]), []).append(float(result["ratio"]))
    for species, ratios in grouped.items():
        print(
            f"  descriptive point-estimate ratio range [{species}] = "
            f"[{min(ratios):.4f}, {max(ratios):.4f}] over "
            f"{len(ratios)} energy point(s); no combined estimate"
        )
    print(f"CROSS-ENERGY COMBINATION POLICY: {CROSS_ENERGY_COMBINATION_POLICY}")
    print(
        f"SIM INPUT VALIDATION: rows={sim_summary['rows_validated']} "
        f"sha256={sim_summary['input_sha256']} validator={SIM_TABLE_VALIDATOR_VERSION}"
    )
    print(f"ENERGY GROUPING: {ENERGY_GROUPING}")
    print(f"MASS STOPPING ESTIMATOR: {MASS_STOPPING_ESTIMATOR}")
    print(f"SUMMATION METHOD: {SUMMATION_METHOD}")
    print(f"REPORT FLOAT SERIALIZATION: {REPORT_FLOAT_SERIALIZATION}")
    print(f"REPORT PUBLICATION POLICY: {REPORT_PUBLICATION_POLICY}")
    print(
        f"PSTAR REFERENCE VALIDATION: rows={ref_summary['rows_validated']} "
        f"sha256={ref_summary['input_sha256']} validator={PSTAR_VALIDATOR_VERSION} "
        "component_sum=VALIDATED"
    )
    if has_deuteron:
        print(f"DEUTERON REFERENCE BASIS: {DEUTERON_REFERENCE_PROXY}")
    if basis == QUENCHED_BASIS:
        print("ENERGY DEPOSIT BASIS: QUENCHED_PROXY")
        print("NUMERICAL TOLERANCE: NOT_ACCEPTED_QUENCHED_PROXY")
    elif has_deuteron:
        print("ENERGY DEPOSIT BASIS: UNQUENCHED_RAW")
        print("NUMERICAL TOLERANCE: NOT_ACCEPTED_DEUTERON_PROXY")
    else:
        print("ENERGY DEPOSIT BASIS: UNQUENCHED_RAW")
        if results and all(result["numeric_within_tolerance"] for result in results):
            print("NUMERICAL TOLERANCE: POINT_ESTIMATE_ONLY_NOT_ACCEPTED")
        else:
            print("NUMERICAL TOLERANCE: FAIL")
    print(f"TRACK LENGTH SCOPE: {track_scope}")
    print(f"PSTAR PRIMARY IDENTITY OK: {primary_ok}")
    print(f"UNCERTAINTY EVALUATION: {UNCERTAINTY_METHOD}")
    print("SCIENTIFIC STATUS: DIAGNOSTIC_ONLY")
    return results, all_pass and bool(results)


def self_test(ref_path: Path | None = None) -> int:
    """Build synthetic proton events against the selected committed reference table."""
    reference_path = DEFAULT_REF if ref_path is None else ref_path
    if not reference_path.is_file():
        print(
            f"SELF-TEST: FAIL (reference table not found: {reference_path})",
            file=sys.stderr,
        )
        return 1
    try:
        table, ref_summary = _read_reference_with_summary(reference_path)
    except StoppingPowerInputError as exc:
        print(f"SELF-TEST: FAIL ({exc})", file=sys.stderr)
        return 1
    print(
        f"reference={reference_path.resolve()} "
        f"sha256={ref_summary['input_sha256']} rows={len(table)} "
        f"validator={PSTAR_VALIDATOR_VERSION} component_sum=VALIDATED"
    )
    cases = [
        ("proton", 60.0),
        ("proton", 100.0),
        ("proton", 150.0),
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
        print("=== self-test on synthetic proton events (expected ratio ~ 1.0) ===")
        results, _ = run_compare(
            simulation_path,
            reference_path,
            DEFAULT_RHO,
            None,
            tol_pct=2.0,
        )
    max_error = max(abs(float(result["ratio"]) - 1.0) for result in results)
    print(f"\nmax |ratio-1| = {max_error:.2e}")
    if max_error < 1e-6:
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
    parser.add_argument(
        "--allow-deuteron-proxy",
        action="store_true",
        help="permit labelled, non-accepting deuteron E/2 PSTAR proxy output",
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
            allow_deuteron_proxy=args.allow_deuteron_proxy,
        )
        return 0 if ok else 1
    except StoppingPowerInputError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
