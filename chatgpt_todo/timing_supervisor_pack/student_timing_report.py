#!/usr/bin/env python3
# ruff: noqa: F403, F405
"""Modular component of the student timing walkthrough."""
from student_timing_types import *  # noqa: F403
from student_timing_data import *  # noqa: F403
from student_timing_analysis import *  # noqa: F403
from student_timing_plots_basic import *  # noqa: F403
from student_timing_plots_advanced import *  # noqa: F403


def markdown_table(frame: pd.DataFrame, columns: Sequence[str]) -> list[str]:
    if frame.empty:
        return ["No rows were available."]
    selected = frame[list(columns)].copy()
    header = "| " + " | ".join(columns) + " |"
    separator = "|" + "|".join("---" for _ in columns) + "|"
    rows = [header, separator]
    for _, row in selected.iterrows():
        values: list[str] = []
        for column in columns:
            value = row[column]
            if isinstance(value, float):
                values.append(f"{value:.6g}")
            else:
                values.append(str(value))
        rows.append("| " + " | ".join(values) + " |")
    return rows


def write_report(
    out_dir: Path,
    lane_records: Sequence[tuple[WaveformDataset, LaneResult, list[str]]],
    comparison_stems: Sequence[str],
) -> None:
    lines = [
        "# Student timing-study report",
        "",
        "This report follows the evidence in the same order that a new student should ask questions.",
        "A timestamp is never trusted merely because its final histogram is narrow.",
        "",
        "## Four quantities that must not be confused",
        "",
        "1. A **sample interval** is the distance between recorded waveform points.",
        "2. A **timestamp** is the interpolated crossing assigned to one waveform.",
        "3. A **pair residual** is a corrected difference between two timestamps.",
        "4. A **single-stave resolution** is an inferred detector parameter and needs a reference or a validated multi-pair model.",
        "",
        "The first two can be sub-sample. The fourth does not follow from one pair width.",
        "",
    ]
    for dataset, result, plot_stems in lane_records:
        lines.extend(
            [
                f"## Lane: {result.config.name}",
                "",
                result.config.description,
                "",
                f"- Dataset: `{dataset.label}`",
                f"- Events: {dataset.waveforms.shape[0]}",
                f"- Frame: {dataset.waveforms.shape[1]} channels x {dataset.waveforms.shape[2]} samples",
                f"- Sample period: {dataset.sample_period_ns:g} ns",
                f"- Analysis fraction: {result.config.analysis_fraction:.0%}",
                f"- Authorising: **{result.config.authorising}**",
                f"- Watermark: `{result.config.watermark}`",
                "",
                "### Authorization gates",
                "",
                "```json",
                json.dumps(
                    json_safe(result.summary["authorization_gates"]),
                    indent=2,
                    sort_keys=True,
                    allow_nan=False,
                ),
                "```",
                "",
                "### Plot sequence",
                "",
            ]
        )
        for stem in plot_stems:
            lines.extend([f"#### `{stem}`", "", f"![](plots/{stem}.png)", ""])
        lines.extend(
            [
                "### Pair metrics at the pre-registered fraction",
                "",
                *markdown_table(
                    result.pair_metrics[
                        result.pair_metrics["fraction"] == result.config.analysis_fraction
                    ],
                    [
                        "stave_a",
                        "stave_b",
                        "n",
                        "median_ns",
                        "sigma68_ns",
                        "rms_ns",
                        "core_sigma_ns",
                        "chi2_ndf",
                        "tail_gt2ns",
                    ],
                ),
                "",
                "### Resolution inference gate",
                "",
                "```json",
                json.dumps(
                    json_safe(result.inference),
                    indent=2,
                    sort_keys=True,
                    allow_nan=False,
                ),
                "```",
                "",
            ]
        )
    if comparison_stems:
        lines.extend(["## Correct-frame versus legacy-artifact comparison", ""])
        for stem in comparison_stems:
            lines.extend([f"![](plots/{stem}.png)", ""])
    lines.extend(
        [
            "## How a 0.1 ns core is reached",
            "",
            "The numerical path is:",
            "",
            "```text",
            "raw waveform samples",
            "  -> per-event frame validation",
            "  -> baseline subtraction and signed polarity",
            "  -> explicitly selected pulse component",
            "  -> constant-fraction threshold",
            "  -> linear interpolation between the two bracketing samples",
            "  -> complete event pair",
            "  -> TOF and frozen channel/peak alignment",
            "  -> residual distribution",
            "  -> central sigma68, full RMS, tails, and model-fit diagnostics",
            "```",
            "",
            "In the physical synthetic lane, high signal-to-noise and a locally linear rising edge make the interpolation precise.",
            "In the legacy-artifact lane, fixed pedestal boundaries make the crossing repeatable for the wrong reason.",
            "The log-scale residual, phase/slope dependencies, waveform atlas, and frame comparison are what distinguish these cases.",
            "",
            "## Rule for publication",
            "",
            "A stave resolution is publishable only after frame, pulse identity, held-out stability, covariance model, multi-pair/external-reference inference, and injection/recovery closure all pass.",
            "",
        ]
    )
    (out_dir / "STUDENT_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
