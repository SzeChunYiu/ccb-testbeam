#!/usr/bin/env python3
"""Render the issue #885 seed-averaged calibration diagnostic as compact SVG."""
from __future__ import annotations

import argparse
import html
import json
import math
import sys
from pathlib import Path
from typing import Any

import pandas as pd

TOOL_VERSION = "1.0.0"
PANELS = {
    "pe_sat_readout_vs_KE": {
        "x0": 65,
        "x1": 435,
        "y0": 325,
        "y1": 70,
        "ymax": 140.0,
        "title": "P5: SiPM response vs kinetic energy",
        "ylabel": "SiPM photoelectrons",
    },
    "edep_scint_MeV_vs_KE": {
        "x0": 515,
        "x1": 885,
        "y0": 325,
        "y1": 70,
        "ymax": 12.5,
        "title": "P5b: Birks-visible response vs kinetic energy",
        "ylabel": "Birks-visible energy (MeV)",
    },
}
REQUIRED_POINT_COLUMNS = {
    "particle",
    "metric",
    "energy_MeV",
    "value",
    "uncertainty",
    "n_files",
}
SUPERSCRIPT = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")


class RenderError(ValueError):
    """Raised when a result bundle cannot be rendered safely."""


def x_position(value: float, panel: dict[str, Any]) -> float:
    return panel["x0"] + (value / 20.0) * (panel["x1"] - panel["x0"])


def y_position(value: float, panel: dict[str, Any]) -> float:
    return panel["y0"] - (value / panel["ymax"]) * (panel["y0"] - panel["y1"])


def format_p_value(fit: dict[str, Any]) -> str:
    if fit.get("goodness_of_fit_p_value_underflow"):
        return "p below floating-point range"
    value = float(fit["goodness_of_fit_p_value"])
    if not math.isfinite(value) or value <= 0:
        raise RenderError("nonfinite or nonpositive non-underflow p-value")
    exponent = math.floor(math.log10(value))
    coefficient = value / (10.0**exponent)
    return f"p = {coefficient:.2f}×10{str(exponent).translate(SUPERSCRIPT)}"


def load_inputs(fits_path: Path, points_path: Path) -> tuple[dict[str, Any], pd.DataFrame]:
    fits = json.loads(fits_path.read_text())
    points = pd.read_csv(points_path)
    missing = sorted(REQUIRED_POINT_COLUMNS - set(points.columns))
    if missing:
        raise RenderError("point CSV missing columns: " + ", ".join(missing))
    if points.empty:
        raise RenderError("point CSV is empty")
    for column in ["energy_MeV", "value", "uncertainty", "n_files"]:
        points[column] = pd.to_numeric(points[column], errors="coerce")
    numeric = points[["energy_MeV", "value", "uncertainty", "n_files"]]
    if not numeric.map(math.isfinite).all().all():
        raise RenderError("point CSV contains nonfinite numeric values")
    if (points["uncertainty"] < 0).any():
        raise RenderError("point uncertainty must be nonnegative")
    if fits.get("fits"):
        raise RenderError("this rejection diagnostic expects no accepted calibration fits")
    return fits, points


