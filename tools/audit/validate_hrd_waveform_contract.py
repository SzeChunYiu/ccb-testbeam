#!/usr/bin/env python3
"""Fail-closed structural audit for HRD waveform event layout.

This tool deliberately validates each event before reshaping.  It is intended to
falsify the historical failure mode where a batch of 8x16 waveforms can be
reshaped globally under an 8x18 configuration and silently mix event boundaries.

ROOT I/O is optional and imported lazily so the pure validation helpers remain
unit-testable without uproot.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np


@dataclass
class BatchValidation:
    events: int
    expected_words: int
    malformed_events: int
    malformed_indices: list[int]
    length_histogram: dict[str, int]


def _row_length(row: object) -> int:
    arr = np.asarray(row)
    return int(arr.size)


def validate_and_reshape_rows(
    rows: Sequence[object] | np.ndarray,
    *,
    n_channels: int,
    samples_per_channel: int,
) -> tuple[np.ndarray, BatchValidation]:
    """Validate every event length, then return ``(event, channel, sample)``.

    No truncation, padding, or aggregate/batch-level reshape is permitted.
    ``ValueError`` is raised if *any* row does not contain exactly
    ``n_channels * samples_per_channel`` scalar words.
    """
    if n_channels <= 0 or samples_per_channel <= 0:
        raise ValueError("n_channels and samples_per_channel must be positive")

    expected = int(n_channels * samples_per_channel)
    materialized = list(rows)
    lengths = [_row_length(row) for row in materialized]
    hist: dict[str, int] = {}
    for length in lengths:
        key = str(int(length))
        hist[key] = hist.get(key, 0) + 1
    bad = [idx for idx, length in enumerate(lengths) if length != expected]
    summary = BatchValidation(
        events=len(materialized),
        expected_words=expected,
        malformed_events=len(bad),
        malformed_indices=bad[:100],
        length_histogram=hist,
    )
    if bad:
        examples = ", ".join(f"{idx}:{lengths[idx]}" for idx in bad[:10])
        raise ValueError(
            f"HRD waveform contract violation: expected {expected} words/event "
            f"({n_channels}x{samples_per_channel}); malformed {len(bad)}/{len(materialized)}; "
            f"first index:length pairs [{examples}]"
        )

    if not materialized:
        return np.empty((0, n_channels, samples_per_channel), dtype=float), summary

    # Only after every row has passed the per-event width gate is stacking safe.
    matrix = np.stack([np.asarray(row) for row in materialized])
    if matrix.ndim != 2 or matrix.shape != (len(materialized), expected):
        raise ValueError(
            "HRD rows passed scalar-length checks but do not form a 2-D scalar matrix; "
            f"got shape {matrix.shape!r}. Nested/non-scalar event content is not supported."
        )
    return matrix.reshape(len(materialized), n_channels, samples_per_channel), summary


def _init_channel_stats(n_channels: int) -> list[dict[str, float | int | None]]:
    return [
        {
            "events": 0,
            "all_zero_events": 0,
            "constant_trace_events": 0,
            "variable_trace_events": 0,
            "min_adc": None,
            "max_adc": None,
        }
        for _ in range(n_channels)
    ]


def _update_channel_stats(stats: list[dict], waveforms: np.ndarray) -> None:
    for ch in range(waveforms.shape[1]):
        x = np.asarray(waveforms[:, ch, :])
        s = stats[ch]
        s["events"] += int(x.shape[0])
        if x.size == 0:
            continue
        s["all_zero_events"] += int(np.all(x == 0, axis=1).sum())
        variable = np.ptp(x, axis=1) != 0
        s["variable_trace_events"] += int(variable.sum())
        s["constant_trace_events"] += int((~variable).sum())
        xmin = float(np.nanmin(x))
        xmax = float(np.nanmax(x))
        s["min_adc"] = xmin if s["min_adc"] is None else min(float(s["min_adc"]), xmin)
        s["max_adc"] = xmax if s["max_adc"] is None else max(float(s["max_adc"]), xmax)


def audit_root(
    path: Path,
    *,
    tree_name: str,
    branch_name: str,
    n_channels: int,
    samples_per_channel: int,
    step_size: int,
    max_events: int | None,
) -> dict:
    try:
        import uproot  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise SystemExit("uproot is required for ROOT input: pip install uproot") from exc

    expected = n_channels * samples_per_channel
    total = 0
    malformed = 0
    length_hist: dict[str, int] = {}
    bad_examples: list[dict[str, int]] = []
    channel_stats = _init_channel_stats(n_channels)

    with uproot.open(path) as root_file:
        if tree_name not in root_file:
            raise SystemExit(f"tree {tree_name!r} not found in {path}")
        tree = root_file[tree_name]
        for batch in tree.iterate([branch_name], step_size=step_size, library="np"):
            rows = list(batch[branch_name])
            if max_events is not None:
                remaining = max_events - total
                if remaining <= 0:
                    break
                rows = rows[:remaining]
            lengths = [_row_length(row) for row in rows]
            for length in lengths:
                key = str(int(length))
                length_hist[key] = length_hist.get(key, 0) + 1
            bad_local = [idx for idx, length in enumerate(lengths) if length != expected]
            malformed += len(bad_local)
            for idx in bad_local[: max(0, 100 - len(bad_examples))]:
                bad_examples.append({"event_index": total + idx, "length": lengths[idx]})
            if bad_local:
                # Fail closed for this batch: do not reshape any event in it because a
                # malformed row is direct evidence of a broken structural contract.
                total += len(rows)
                if max_events is not None and total >= max_events:
                    break
                continue
            waveforms, _ = validate_and_reshape_rows(
                rows, n_channels=n_channels, samples_per_channel=samples_per_channel
            )
            _update_channel_stats(channel_stats, waveforms)
            total += len(rows)
            if max_events is not None and total >= max_events:
                break

    for ch, s in enumerate(channel_stats):
        events = int(s["events"])
        s["channel"] = ch
        s["variable_fraction"] = (
            float(s["variable_trace_events"]) / events if events else None
        )

    return {
        "input": str(path),
        "tree": tree_name,
        "branch": branch_name,
        "n_channels": n_channels,
        "samples_per_channel": samples_per_channel,
        "expected_words_per_event": expected,
        "events_scanned": total,
        "malformed_events": malformed,
        "length_histogram": length_hist,
        "malformed_examples": bad_examples,
        "channel_stats": channel_stats,
        "contract_pass": malformed == 0 and total > 0,
    }


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", type=Path)
    ap.add_argument("--tree", default="h101")
    ap.add_argument("--branch", default="HRDv")
    ap.add_argument("--channels", type=int, default=8)
    ap.add_argument("--samples-per-channel", type=int, required=True)
    ap.add_argument("--step-size", type=int, default=10000)
    ap.add_argument("--max-events", type=int)
    ap.add_argument("--require-last-channel-variable", action="store_true")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(list(argv) if argv is not None else None)

    result = audit_root(
        args.root,
        tree_name=args.tree,
        branch_name=args.branch,
        n_channels=args.channels,
        samples_per_channel=args.samples_per_channel,
        step_size=args.step_size,
        max_events=args.max_events,
    )
    if args.require_last_channel_variable and result["channel_stats"]:
        last = result["channel_stats"][-1]
        result["last_channel_variable_gate"] = bool(last["variable_trace_events"] > 0)
        result["contract_pass"] = bool(
            result["contract_pass"] and result["last_channel_variable_gate"]
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["contract_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
