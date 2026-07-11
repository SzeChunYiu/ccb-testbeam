#!/usr/bin/env python3
"""Ticket-local S25c saturation recovery energy/PID waveform benchmark."""

from pathlib import Path

import pandas as pd

import s25c_1783762816_2556_026a1556_timing_mediated_pid_energy_ablation as base


base.CONFIG = (
    Path(__file__).resolve().parents[1]
    / "configs/s25c_1783776900_14960_721776e3_saturation_recovery_energy_pid_waveform.json"
)


def md_table_without_tabulate(df, columns):
    view = df.loc[:, list(columns)].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: "" if pd.isna(x) else f"{x:.4g}")
    headers = [str(col) for col in view.columns]
    rows = [[str(value) for value in row] for row in view.to_numpy()]
    widths = [
        max(len(headers[i]), *(len(row[i]) for row in rows)) if rows else len(headers[i])
        for i in range(len(headers))
    ]

    def fmt(values):
        return "| " + " | ".join(str(values[i]).ljust(widths[i]) for i in range(len(values))) + " |"

    sep = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    return "\n".join([fmt(headers), sep, *[fmt(row) for row in rows]])


base.md_table = md_table_without_tabulate


if __name__ == "__main__":
    base.main()
