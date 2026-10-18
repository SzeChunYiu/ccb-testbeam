"""Strict reference for trigger selection accounting; NOT a hardware model.

Same-population identity is a caller's source-bound contract, not inferred here.
No ROOT reading, species inference, transport, weights, or release authorization.
"""
from __future__ import annotations

import math
from itertools import product
from typing import Any

MAX_EXACT_COUNT = 2**53


def count(value: Any) -> int:
    if type(value) is not int or not 0 <= value <= MAX_EXACT_COUNT:
        raise ValueError("count must be an integer in [0, 2**53], not bool")
    return value


def identifier(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("nonempty explicit identity required")
    return value


def positive(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("coordinate must be numeric, not bool/string")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError("coordinate must be finite and positive")
    return number


def ratio(numerator: int, denominator: int) -> dict[str, Any]:
    numerator, denominator = count(numerator), count(denominator)
    if numerator > denominator:
        raise ValueError("numerator exceeds denominator")
    return {"numerator": numerator, "denominator": denominator,
            "estimate": numerator / denominator if denominator else None,
            "status": "ESTIMABLE" if denominator else "NOT_ESTIMABLE"}


def _index(rows: list[dict[str, Any]]) -> dict[tuple[str, int], bool]:
    if not isinstance(rows, list):
        raise ValueError("event records must be a list")
    result = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"run_id", "event_id", "passed"}:
            raise ValueError("exact run_id/event_id/passed schema required; weights unsupported")
        key = (identifier(row["run_id"]), count(row["event_id"]))
        if type(row["passed"]) is not bool:
            raise ValueError("passed must be a Boolean, not numeric or unknown")
        if key in result:
            raise ValueError("duplicate event key; never silently deduplicate")
        result[key] = row["passed"]
    return result


def joint_counts(proxy_rows: list[dict[str, Any]], hardware_rows: list[dict[str, Any]],
                 *, population_id: str) -> dict[str, Any]:
    """Compute joint events after exact composite-key alignment; no inner-join loss."""
    population_id = identifier(population_id)
    proxy, hardware = _index(proxy_rows), _index(hardware_rows)
    if proxy.keys() != hardware.keys():
        raise ValueError("population keys differ; missing/rejected events need reconciliation")
    cells = {"both": 0, "neither": 0, "proxy_only": 0, "hardware_only": 0}
    for key in sorted(proxy):
        p, h = proxy[key], hardware[key]
        cell = "both" if p and h else "proxy_only" if p else "hardware_only" if h else "neither"
        cells[cell] += 1
    total = len(proxy)
    npass = cells["both"] + cells["proxy_only"]
    hpass = cells["both"] + cells["hardware_only"]
    return {"population_id": population_id, "n_total": total, "counts": cells,
            "rates": {"proxy_acceptance": ratio(npass, total),
                      "hardware_acceptance": ratio(hpass, total),
                      "hardware_given_proxy": ratio(cells["both"], npass),
                      "proxy_given_hardware": ratio(cells["both"], hpass),
                      "proxy_loss": ratio(cells["proxy_only"], npass)},
            "uncertainty": "NOT_EVALUATED", "weighted": False,
            "scientific_release": "NOT_AUTHORIZED"}


def marginal_bounds(n_total: int, n_proxy: int, n_hardware: int,
                    *, population_id: str) -> dict[str, Any]:
    """Sharp coupled Frechet bounds for a known common finite population.

    These are identification bounds, NOT confidence intervals. Equality of N
    alone cannot establish that two real tables share this population.
    """
    population_id = identifier(population_id)
    n, p, h = count(n_total), count(n_proxy), count(n_hardware)
    if p > n or h > n:
        raise ValueError("accepted count exceeds population")
    lo, hi = max(0, p + h - n), min(p, h)
    loss = [(p-hi)/p, (p-lo)/p] if p else None
    return {"population_id": population_id, "n_total": n,
            "both_bounds": [lo, hi], "proxy_only_bounds": [p-hi, p-lo],
            "hardware_only_bounds": [h-hi, h-lo],
            "neither_bounds": [n-p-h+lo, n-p-h+hi],
            "proxy_loss_bounds": loss, "joint_counts_identified": lo == hi,
            "constraint": "one common integer J in both_bounds determines all four cells",
            "uncertainty": "IDENTIFICATION_BOUNDS_NOT_CONFIDENCE_INTERVALS",
            "scientific_release": "NOT_AUTHORIZED"}


def scan_surface(rows: list[dict[str, Any]], *, thresholds: list[float],
                 windows: list[float], population_id: str) -> dict[str, Any]:
    """Preserve both scan coordinates and refuse missing/duplicate grid cells.

    Counts are unweighted for a declared common population. No generic threshold
    monotonicity is imposed: changing the threshold can change selected times.
    """
    population_id = identifier(population_id)
    if not isinstance(rows, list) or not isinstance(thresholds, list) or not isinstance(windows, list):
        raise ValueError("scan rows and both axes must be lists")
    ts, ws = [positive(x) for x in thresholds], [positive(x) for x in windows]
    if not ts or not ws or len(set(ts)) != len(ts) or len(set(ws)) != len(ws):
        raise ValueError("nonempty unique scan axes required")
    grid = set(product(ts, ws))
    observed = {}
    totals = set()
    expected = {"threshold_mev", "coinc_ns", "n_total", "n_pass", "population_id"}
    for row in rows:
        if not isinstance(row, dict) or set(row) != expected:
            raise ValueError("exact scan schema required")
        if row["population_id"] != population_id:
            raise ValueError("scan population identity differs")
        key = (positive(row["threshold_mev"]), positive(row["coinc_ns"]))
        if key not in grid or key in observed:
            raise ValueError("unexpected or duplicate scan coordinate")
        r = ratio(row["n_pass"], row["n_total"])
        totals.add(r["denominator"])
        observed[key] = {"threshold_mev": key[0], "coinc_ns": key[1], **r}
    if observed.keys() != grid or len(totals) != 1:
        raise ValueError("incomplete scan grid or inconsistent population denominator")
    return {"population_id": population_id,
            "rows": [observed[key] for key in sorted(grid)],
            "scientific_release": "NOT_AUTHORIZED"}


def zero_success_upper(n: int, *, confidence: float, sided: str,
                       sampling_model: str) -> float:
    """Binomial zero-success upper endpoint; no weighted/correlated-event claim."""
    n = count(n)
    if not n or sampling_model != "independent_identical_bernoulli":
        raise ValueError("positive independent Bernoulli trial count required")
    level = positive(confidence)
    if level >= 1 or sided not in {"one-sided", "two-sided-equal-tail"}:
        raise ValueError("explicit confidence in (0,1) and sidedness required")
    alpha = (1-level) / (2 if sided == "two-sided-equal-tail" else 1)
    return -math.expm1(math.log(alpha) / n)
