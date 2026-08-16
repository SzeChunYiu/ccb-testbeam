"""Machine-readable run ledger helpers (#962)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


SCHEMA = "ccb-run-ledger/1"


class RunLedgerError(RuntimeError):
    """Invalid or contradictory run-ledger content."""


def load_run_ledger(path: Path | str) -> dict[str, Any]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise RunLedgerError(f"run ledger must be a mapping: {path}")
    if payload.get("schema") != SCHEMA:
        raise RunLedgerError(
            f"unsupported run ledger schema {payload.get('schema')!r}; expected {SCHEMA}"
        )
    return payload


def sample_ii_calibration_runs(ledger: dict[str, Any]) -> list[int]:
    sample_ii = ledger.get("samples", {}).get("sample_ii", {})
    runs = [int(r) for r in sample_ii.get("calibration_runs", [])]
    if not runs:
        raise RunLedgerError("sample_ii.calibration_runs missing/empty in run ledger")
    return runs


def assert_no_role_contradiction(ledger: dict[str, Any]) -> None:
    """Fail if the same run is both calibration and independent validation for one study object."""
    for study, roles in (ledger.get("study_roles") or {}).items():
        calib = set(int(x) for x in roles.get("calibration", []))
        heldout = set(int(x) for x in roles.get("independent_validation", []))
        overlap = calib & heldout
        if overlap:
            raise RunLedgerError(
                f"study {study!r} assigns runs {sorted(overlap)} to both "
                "calibration and independent_validation"
            )


def reconcile_sample_ii_calibration(ledger: dict[str, Any]) -> dict[str, Any]:
    """Return the evidence-bound Sample II calibration decision (run 64, not 61)."""
    decision = ledger.get("decisions", {}).get("sample_ii_calibration_run", {})
    if int(decision.get("canonical_run", -1)) != 64:
        raise RunLedgerError(
            "canonical Sample II calibration run must be 64 per newer report evidence"
        )
    if 61 in sample_ii_calibration_runs(ledger):
        raise RunLedgerError("run 61 must not appear in sample_ii calibration_runs")
    return decision


ROLE_KEYS = ("sample_i_calib", "sample_i_analysis", "sample_ii_calib", "sample_ii_analysis")
VALIDATION_KEYS = (
    "heldout_runs",
    "validation_runs",
    "independent_validation",
    "independent_validation_runs",
)


def ledger_run_universe(ledger: dict[str, Any]) -> set[int]:
    """Every run number the ledger knows about (any role, including excluded)."""
    runs: set[int] = set()
    for sample in (ledger.get("samples") or {}).values():
        for key in ("calibration_runs", "analysis_runs", "light_collection_dedicated_runs"):
            value = sample.get(key)
            if isinstance(value, list):
                runs |= {int(x) for x in value}
        excluded = sample.get("excluded_runs")
        if isinstance(excluded, dict):
            runs |= {int(x) for x in excluded}
    runs |= {int(r) for r in (ledger.get("runs") or {})}
    if not runs:
        raise RunLedgerError("run ledger declares no runs at all")
    return runs


def _canonical_groups(ledger: dict[str, Any]) -> dict[tuple[str, str], set[int]]:
    groups: dict[tuple[str, str], set[int]] = {}
    for sample_name, sample in (ledger.get("samples") or {}).items():
        groups[(sample_name, "calib")] = {int(x) for x in sample.get("calibration_runs", [])}
        groups[(sample_name, "analysis")] = {int(x) for x in sample.get("analysis_runs", [])}
    return groups


def _run_list(value: Any, universe: set[int]) -> list[int] | None:
    """Run-number list iff value is a non-empty int list inside the beam-run universe.

    Count-like reuse of the same keys (expected-count blocks carrying pulse
    totals such as ``[14630]``) is deliberately not a run list and is ignored.
    """
    if not isinstance(value, list) or not value:
        return None
    if all(isinstance(x, int) and not isinstance(x, bool) and x in universe for x in value):
        return list(value)
    return None


def _walk_blocks(payload: Any, universe: set[int], rel: str, path: str = ""):
    if isinstance(payload, dict):
        yield rel, path or ".", payload
        for key, value in payload.items():
            yield from _walk_blocks(value, universe, rel, f"{path}.{key}" if path else key)
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            yield from _walk_blocks(value, universe, rel, f"{path}[{index}]")


def iter_config_run_role_blocks(repo_root: Path | str, universe: set[int]):
    """Yield (file, dotted_path, block) for every configs/ mapping holding run-role keys."""
    repo_root = Path(repo_root)
    for path in sorted((repo_root / "configs").rglob("*")):
        if path.suffix not in (".json", ".yaml", ".yml") or not path.is_file():
            continue
        try:
            if path.suffix == ".json":
                payload = json.loads(path.read_text(encoding="utf-8"))
            else:
                payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:  # surface the file, not the parser internals
            raise RunLedgerError(f"unreadable config {path}: {exc}") from exc
        yield from _walk_blocks(payload, universe, str(path.relative_to(repo_root)))


def assert_configs_consistent_with_ledger(
    ledger: dict[str, Any], repo_root: Path | str
) -> dict[str, int]:
    """Enforce the #962 run-role contract across every config run-role block.

    Rules:

    1. ``sample_ii_calib`` run lists equal the ledger calibration runs
       (run 64, never 61).
    2. Every role list stays inside the ledger's canonical group for that
       sample and role (excluded runs 38/43 cannot re-enter analysis).
    3. Within one block (one declared grouping context, i.e. one fitted
       object) no run is both calibration and held-out/validation.
       Cross-object reuse inside one file (a template-calibration population
       versus an ML train/test split) is allowed, matching the issue's
       "for the same fitted object" wording.
    """
    universe = ledger_run_universe(ledger)
    canonical = _canonical_groups(ledger)
    calib_ii = sample_ii_calibration_runs(ledger)
    errors: list[str] = []
    blocks = 0
    for rel, path, block in iter_config_run_role_blocks(repo_root, universe):
        roles: dict[str, list[int]] = {}
        for key in ROLE_KEYS:
            if key in block:
                runs = _run_list(block[key], universe)
                if runs:
                    roles[key] = runs
        if not roles:
            continue
        blocks += 1
        declared = roles.get("sample_ii_calib")
        if declared is not None and declared != calib_ii:
            errors.append(f"{rel}:{path} sample_ii_calib {declared} != ledger {calib_ii}")
        for key, runs in roles.items():
            sample = "sample_ii" if key.startswith("sample_ii") else "sample_i"
            role = "calib" if key.endswith("calib") else "analysis"
            extra = set(runs) - canonical[(sample, role)]
            if extra:
                errors.append(f"{rel}:{path} {key} has non-ledger runs {sorted(extra)}")
        calib = set(roles.get("sample_i_calib") or []) | set(roles.get("sample_ii_calib") or [])
        for vkey in VALIDATION_KEYS:
            heldout = _run_list(block.get(vkey), universe)
            if heldout:
                overlap = calib & set(heldout)
                if overlap:
                    errors.append(
                        f"{rel}:{path} runs {sorted(overlap)} both calibration and {vkey}"
                    )
    if errors:
        head = "; ".join(errors[:10])
        more = f" (+{len(errors) - 10} more)" if len(errors) > 10 else ""
        raise RunLedgerError(f"config run-role contradictions: {head}{more}")
    return {"blocks_checked": blocks}

