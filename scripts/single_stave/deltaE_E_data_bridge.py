#!/usr/bin/env python3
"""ΔE-E rerun with the COMPOSITE key on real data (A-002 CCB-DELTAE-FIX).

Builds a wide ΔE-E data table from the real per-hit pulse table using the
composite key ``(source_file_id, run, evt)`` instead of ``eventno`` alone.

The original bridge accidentally kept ``eventno`` in the aggregation and pivot
indices. If one physical ``(run, evt)`` had more than one eventno value, that
split one physical event into multiple output rows and made the stopping-layer
counts exceed the reported physical-event count. This implementation treats
``eventno`` only as a collision diagnostic and enforces one output row per
physical composite key.

Bare ``amplitude_adc`` is deliberately rejected because the repository schema
audit classifies it as ambiguous: it may be a peak code or a baseline-subtracted
height. The bridge requires an explicit amplitude field or caller override.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

R = Path("/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam")
SRC = R / "reports/1781014251.574.7a497937/pulse_taxonomy_table.csv.gz"
OUT = Path("/projects/hep/fs10/shared/nnbar/billy/ccb_deltae_rerun")
THRESHOLD_ADC = 200.0
LAYERS = ("B2", "B4", "B6", "B8")
SAFE_AMPLITUDE_COLUMNS = ("median_amp_adc", "peak_height_adc", "net_adc")
AMBIGUOUS_AMPLITUDE_COLUMN = "amplitude_adc"


def resolve_amplitude_column(
    pulses: pd.DataFrame,
    requested: str | None = None,
) -> str:
    """Return an explicit amplitude column and reject ambiguous fallbacks.

    ``amplitude_adc`` is accepted only when the caller explicitly requests it.
    This makes any use of the ambiguous legacy field visible in code, command
    provenance, and the generated result metadata rather than silently choosing
    it by fallback.
    """
    if requested is not None:
        if requested not in pulses.columns:
            raise ValueError(f"requested amplitude column is missing: {requested}")
        return requested

    available = [name for name in SAFE_AMPLITUDE_COLUMNS if name in pulses.columns]
    if len(available) == 1:
        return available[0]
    if len(available) > 1:
        raise ValueError(
            "multiple explicit amplitude columns are present; select one with "
            f"amplitude_column=...: {available}"
        )
    if AMBIGUOUS_AMPLITUDE_COLUMN in pulses.columns:
        raise ValueError(
            "bare amplitude_adc is schema-ambiguous and cannot be selected "
            "implicitly; regenerate an explicit peak_height_adc/net_adc field "
            "or pass amplitude_column='amplitude_adc' with documented semantics"
        )
    raise ValueError(
        "no supported amplitude column found; expected exactly one of "
        f"{list(SAFE_AMPLITUDE_COLUMNS)}"
    )


def build_event_table(
    pulses: pd.DataFrame,
    *,
    source_file_id: str,
    threshold_adc: float = THRESHOLD_ADC,
    amplitude_column: str | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Build one ΔE-E row per physical ``(source_file_id, run, evt)`` event.

    ``eventno`` is deliberately excluded from the event-table key. It is used
    only to quantify how unsafe an eventno-only join would be and how often one
    physical key carries multiple eventno values.
    """
    ampcol = resolve_amplitude_column(pulses, amplitude_column)
    required = {"run", "evt", "eventno", "stave", ampcol}
    missing = sorted(required.difference(pulses.columns))
    if missing:
        raise ValueError(f"missing required pulse columns: {missing}")

    df = pulses[["run", "evt", "eventno", "stave", ampcol]].copy()
    df["stave"] = df["stave"].astype(str)

    physical_keys = ["run", "evt"]
    eventno_per_physical = df.groupby(physical_keys, dropna=False)["eventno"].nunique()
    n_comp = int(eventno_per_physical.size)
    physical_multi_eventno = int((eventno_per_physical > 1).sum())

    eventno_to_physical = (
        df[["eventno", *physical_keys]]
        .drop_duplicates()
        .groupby("eventno", dropna=False)
        .size()
    )
    collide = int((eventno_to_physical > 1).sum())
    collide_events = int(eventno_to_physical[eventno_to_physical > 1].sum())

    # Aggregate all hits for a physical event and stave before pivoting. Keeping
    # eventno here would split a single physical event into multiple rows.
    agg = (
        df.groupby([*physical_keys, "stave"], dropna=False)[ampcol]
        .max()
        .reset_index()
    )
    wide = (
        agg.pivot_table(
            index=physical_keys,
            columns="stave",
            values=ampcol,
            aggfunc="max",
        )
        .reset_index()
    )
    wide.insert(0, "source_file_id", source_file_id)

    for layer in LAYERS:
        wide[f"amp_{layer}"] = (
            wide[layer].fillna(0.0) if layer in wide.columns else 0.0
        )

    wide["deltaE_data_adc"] = wide["amp_B2"]
    wide["E_data_adc"] = wide["amp_B4"] + wide["amp_B6"] + wide["amp_B8"]

    amplitudes = wide[[f"amp_{layer}" for layer in LAYERS]].to_numpy(dtype=float)
    passed = amplitudes > float(threshold_adc)
    deepest_index = np.where(passed, np.arange(len(LAYERS)), -1).max(axis=1)
    wide["stopping_layer"] = np.where(
        deepest_index >= 0,
        np.asarray(LAYERS, dtype=object)[np.maximum(deepest_index, 0)],
        "none",
    )
    wide["category"] = np.where(
        wide["E_data_adc"] + wide["deltaE_data_adc"] <= 0,
        "all_zero",
        "ok",
    )

    if len(wide) != n_comp:
        raise RuntimeError(
            "composite-key event-table cardinality mismatch: "
            f"{len(wide)} rows for {n_comp} physical events"
        )

    stopping_distribution = {
        str(key): int(value)
        for key, value in wide["stopping_layer"].value_counts().items()
    }
    if sum(stopping_distribution.values()) != n_comp:
        raise RuntimeError(
            "stopping-distribution cardinality mismatch: "
            f"{sum(stopping_distribution.values())} bins for {n_comp} events"
        )

    result: dict[str, object] = {
        "source_file_id": source_file_id,
        "key": ["source_file_id", "run", "evt"],
        "amplitude_column": ampcol,
        "amplitude_column_explicitly_requested": amplitude_column is not None,
        "n_events_composite_key": n_comp,
        "n_eventno_values": int(df["eventno"].nunique(dropna=False)),
        "eventno_values_spanning_multiple_events": collide,
        "events_that_eventno_only_join_would_corrupt": collide_events,
        "physical_events_with_multiple_eventno_values": physical_multi_eventno,
        "threshold_adc": float(threshold_adc),
        "stopping_distribution": stopping_distribution,
        "stopping_distribution_total": int(sum(stopping_distribution.values())),
        "staves_present": sorted(set(df["stave"])),
        "units": "ADC (data); never relabeled MeV",
    }
    return wide, result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source_file_id = SRC.parent.name
    pulses = pd.read_csv(SRC)
    wide, result = build_event_table(
        pulses,
        source_file_id=source_file_id,
        threshold_adc=THRESHOLD_ADC,
    )
    result["source"] = str(SRC)
    result["note"] = (
        "Missing B layers are filled with zero only after composite-key "
        "aggregation and cardinality validation."
    )

    with (OUT / "result.json").open("w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    wide.to_csv(OUT / "deltaE_E_events_data.csv", index=False)

    ok = wide[wide["category"] == "ok"]
    plt.figure(figsize=(6, 4.5))
    plt.hexbin(
        ok["E_data_adc"],
        ok["deltaE_data_adc"],
        gridsize=40,
        mincnt=1,
        bins="log",
        cmap="viridis",
    )
    plt.colorbar(label="log count")
    plt.xlabel("E = amp(B4+B6+B8) [ADC]")
    plt.ylabel("ΔE = amp(B2) [ADC]")
    plt.title(f"ΔE-E (composite key, {len(wide)} events)")
    plt.tight_layout()
    plt.savefig(OUT / "DE-01_deltaE_E_data.png", dpi=130)

    print(json.dumps(result, indent=2))
    print("DELTAE_RERUN_DONE")


if __name__ == "__main__":
    main()
