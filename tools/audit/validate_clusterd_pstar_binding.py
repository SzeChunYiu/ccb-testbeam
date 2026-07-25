#!/usr/bin/env python3
"""Validate Cluster D VIS-MC-002 binding to the canonical PSTAR reference."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.audit.validate_pstar_component_sum import (  # noqa: E402
    PstarComponentError,
    read_validated_pstar_table,
)

TOOL_VERSION = "1.0.0"
POLICY = "CLUSTERD_VIS_MC_002_MUST_USE_CANONICAL_VALIDATED_PSTAR_REFERENCE"
FORMER_EMBEDDED = {10.0: 50.5, 50.0: 19.8, 100.0: 12.9, 150.0: 9.74}


class ValidationInputError(ValueError):
    """Raised when validation inputs cannot be trusted."""


def _snapshot(path: Path) -> tuple[str, dict[str, object]]:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise ValidationInputError(f"cannot read {path}: {exc}") from exc
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationInputError(f"invalid UTF-8 in {path}: {exc}") from exc
    return text, {
        "path": str(path),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _paths_alias(left: Path, right: Path) -> bool:
    left_resolved = _resolved(left)
    right_resolved = _resolved(right)
    if left_resolved == right_resolved:
        return True
    try:
        return left.exists() and right.exists() and os.path.samefile(left, right)
    except OSError:
        return False


def _write_json(path: Path, payload: dict[str, object], inputs: list[Path]) -> None:
    if any(_paths_alias(path, input_path) for input_path in inputs):
        raise ValidationInputError(f"output path aliases an input: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def validate(
    common_path: Path,
    transport_path: Path,
    run_script_path: Path,
    summary_path: Path,
    reference_path: Path,
) -> dict[str, object]:
    paths = [common_path, transport_path, run_script_path, summary_path, reference_path]
    texts: dict[str, str] = {}
    snapshots: dict[str, dict[str, object]] = {}
    for path in paths[:-1]:
        text, snapshot = _snapshot(path)
        texts[path.name] = text
        snapshots[path.name] = snapshot
    _, reference_snapshot = _snapshot(reference_path)
    snapshots[reference_path.name] = reference_snapshot

    findings: list[dict[str, str]] = []

    def require(condition: bool, code: str, message: str) -> None:
        if not condition:
            findings.append({"code": code, "message": message})

    common = texts[common_path.name]
    transport = texts[transport_path.name]
    run_script = texts[run_script_path.name]
    summary = texts[summary_path.name]

    require(
        "PSTAR_POLYSTYRENE = [" not in common,
        "EMBEDDED_REFERENCE_REMAINS",
        "_common.py still contains a second embedded PSTAR table",
    )
    require(
        "read_validated_pstar_table" in common,
        "CANONICAL_PARSER_NOT_IMPORTED",
        "_common.py does not invoke the shared exact-decimal PSTAR parser",
    )
    require(
        '"stopping_power_column": "total_MeV_cm2_g"' in common,
        "TOTAL_COLUMN_NOT_DECLARED",
        "campaign provenance does not declare the total stopping-power column",
    )
    require(
        "FAIL_CLOSED_OUTSIDE_VALIDATED_REFERENCE_DOMAIN" in common,
        "REFERENCE_RANGE_FAIL_CLOSED_MISSING",
        "campaign interpolation does not state fail-closed reference-domain behavior",
    )
    require(
        POLICY in transport,
        "TRANSPORT_POLICY_MISSING",
        "dedicated VIS-MC-002 renderer does not publish the canonical binding policy",
    )
    require(
        '"acceptance_statistic": "NONE"' in transport,
        "UNSUPPORTED_ACCEPTANCE_STATISTIC",
        "VIS-MC-002 does not explicitly withhold an acceptance statistic",
    )
    require(
        'ESTIMAND = "RATIO_OF_SUMS_TRACK_LENGTH_WEIGHTED"' in transport,
        "ESTIMAND_NOT_TRACEABLE",
        "VIS-MC-002 does not use the traceable ratio-of-sums estimator",
    )
    require(
        'UNCERTAINTY_METHOD = "NOT_EVALUATED"' in transport,
        "UNCERTAINTY_BOUNDARY_MISSING",
        "VIS-MC-002 does not explicitly withhold uncertainty evaluation",
    )
    require(
        "DIAGNOSTIC_PROXY_NOT_ACCEPTED_STOPPING_POWER_CLOSURE" in transport,
        "SCIENTIFIC_BOUNDARY_MISSING",
        "VIS-MC-002 does not preserve the diagnostic-only scientific boundary",
    )
    require(
        "vis_mc_002_transport.py" in run_script,
        "REPRODUCER_NOT_MIGRATED",
        "Cluster D run script does not execute the canonical VIS-MC-002 renderer",
    )
    require(
        "VIS-MC-002_transport_vs_pstar.png" in summary and "SUPERSEDED" in summary,
        "LEGACY_PLOT_NOT_QUARANTINED",
        "summary does not quarantine the embedded-table legacy plot",
    )
    require(
        "VIS-MC-002_transport_vs_pstar_canonical.png" in summary,
        "CANONICAL_PLOT_NOT_DOCUMENTED",
        "summary does not name the canonical regenerated plot",
    )

    try:
        rows, provenance = read_validated_pstar_table(reference_path)
    except PstarComponentError as exc:
        findings.append({"code": "REFERENCE_REJECTED", "message": str(exc)})
        rows = []
        provenance = {}

    canonical = {float(row[0]): float(row[3]) for row in rows}
    comparison: dict[str, dict[str, float]] = {}
    for energy, former in FORMER_EMBEDDED.items():
        if energy not in canonical:
            findings.append(
                {
                    "code": "REFERENCE_ENERGY_MISSING",
                    "message": f"canonical reference lacks {energy} MeV",
                }
            )
            continue
        current = canonical[energy]
        comparison[str(int(energy))] = {
            "former_embedded_total_MeV_cm2_g": former,
            "canonical_total_MeV_cm2_g": current,
            "former_relative_bias_percent": (former / current - 1.0) * 100.0,
        }

    return {
        "schema_version": 1,
        "tool": "tools/audit/validate_clusterd_pstar_binding.py",
        "tool_version": TOOL_VERSION,
        "policy": POLICY,
        "status": "VALIDATED" if not findings else "FLAWED",
        "findings": findings,
        "finding_count": len(findings),
        "inputs": snapshots,
        "reference_validation": provenance,
        "former_vs_canonical_reference": comparison,
        "scientific_boundary": (
            "Software/reference provenance only. Existing external ROOT paths were not "
            "reprocessed, and no accepted stopping-power closure is claimed."
        ),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--common", type=Path, required=True)
    parser.add_argument("--transport", type=Path, required=True)
    parser.add_argument("--run-script", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    inputs = [args.common, args.transport, args.run_script, args.summary, args.reference]
    try:
        result = validate(*inputs)
        if args.output:
            _write_json(args.output, result, inputs)
    except (OSError, ValidationInputError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(
        "Cluster D PSTAR binding: "
        f"status={result['status']} findings={result['finding_count']}"
    )
    return 0 if result["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
