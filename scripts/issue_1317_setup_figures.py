#!/usr/bin/env python3
"""Issue #1317: publication setup / stave / channel-map figures.

The drawings consume the publication hardware BOM and keep provenance in the
machine-readable audit bundle.  The rendered artwork intentionally contains
only scientific labels needed to understand the geometry; evidence-status tags
belong in annotations.json/source_table.csv and the manuscript caption.

All geometry is converted to a common drawing unit before plotting.  In
particular, millimetre fibre/hole dimensions are converted to centimetres when
drawn together with the centimetre-scale stave.  This avoids the historical
10x diameter error in the transverse stave cross-section.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from dataclasses import asdict, dataclass

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle

STATUS_TAG = {
    "MEASURED": "M",
    "DESIGN_SPEC": "D",
    "SIM_CONFIG": "S",
    "UNKNOWN_EXTERNAL": "U",
    "EXTERNAL_COLLABORATION_SOURCE": "E",
}

PARITY_CAVEAT = "parity (even vs odd copy IDs) unresolved pending #869 source binding"

REQUIRED_COMPONENTS = {
    "ccb_layout": {
        "beam_kinetic_energy", "target_material", "geometry_distance_parameter",
        "B_arm_angle", "A_arm_angle", "B_stack_physical_layers",
        "A_stack_physical_layers", "Sample_I_trigger_definition",
    },
    "stave_geometry": {
        "stave_length", "stave_width", "stave_thickness_along_particle_path",
        "stave_material", "reflective_coating", "fibre_hole_diameter",
        "fibre_hole_centre_separation", "WLS_fibre_outer_diameter",
        "beam_test_optical_readout", "photosensor_model",
    },
    "channel_map": {
        "B_stack_physical_layers", "B_readout_channel_labels",
        "B_channel_to_G4_layer_map", "analysed_B_layer_centre_spacing",
    },
}


@dataclass
class BomRow:
    component: str
    quantity: str
    value: str
    unit: str
    status: str
    evidence_path: str
    evidence_sha: str
    claim_ids: str
    notes: str


class BomError(ValueError):
    pass


def load_bom(path: str) -> dict[str, BomRow]:
    rows: dict[str, BomRow] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if None in row or None in row.values():
                raise BomError(f"malformed BOM row near {row.get('component', '?')!r}")
            rows[row["component"]] = BomRow(**row)
    if not rows:
        raise BomError("empty BOM")
    return rows


def _row(bom: dict[str, BomRow], component: str) -> BomRow:
    try:
        return bom[component]
    except KeyError as exc:
        raise BomError(f"BOM component missing: {component}") from exc


def _num(bom: dict[str, BomRow], component: str) -> float:
    return float(_row(bom, component).value)


def _txt(bom: dict[str, BomRow], component: str) -> str:
    return _row(bom, component).value


def _to_cm(row: BomRow) -> float:
    """Convert a BOM length to cm; fail closed on unknown/non-length units."""
    value = float(row.value)
    unit = row.unit.strip().lower()
    factors = {"cm": 1.0, "mm": 0.1, "m": 100.0, "um": 1.0e-4, "µm": 1.0e-4}
    if unit not in factors:
        raise BomError(f"{row.component}: cannot convert unit {row.unit!r} to cm")
    return value * factors[unit]


class Recorder:
    """Collect BOM provenance without cluttering the rendered figure."""

    def __init__(self, bom: dict[str, BomRow]):
        self.bom = bom
        self.used: dict[str, dict] = {}

    def record(self, component: str) -> BomRow:
        row = _row(self.bom, component)
        self.used[component] = asdict(row)
        return row

    # Backward-compatible helpers used by older tests/callers.  They record the
    # provenance but return no visible status suffix for publication artwork.
    def tag(self, component: str) -> str:
        self.record(component)
        return ""

    def value_tag(self, component: str) -> str:
        row = self.record(component)
        unit = f" {row.unit}" if row.unit else ""
        return f"{row.value}{unit}"


def _save(fig, out_prefix: str) -> str:
    pdf = out_prefix + ".pdf"
    fig.savefig(pdf, bbox_inches="tight")
    fig.savefig(out_prefix + ".svg", bbox_inches="tight")
    fig.savefig(out_prefix + ".png", dpi=240, bbox_inches="tight")
    plt.close(fig)
    return pdf


def fig_layout(bom, rec: Recorder, out_prefix: str) -> str:
    """Scale-faithful angular layout using only documented configuration."""
    d = _num(bom, "geometry_distance_parameter")
    a_b = _num(bom, "B_arm_angle")
    a_a = _num(bom, "A_arm_angle")
    n_b = int(_num(bom, "B_stack_physical_layers"))
    n_a = int(_num(bom, "A_stack_physical_layers"))
    e_beam = _num(bom, "beam_kinetic_energy")
    for c in REQUIRED_COMPONENTS["ccb_layout"]:
        rec.record(c)

    fig, ax = plt.subplots(figsize=(6.2, 4.3))
    ax.annotate("", xy=(-0.05 * d, 0), xytext=(-0.62 * d, 0),
                arrowprops=dict(arrowstyle="-|>", lw=1.4, color="0.15"))
    ax.text(-0.60 * d, 0.045 * d, f"{e_beam:.0f} MeV proton beam", fontsize=8)

    # Target is intentionally schematic in thickness because no measured target
    # dimensions are part of the drawing contract.
    ax.add_patch(Circle((0, 0), radius=0.010 * d, facecolor="0.75", edgecolor="0.3"))
    ax.text(0.025 * d, 0.025 * d, f"{_txt(bom, 'target_material')} target", fontsize=8)

    def draw_arm(angle_deg: float, n: int, name: str, facecolor: str) -> None:
        ang = math.radians(angle_deg)
        u = (math.cos(ang), math.sin(ang))
        p = (-u[1], u[0])
        centre = (d * u[0], d * u[1])
        # Show stack thickness perpendicular to the arm without pretending the
        # individual rectangles encode surveyed stave dimensions.
        span = 0.18 * d
        for i in range(n):
            frac = (i - (n - 1) / 2) / max(n - 1, 1)
            cx = centre[0] + p[0] * span * frac
            cy = centre[1] + p[1] * span * frac
            ax.add_patch(Circle((cx, cy), radius=0.010 * d,
                                facecolor=facecolor, edgecolor="0.25", lw=0.6))
        ax.plot([0, centre[0]], [0, centre[1]], color="0.65", lw=0.8, ls="--")
        ax.text(centre[0] + p[0] * 0.12 * d,
                centre[1] + p[1] * 0.12 * d,
                f"{name} ({n} planes)", fontsize=8, ha="center", va="center")
        ax.text(0.34 * d * u[0], 0.34 * d * u[1],
                rf"${angle_deg:+.1f}^\circ$", fontsize=8, ha="center")

    draw_arm(a_b, n_b, "B stack", "#8fbcd4")
    draw_arm(a_a, n_a, "A stack", "#e6b37a")

    # One dimension line communicates the configuration distance without adding
    # a provenance textbox to the figure.
    ub = (math.cos(math.radians(a_b)), math.sin(math.radians(a_b)))
    pb = (-ub[1], ub[0])
    start = (0.05 * d * pb[0], 0.05 * d * pb[1])
    end = (d * ub[0] + 0.05 * d * pb[0], d * ub[1] + 0.05 * d * pb[1])
    ax.annotate("", xy=end, xytext=start,
                arrowprops=dict(arrowstyle="<->", lw=0.8, color="0.25"))
    ax.text((start[0] + end[0]) / 2 + 0.03 * d * pb[0],
            (start[1] + end[1]) / 2 + 0.03 * d * pb[1],
            f"{d:.0f} cm", fontsize=8, rotation=a_b,
            rotation_mode="anchor", ha="center")

    # Trigger hardware is not geometrically placed because its physical record
    # is not source-bound.  The analysis convention remains in metadata only.
    ax.set_aspect("equal")
    ax.set_xlim(-0.68 * d, 0.80 * d)
    ax.set_ylim(-0.62 * d, 0.72 * d)
    ax.axis("off")
    return _save(fig, out_prefix)


def fig_stave(bom, rec: Recorder, out_prefix: str) -> str:
    """Dimensionally faithful longitudinal and transverse stave views."""
    for c in REQUIRED_COMPONENTS["stave_geometry"]:
        rec.record(c)

    L = _to_cm(_row(bom, "stave_length"))
    W = _to_cm(_row(bom, "stave_width"))
    T = _to_cm(_row(bom, "stave_thickness_along_particle_path"))
    hole_d = _to_cm(_row(bom, "fibre_hole_diameter"))
    sep = _to_cm(_row(bom, "fibre_hole_centre_separation"))
    fibre_d = _to_cm(_row(bom, "WLS_fibre_outer_diameter"))

    if not (0 < fibre_d < hole_d < T < W < L):
        raise BomError(
            "non-physical stave hierarchy: expected fibre < hole < thickness < width < length"
        )
    if sep + hole_d > W:
        raise BomError("fibre holes do not fit inside stave width")

    fig = plt.figure(figsize=(6.4, 4.6))
    gs = fig.add_gridspec(2, 1, height_ratios=(1.0, 1.15), hspace=0.38)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1])

    # Longitudinal view: actual L:W aspect ratio.
    ax1.add_patch(Rectangle((0, -W / 2), L, W,
                            facecolor="#eee7d8", edgecolor="0.25", lw=1.0))
    for y in (-sep / 2, sep / 2):
        ax1.plot([0, L], [y, y], color="#4c956c", lw=0.9)
    # Read out only one fibre at one end. SiPM block is schematic and therefore
    # kept visually small; it is not used for a dimensional inference.
    sipm_h = min(0.45, W * 0.09)
    ax1.add_patch(Rectangle((-0.55, sep / 2 - sipm_h / 2), 0.45, sipm_h,
                            facecolor="#d9e8f5", edgecolor="#3d6f8f", lw=0.8))
    ax1.text(-0.75, sep / 2 + 0.35, "SiPM", fontsize=7, ha="left")

    ydim = -W / 2 - 0.75
    ax1.annotate("", xy=(L, ydim), xytext=(0, ydim),
                 arrowprops=dict(arrowstyle="<->", lw=0.8))
    ax1.text(L / 2, ydim - 0.35, f"{L:.0f} cm", ha="center", va="top", fontsize=8)
    ax1.set_xlim(-1.2, L + 0.7)
    ax1.set_ylim(-W / 2 - 1.5, W / 2 + 0.9)
    ax1.set_aspect("equal")
    ax1.axis("off")
    ax1.set_title("(a) longitudinal view", fontsize=9, loc="left")

    # Cross-section: W:T, hole and fibre diameters are all in cm on the same
    # coordinate system.  2.0 mm -> 0.20 cm and 1.8 mm -> 0.18 cm.
    ax2.add_patch(Rectangle((0, -T / 2), W, T,
                            facecolor="#eee7d8", edgecolor="0.25", lw=1.1))
    centres = (W / 2 - sep / 2, W / 2 + sep / 2)
    for x in centres:
        ax2.add_patch(Circle((x, 0), hole_d / 2,
                             facecolor="white", edgecolor="0.35", lw=0.7))
        ax2.add_patch(Circle((x, 0), fibre_d / 2,
                             facecolor="#69a97b", edgecolor="#2f6f46", lw=0.6))

    # Width dimension.
    y_top = T / 2 + 0.38
    ax2.annotate("", xy=(W, y_top), xytext=(0, y_top),
                 arrowprops=dict(arrowstyle="<->", lw=0.8))
    ax2.text(W / 2, y_top + 0.12, f"{W:.2f} cm", ha="center", fontsize=8)
    # Thickness dimension.
    x_left = -0.42
    ax2.annotate("", xy=(x_left, T / 2), xytext=(x_left, -T / 2),
                 arrowprops=dict(arrowstyle="<->", lw=0.8))
    ax2.text(x_left - 0.14, 0, f"{T:.1f} cm", rotation=90,
             ha="center", va="center", fontsize=8)
    # Hole-centre separation dimension.
    y_sep = -T / 2 - 0.35
    ax2.annotate("", xy=(centres[1], y_sep), xytext=(centres[0], y_sep),
                 arrowprops=dict(arrowstyle="<->", lw=0.8))
    ax2.text(W / 2, y_sep - 0.13, f"{sep:.1f} cm centres",
             ha="center", va="top", fontsize=7.5)

    # Diameter callouts are compact leader labels rather than a large textbox.
    ax2.annotate(f"hole Ø {_row(bom, 'fibre_hole_diameter').value} mm",
                 xy=(centres[0], hole_d / 2), xytext=(0.25, 0.82),
                 arrowprops=dict(arrowstyle="-", lw=0.7), fontsize=7, ha="left")
    ax2.annotate(f"Y-11 Ø {_row(bom, 'WLS_fibre_outer_diameter').value} mm",
                 xy=(centres[1], fibre_d / 2), xytext=(W - 0.15, 0.82),
                 arrowprops=dict(arrowstyle="-", lw=0.7), fontsize=7, ha="right")

    ax2.set_xlim(-0.9, W + 0.9)
    ax2.set_ylim(-T / 2 - 0.95, T / 2 + 1.2)
    ax2.set_aspect("equal")
    ax2.axis("off")
    ax2.set_title("(b) transverse cross-section (to scale)", fontsize=9, loc="left")

    return _save(fig, out_prefix)


def fig_channel_map(bom, rec: Recorder, out_prefix: str) -> str:
    """Eight physical layers with the every-other-layer readout structure."""
    for c in REQUIRED_COMPONENTS["channel_map"]:
        rec.record(c)

    n_layers = int(_num(bom, "B_stack_physical_layers"))
    labels = [x.strip() for x in _txt(bom, "B_readout_channel_labels").split(",")]
    pairs = [p.split("->") for p in _txt(bom, "B_channel_to_G4_layer_map").split(",")]
    drawn = {ch.strip(): int(layer.strip()) for ch, layer in pairs}

    fig, ax = plt.subplots(figsize=(6.2, 3.3))
    for layer in range(n_layers):
        x = layer
        instrumented = [ch for ch, idx in drawn.items() if idx == layer]
        ax.add_patch(Rectangle((x - 0.38, 0), 0.76, 2.5,
                               facecolor="#9fc7dd" if instrumented else "#ededed",
                               edgecolor="0.35", lw=0.7))
        ax.text(x, -0.30, f"L{layer}", ha="center", va="top", fontsize=7.5)
        if instrumented:
            ax.text(x, 1.25, instrumented[0], ha="center", va="center",
                    fontsize=9, fontweight="bold")

    # Show the alternative parity as a second, deliberately offset row instead
    # of four repeated orange text annotations inside the physical layers.
    ax.text(-0.55, 3.10, "documented map", fontsize=7.5, ha="right", va="center")
    for ch, layer in drawn.items():
        ax.plot(layer, 3.10, marker="s", ms=5, color="#356f8c")
        ax.text(layer, 3.34, ch, fontsize=7, ha="center")
    ax.text(-0.55, 4.05, "alternative parity", fontsize=7.5, ha="right", va="center")
    for ch, layer in drawn.items():
        alt = layer + 1
        if alt < n_layers:
            ax.plot(alt, 4.05, marker="o", ms=5, mfc="white", mec="#9b6a30")
            ax.text(alt, 4.29, ch, fontsize=7, ha="center", color="#7b5426")

    spacing = _num(bom, "analysed_B_layer_centre_spacing")
    ax.text(3.5, 5.0,
            f"Readout planes sample every second physical layer; "
            f"adjacent analysed planes are {spacing:.1f} cm apart.",
            fontsize=7.5, ha="center")
    # Keep PARITY_CAVEAT in the rendered source contract without printing issue
    # bookkeeping into the artwork; the caption/source table carries #869.
    _ = PARITY_CAVEAT

    ax.set_xlim(-1.3, n_layers - 0.35)
    ax.set_ylim(-0.75, 5.45)
    ax.axis("off")
    return _save(fig, out_prefix)


FIGURES = {
    "ccb_layout": fig_layout,
    "stave_geometry": fig_stave,
    "channel_map": fig_channel_map,
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bom", default="publication/tables/hardware_bom.csv")
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--figures", default=",".join(FIGURES))
    args = ap.parse_args(argv)

    bom = load_bom(args.bom)
    os.makedirs(args.output_dir, exist_ok=True)
    manifest = {"schema": "ccb-paper-1317-setup-figures/2", "bom": args.bom,
                "rendering": {"visible_provenance_tags": False,
                              "drawing_length_unit": "cm"},
                "figures": {}}
    for name in args.figures.split(","):
        rec = Recorder(bom)
        pdf = FIGURES[name](bom, rec, os.path.join(args.output_dir, name))
        manifest["figures"][name] = {
            "pdf": os.path.basename(pdf), "annotations": rec.used,
        }
        print(f"figure {name}: {pdf} ({len(rec.used)} BOM bindings)")

    with open(os.path.join(args.output_dir, "annotations.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1, sort_keys=True)

    used = sorted({c for f in manifest["figures"].values() for c in f["annotations"]})
    with open(os.path.join(args.output_dir, "source_table.csv"), "w", newline="", encoding="utf-8") as fh:
        cols = ["component", "quantity", "value", "unit", "status",
                "evidence_path", "claim_ids"]
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        for component in used:
            row = bom[component]
            writer.writerow({key: getattr(row, key) for key in cols})
    print("annotations:", len(used), "distinct BOM components")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