def render_svg(fits: dict[str, Any], points: pd.DataFrame) -> str:
    width, height = 900, 400
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}" role="img" '
            'aria-labelledby="title desc">'
        ),
        "<title id=\"title\">Issue 885 seed-averaged calibration diagnostics</title>",
        (
            '<desc id="desc">Two panels show partial Geant4 simulation points. '
            "Proton straight-line models are rejected. Deuteron fits are skipped "
            "because only two independent energies exist. This is not detector "
            "data.</desc>"
        ),
        '<rect width="100%" height="100%" fill="white"/>',
        (
            "<style>text{font-family:Arial,sans-serif;fill:#111}"
            ".axis{stroke:#111;stroke-width:1}"
            ".grid{stroke:#bbb;stroke-width:.6;stroke-dasharray:2 3}"
            ".fit{stroke:#111;stroke-width:1.4;stroke-dasharray:7 4;fill:none}"
            ".err{stroke:#111;stroke-width:1}"
            ".proton{fill:white;stroke:#111;stroke-width:1.6}"
            ".deuteron{fill:#111;stroke:#111;stroke-width:1.2}</style>"
        ),
        (
            '<text x="450" y="20" text-anchor="middle" font-size="15" '
            'font-weight="bold">Issue #885 partial Geant4 campaign — '
            "seed-averaged independent energies</text>"
        ),
        (
            '<text x="450" y="39" text-anchor="middle" font-size="12">'
            "Error bars combine propagated within-file SEM and between-seed SEM; "
            "not detector data</text>"
        ),
    ]

    for metric_name, panel in PANELS.items():
        for tick in [0, 5, 10, 15, 20]:
            x = x_position(float(tick), panel)
            lines.extend(
                [
                    (
                        f'<line class="grid" x1="{x:.1f}" y1="{panel["y1"]}" '
                        f'x2="{x:.1f}" y2="{panel["y0"]}"/>'
                    ),
                    (
                        f'<text x="{x:.1f}" y="{panel["y0"] + 18}" '
                        f'text-anchor="middle" font-size="10">{tick}</text>'
                    ),
                ]
            )
        for tick in [
            0.0,
            panel["ymax"] / 4.0,
            panel["ymax"] / 2.0,
            3.0 * panel["ymax"] / 4.0,
            panel["ymax"],
        ]:
            y = y_position(tick, panel)
            lines.extend(
                [
                    (
                        f'<line class="grid" x1="{panel["x0"]}" y1="{y:.1f}" '
                        f'x2="{panel["x1"]}" y2="{y:.1f}"/>'
                    ),
                    (
                        f'<text x="{panel["x0"] - 8}" y="{y + 3:.1f}" '
                        f'text-anchor="end" font-size="10">{tick:g}</text>'
                    ),
                ]
            )

        midpoint = (panel["x0"] + panel["x1"]) / 2.0
        vertical_midpoint = (panel["y0"] + panel["y1"]) / 2.0
        lines.extend(
            [
                (
                    f'<line class="axis" x1="{panel["x0"]}" y1="{panel["y0"]}" '
                    f'x2="{panel["x1"]}" y2="{panel["y0"]}"/>'
                ),
                (
                    f'<line class="axis" x1="{panel["x0"]}" y1="{panel["y0"]}" '
                    f'x2="{panel["x0"]}" y2="{panel["y1"]}"/>'
                ),
                (
                    f'<text x="{midpoint:.1f}" y="365" text-anchor="middle" '
                    'font-size="11">kinetic energy (MeV)</text>'
                ),
                (
                    f'<text x="{panel["x0"] - 48}" y="{vertical_midpoint:.1f}" '
                    f'transform="rotate(-90 {panel["x0"] - 48} '
                    f'{vertical_midpoint:.1f})" text-anchor="middle" '
                    f'font-size="11">{html.escape(panel["ylabel"])}</text>'
                ),
                (
                    f'<text x="{midpoint:.1f}" y="61" text-anchor="middle" '
                    f'font-size="12" font-weight="bold">'
                    f'{html.escape(panel["title"])}</text>'
                ),
            ]
        )

        fit_name = f"{metric_name}_proton"
        fit = fits.get("fit_rejections", {}).get(fit_name)
        if not fit or fit.get("fit_status") != "LINEAR_MODEL_REJECTED":
            raise RenderError(f"missing rejected proton diagnostic {fit_name}")
        x_low = float(fit["energy_min_MeV"])
        x_high = float(fit["energy_max_MeV"])
        y_low = float(fit["slope"]) * x_low + float(fit["intercept"])
        y_high = float(fit["slope"]) * x_high + float(fit["intercept"])
        lines.append(
            (
                f'<path class="fit" d="M {x_position(x_low, panel):.1f} '
                f'{y_position(y_low, panel):.1f} L '
                f'{x_position(x_high, panel):.1f} '
                f'{y_position(y_high, panel):.1f}"/>'
            )
        )

        subset = points[points["metric"] == metric_name]
        for row in subset.itertuples(index=False):
            x = x_position(float(row.energy_MeV), panel)
            y = y_position(float(row.value), panel)
            error = abs(y_position(float(row.value + row.uncertainty), panel) - y)
            lines.append(
                (
                    f'<line class="err" x1="{x:.1f}" y1="{y - error:.1f}" '
                    f'x2="{x:.1f}" y2="{y + error:.1f}"/>'
                )
            )
            if row.particle == "proton":
                lines.append(
                    f'<circle class="proton" cx="{x:.1f}" cy="{y:.1f}" r="4"/>'
                )
            elif row.particle == "deuteron":
                lines.append(
                    (
                        f'<rect class="deuteron" x="{x - 4:.1f}" '
                        f'y="{y - 4:.1f}" width="8" height="8"/>'
                    )
                )
            else:
                raise RenderError(f"unsupported particle {row.particle!r}")

        deuteron_name = f"{metric_name}_deuteron"
        skip = fits.get("fit_skips", {}).get(deuteron_name)
        if not skip or skip.get("status") != "SKIPPED_INSUFFICIENT_ENERGY_POINTS":
            raise RenderError(f"missing deuteron coverage skip {deuteron_name}")
        p_value_text = format_p_value(fit)
        lines.extend(
            [
                (
                    f'<text x="{panel["x0"] + 9}" y="{panel["y1"] + 18}" '
                    'font-size="10">○ proton seed-averaged points</text>'
                ),
                (
                    f'<text x="{panel["x0"] + 9}" y="{panel["y1"] + 34}" '
                    'font-size="10">■ deuteron seed-averaged points</text>'
                ),
                (
                    f'<text x="{panel["x0"] + 9}" y="{panel["y1"] + 50}" '
                    'font-size="10">-- proton linear diagnostic rejected '
                    f'({html.escape(p_value_text)})</text>'
                ),
                (
                    f'<text x="{panel["x0"] + 9}" y="{panel["y1"] + 66}" '
                    'font-size="10">deuteron fit skipped: '
                    f'{skip["n_energy_points"]} &lt; '
                    f'{skip["minimum_energy_points"]} energies</text>'
                ),
            ]
        )

    lines.extend(
        [
            (
                '<text x="450" y="391" text-anchor="middle" font-size="10">'
                f'Source: i885_per_config.csv, {fits["n_configs"]} files / '
                f'{fits["n_events_total"]:,} simulated events. '
                "No accepted calibration function.</text>"
            ),
            "</svg>",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fits", required=True, type=Path)
    parser.add_argument("--points", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        fits, points = load_inputs(args.fits, args.points)
        svg = render_svg(fits, points)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(svg)
    except (OSError, json.JSONDecodeError, RenderError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {args.output} with {len(points)} seed-averaged metric points")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
