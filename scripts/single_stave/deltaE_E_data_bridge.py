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
audit shows that its semantics vary by table. The bridge requires a measured
absolute/net convention. Absolute ADC codes additionally require an explicit
pulse polarity; the signed pedestal conversion is never replaced by ``abs``.
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
    amplitude_convention: str | None = None,
) -> tuple[str, str]:
    """Return the source amplitude column and its explicit signal convention.

    Explicit net-height fields are treated as NET. Legacy ``amplitude_adc``
    requires the caller to state ``absolute`` or ``net``. Absolute conversion
    also requires an explicit polarity in :func:`build_event_table`.
    """
    convention = amplitude_convention.lower() if amplitude_convention else None
    if convention not in {None, "absolute", "net"}:
        raise ValueError("amplitude_convention must be 'absolute' or 'net'")

    if requested is not None:
        if requested not in pulses.columns:
            raise ValueError(f"requested amplitude column is missing: {requested}")
        if requested == AMBIGUOUS_AMPLITUDE_COLUMN:
            if convention is None:
                raise ValueError(
                    "amplitude_adc requires amplitude_convention='absolute' or 'net'"
                )
            if convention == "absolute" and "baseline_adc" not in pulses.columns:
                raise ValueError(
                    "absolute amplitude_adc requires baseline_adc for conversion"
                )
            return requested, convention
        if convention not in {None, "net"}:
            raise ValueError(
                f"{requested} is an explicit net-height field; "
                "amplitude_convention='absolute' is inconsistent"
            )
        return requested, "net"

    available = [name for name in SAFE_AMPLITUDE_COLUMNS if name in pulses.columns]
    if len(available) == 1:
        if convention not in {None, "net"}:
            raise ValueError(
                f"{available[0]} is an explicit net-height field; "
                "amplitude_convention='absolute' is inconsistent"
            )
        return available[0], "net"
    if len(available) > 1:
        raise ValueError(
            "multiple explicit amplitude columns are present; select one with "
            f"amplitude_column=...: {available}"
        )
    if AMBIGUOUS_AMPLITUDE_COLUMN in pulses.columns:
        raise ValueError(
            "bare amplitude_adc has table-dependent semantics and cannot be "
            "selected implicitly; pass amplitude_column='amplitude_adc' plus "
            "amplitude_convention='absolute' or 'net' from measured provenance"
        )
    raise ValueError(
        "no supported amplitude column found; expected exactly one of "
        f"{list(SAFE_AMPLITUDE_COLUMNS)}"
    )


def _convert_absolute_codes(
    frame: pd.DataFrame,
    amplitude_column: str,
    polarity: str,
) -> pd.Series:
    """Convert absolute ADC codes to signed positive signal heights.

    ``positive`` means pulses rise above the pedestal and uses
    ``amplitude - baseline``. ``negative`` means pulses fall below the pedestal
    and uses ``baseline - amplitude``. Rows on the opposite side fail closed;
    taking an absolute value would silently convert a polarity mismatch into a
    large positive energy deposit.
    """
    numeric = frame[[amplitude_column, "baseline_adc"]].apply(
        pd.to_numeric, errors="coerce"
    )
    finite = np.isfinite(numeric.to_numpy(dtype=float, na_value=np.nan)).all(axis=1)
    if not finite.all():
        bad = int((~finite).sum())
        raise ValueError(
            f"absolute amplitude conversion requires finite numeric values; {bad} rows fail"
        )

    if polarity == "positive":
        signal = numeric[amplitude_column] - numeric["baseline_adc"]
    else:
        signal = numeric["baseline_adc"] - numeric[amplitude_column]

    violations = int((signal < 0).sum())
    if violations:
        raise ValueError(
            f"{violations} absolute amplitude rows violate {polarity}-going pulse polarity"
        )
    return signal


def _coerce_net_heights(frame: pd.DataFrame, amplitude_column: str) -> pd.Series:
    """Return finite numeric net amplitudes before any aggregation or zero fill."""
    numeric = pd.to_numeric(frame[amplitude_column], errors="coerce")
    finite = np.isfinite(numeric.to_numpy(dtype=float, na_value=np.nan))
    if not finite.all():
        bad = int((~finite).sum())
        raise ValueError(
            f"net amplitude input requires finite numeric values; {bad} rows fail"
        )
    return numeric


def build_event_table(
    pulses: pd.DataFrame,
    *,
    source_file_id: str,
    threshold_adc: float = THRESHOLD_ADC,
    amplitude_column: str | None = None,
    amplitude_convention: str | None = None,
    amplitude_polarity: str | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Build one ΔE-E row per physical ``(source_file_id, run, evt)`` event.

    ``eventno`` is deliberately excluded from the event-table key. It is used
    only to quantify how unsafe an eventno-only join would be and how often one
    physical key carries multiple eventno values.
    """
    ampcol, convention = resolve_amplitude_column(
        pulses, amplitude_column, amplitude_convention
    )
    polarity = amplitude_polarity.lower() if amplitude_polarity else None
    if polarity not in {None, "positive", "negative"}:
        raise ValueError("amplitude_polarity must be 'positive' or 'negative'")
    if convention == "absolute" and polarity is None:
        raise ValueError(
            "absolute amplitude conversion requires amplitude_polarity='positive' "
            "or 'negative' from measured provenance"
        )
    if convention != "absolute" and polarity is not None:
        raise ValueError("amplitude_polarity is only valid for absolute amplitude input")

    required = {"run", "evt", "eventno", "stave", ampcol}
    if convention == "absolute":
        required.add("baseline_adc")
    missing = sorted(required.difference(pulses.columns))
    if missing:
        raise ValueError(f"missing required pulse columns: {missing}")

    selected = ["run", "evt", "eventno", "stave", ampcol]
    if convention == "absolute":
        selected.append("baseline_adc")
    df = pulses[selected].copy()
    df["stave"] = df["stave"].astype(str)
    signal_column = "_signal_height_adc"
    if convention == "absolute":
        assert polarity is not None
        df[signal_column] = _convert_absolute_codes(df, ampcol, polarity)
        amplitude_validation = "FINITE_NUMERIC_AND_POLARITY_VALIDATED_BEFORE_AGGREGATION"
    else:
        df[signal_column] = _coerce_net_heights(df, ampcol)
        amplitude_validation = "FINITE_NUMERIC_NET_HEIGHT_VALIDATED_BEFORE_AGGREGATION"

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
        df.groupby([*physical_keys, "stave"], dropna=False)[signal_column]
        .max()
        .reset_index()
    )
    wide = (
        agg.pivot_table(
            index=physical_keys,
            columns="stave",
            values=signal_column,
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
        "amplitude_convention": convention,
        "amplitude_polarity": polarity,
        "amplitude_transform": (
            f"{ampcol} - baseline_adc"
            if convention == "absolute" and polarity == "positive"
            else f"baseline_adc - {ampcol}"
            if convention == "absolute" and polarity == "negative"
            else "identity"
        ),
        "amplitude_validation": amplitude_validation,
        "missing_layer_policy": (
            "ZERO_FILL_ONLY_AFTER_FINITE_ROW_VALIDATION_AND_EVENT_STAVE_AGGREGATION"
        ),
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
        "Missing B layers are filled with zero only after finite row validation, "
        "composite-key aggregation, and cardinality validation."
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
