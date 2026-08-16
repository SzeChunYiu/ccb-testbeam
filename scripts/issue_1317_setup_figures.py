#!/usr/bin/env python3
"""Issue #1317: authorising setup / stave / channel-map figures.

Every annotated value is read from the publication hardware BOM
(publication/tables/hardware_bom.csv) -- the single source of truth bound
by #1296. No dimension is hard-coded in this producer; the companion test
(tests/test_issue_1317_setup_figures.py) asserts that every annotation
component exists in the BOM, that drawn values match the BOM values, and
that the #869 parity alternative is annotated, never silently chosen.

Outputs (per figure): vector PDF + SVG + PNG preview, plus a bundle-level
annotations.json (component -> BOM row per annotation) and source_table.csv.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from dataclasses import dataclass, asdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle

# Evidence-status styling: how each annotation is tagged on the figures.
STATUS_TAG = {
    "MEASURED": "M",
    "DESIGN_SPEC": "D",
    "SIM_CONFIG": "S",
    "UNKNOWN_EXTERNAL": "U",
}
STATUS_LEGEND = (
    "M = MEASURED, D = DESIGN_SPEC, S = SIM_CONFIG, U = UNKNOWN_EXTERNAL\n"
    "(publication hardware BOM, issue #1296)"
)


class BomError(ValueError):
    pass


# The #869 even/odd LayerID parity nuisance: the drawn channel map uses the
# documented detector-map contract and MUST annotate this alternative rather
# than silently choosing one. Kept as a constant so the companion test can
# assert the caveat is rendered, not dropped.
PARITY_CAVEAT = (
    "parity (even vs odd copy IDs) unresolved pending #869 source binding"
)

# Minimum BOM components each figure must draw from (checked by the test).
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


def load_bom(path: str) -> dict[str, BomRow]:
    rows: dict[str, BomRow] = {}
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            if None in r or None in r.values():
                bad = r.get("component") or next(iter(r.values()), "?")
                raise BomError(
                    f"malformed BOM row (field-count mismatch vs header) "
                    f"near component {bad!r} in {path}")
            rows[r["component"]] = BomRow(**r)
    if not rows:
        raise BomError("empty BOM")
    return rows


def _num(bom: dict[str, BomRow], component: str) -> float:
    if component not in bom:
        raise BomError(f"BOM component missing: {component}")
    return float(bom[component].value)


def _txt(bom: dict[str, BomRow], component: str) -> str:
    if component not in bom:
        raise BomError(f"BOM component missing: {component}")
    return bom[component].value


class Recorder:
    """Collects annotations for the machine-readable audit table."""

    def __init__(self, bom: dict[str, BomRow]):
        self.bom = bom
        self.used: dict[str, dict] = {}

    def tag(self, component: str) -> str:
        row = self.bom[component]
        self.used[component] = asdict(row)
        return f" [{STATUS_TAG[row.status]}]"

    def value_tag(self, component: str) -> str:
        row = self.bom[component]
        self.used[component] = asdict(row)
        unit = f" {row.unit}" if row.unit else ""
        return f"{row.value}{unit}{self.tag(component)}"


def fig_layout(bom, rec: Recorder, out_prefix: str) -> str:
    """Two-arm test-beam layout; only BOM-traceable quantities annotated."""
    d = _num(bom, "geometry_distance_parameter")
    a_b = _num(bom, "B_arm_angle")
    a_a = _num(bom, "A_arm_angle")
    n_b = int(_num(bom, "B_stack_physical_layers"))
    n_a = int(_num(bom, "A_stack_physical_layers"))
    e_beam = _num(bom, "beam_kinetic_energy")

    fig, ax = plt.subplots(figsize=(5.6, 3.9))
    # beam axis
    ax.annotate(
        "", xy=(-0.30 * d, 0), xytext=(-0.62 * d, 0),
        arrowprops=dict(arrowstyle="-|>", lw=1.4, color="#333333"),
    )
    ax.text(-0.60 * d, 0.05 * d, f"protons {e_beam:.0f} MeV" + rec.tag("beam_kinetic_energy"),
            fontsize=7, ha="left")
    # target
    ax.add_patch(Rectangle((-0.004 * d, -0.012 * d), 0.008 * d, 0.024 * d,
                           fc="#c8c8c8", ec="#666666"))
    ax.text(0.012 * d, 0.10 * d,
            _txt(bom, "target_material").replace("_", " ") + " target"
            + rec.tag("target_material"), fontsize=7)
    ax.plot([0], [0], "k.", ms=3)

    def draw_arm(angle_deg: float, n: int, label: str, comp: str, fc: str):
        ang = math.radians(angle_deg)
        ux, uy = math.cos(ang), math.sin(ang)
        # perpendicular spread of bars
        px, py = -uy, ux
        for i in range(n):
            off = (i - (n - 1) / 2) * 0.035 * d
            cx, cy = d * ux + px * off, d * uy + py * off
            ax.add_patch(Rectangle((cx - 0.012 * d, cy - 0.006 * d),
                                   0.024 * d, 0.012 * d,
                                   angle=angle_deg, rotation_point="xy",
                                   fc=fc, ec="#444444", lw=0.5))
        ax.plot([0, d * ux], [0, d * uy], color="#bbbbbb", lw=0.6, ls=":")
        ax.text(d * ux * 1.06 + px * 0.06 * d, d * uy * 1.06 + py * 0.06 * d,
                f"{label}: {n} bars" + rec.tag(comp), fontsize=7,
                ha="center", va="center")
        # angle arc from beam axis
        ax.annotate("", xy=(0.30 * d * ux, 0.30 * d * uy), xytext=(0.30 * d, 0),
                    arrowprops=dict(arrowstyle="-", lw=0.7, color="#888888",
                                    connectionstyle="arc3,rad=0.12"))
        ax.text(0.36 * d * ux + 0.06 * d, 0.36 * d * uy,
                f"{angle_deg:+.1f}$^\\circ$" + rec.tag(
                    "B_arm_angle" if label.startswith("B") else "A_arm_angle"),
                fontsize=7)

    draw_arm(a_b, n_b, "B stack", "B_stack_physical_layers", "#9ecae1")
    draw_arm(a_a, n_a, "A stack", "A_stack_physical_layers", "#fdd0a2")
    ax.text(0.5 * d * math.cos(math.radians(a_b)) - 0.02 * d,
            0.5 * d * math.sin(math.radians(a_b)) - 0.07 * d,
            f"r = {d:.0f} cm" + rec.tag("geometry_distance_parameter"),
            fontsize=7, rotation=a_b, rotation_mode="anchor")

    # trigger counters: drawn schematically, hardware record explicitly unbound
    for xt in (-0.17 * d, -0.09 * d):
        ax.add_patch(Rectangle((xt - 0.012 * d, -0.012 * d), 0.024 * d, 0.024 * d,
                               fc="#f2c88a", ec="#8a6100", lw=0.6, ls="--"))
    ax.text(-0.13 * d, -0.062 * d, "trigger counters", fontsize=6.5,
            ha="center", color="#7a4a00")
    ax.text(0.0, -0.27 * d,
            "trigger counters drawn schematically; thresholds/coincidence "
            "hardware record unbound", fontsize=6.5, ha="center", color="#7a4a00")
    ax.text(0.0, -0.335 * d,
            "(analysis convention: "
            + bom["Sample_I_trigger_definition"].value.replace("_", " ")
            + ")" + rec.tag("Sample_I_trigger_definition"),
            fontsize=6.5, ha="center", color="#7a4a00")
    ax.text(0.0, -0.44 * d, STATUS_LEGEND, fontsize=6, ha="center", color="#555555")
    ax.set_xlim(-0.68 * d, 0.75 * d)
    ax.set_ylim(-0.52 * d, 0.55 * d)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()
    pdf = out_prefix + ".pdf"
    fig.savefig(pdf)
    fig.savefig(out_prefix + ".svg")
    fig.savefig(out_prefix + ".png", dpi=200)
    plt.close(fig)
    return pdf


def fig_stave(bom, rec: Recorder, out_prefix: str) -> str:
    """Longitudinal view + transverse cross-section of one B stave."""
    L = _num(bom, "stave_length")
    W = _num(bom, "stave_width")
    T = _num(bom, "stave_thickness_along_particle_path")
    hole_d = _num(bom, "fibre_hole_diameter")
    sep = _num(bom, "fibre_hole_centre_separation")
    fibre_d = _num(bom, "WLS_fibre_outer_diameter")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(5.6, 4.2),
                                   gridspec_kw=dict(height_ratios=[1.25, 1]))

    # --- longitudinal view (units cm) ---
    ax1.add_patch(Rectangle((0, -W / 2), L, W, fc="#efe7d8", ec="#8a7f66", lw=1.0))
    # coating as thick outline is represented by edge; annotate
    for y in (-sep / 2, sep / 2):
        ax1.plot([0.05 * L, 0.95 * L], [y, y], color="#31a354", lw=1.1)
        ax1.add_patch(Circle((0.05 * L, y), hole_d / 2, fc="white", ec="#666666", lw=0.6))
        ax1.add_patch(Circle((0.05 * L, y), fibre_d / 2, fc="#74c476", ec="#238b45", lw=0.5))
    # SiPM at ONE fibre end (one-fibre-one-end)
    ax1.add_patch(Rectangle((-0.022 * L, sep / 2 - 0.35), 0.02 * L, 0.7,
                            fc="#deebf7", ec="#3182bd"))
    ax1.text(-0.022 * L, sep / 2 + 0.9,
             "SiPM " + _txt(bom, "photosensor_model").replace("_", " ")
             + rec.tag("photosensor_model"), fontsize=6.5, ha="left")
    ax1.text(-0.022 * L, sep / 2 - 1.8,
             "one fibre, one end" + rec.tag("beam_test_optical_readout"),
             fontsize=6.5, ha="left")
    ax1.annotate("", xy=(L, -W / 2 - 0.7), xytext=(0, -W / 2 - 0.7),
                 arrowprops=dict(arrowstyle="<->", lw=0.7))
    ax1.text(L / 2, -W / 2 - 1.5,
             f"{L:.0f} cm" + rec.tag("stave_length"), fontsize=7, ha="center")
    ax1.text(L / 2, W / 2 + 0.6,
             _txt(bom, "stave_material").replace("_", " ")
             + rec.tag("stave_material")
             + ", " + _txt(bom, "reflective_coating").replace("_", " ")
             + rec.tag("reflective_coating"), fontsize=6.5, ha="center")
    ax1.set_xlim(-0.12 * L, 1.06 * L)
    ax1.set_ylim(-W, W + 1.2)
    ax1.set_aspect("equal")
    ax1.axis("off")
    ax1.set_title("(a) longitudinal view", fontsize=8, loc="left")

    # --- transverse cross-section (units cm) ---
    ax2.add_patch(Rectangle((0, -T / 2), W, T, fc="#efe7d8", ec="#8a7f66", lw=1.6))
    cx = (W / 2 - sep / 2, W / 2 + sep / 2)
    for x in cx:
        ax2.add_patch(Circle((x, 0), hole_d / 2, fc="white", ec="#666666", lw=0.8))
        ax2.add_patch(Circle((x, 0), fibre_d / 2, fc="#74c476", ec="#238b45", lw=0.7))
    ax2.annotate("", xy=(W, T / 2 + 0.45), xytext=(0, T / 2 + 0.45),
                 arrowprops=dict(arrowstyle="<->", lw=0.7))
    ax2.text(W / 2, T / 2 + 0.62, f"{W:.2f} cm" + rec.tag("stave_width"),
             fontsize=7, ha="center")
    ax2.annotate("", xy=(-0.55, T / 2), xytext=(-0.55, -T / 2),
                 arrowprops=dict(arrowstyle="<->", lw=0.7))
    ax2.text(-0.75, 0, f"{T:.1f} cm" + rec.tag("stave_thickness_along_particle_path"),
             fontsize=7, ha="right", va="center", rotation=90)
    ax2.annotate("", xy=(cx[1], -T / 2 - 0.45), xytext=(cx[0], -T / 2 - 0.45),
                 arrowprops=dict(arrowstyle="<->", lw=0.7))
    ax2.text(W / 2, -T / 2 - 0.95,
             f"hole centres {sep:.1f} cm" + rec.tag("fibre_hole_centre_separation")
             + f"; holes $\\varnothing$ {hole_d:.1f} mm" + rec.tag("fibre_hole_diameter")
             + f"; WLS fibres $\\varnothing$ {fibre_d:.1f} mm" + rec.tag("WLS_fibre_outer_diameter"),
             fontsize=6.5, ha="center")
    ax2.text(W / 2, -T / 2 - 1.8, STATUS_LEGEND, fontsize=6, ha="center", color="#555555")
    ax2.set_xlim(-2.6, W + 1.2)
    ax2.set_ylim(-T - 2.2, T + 1.3)
    ax2.set_aspect("equal")
    ax2.axis("off")
    ax2.set_title("(b) transverse cross-section", fontsize=8, loc="left")

    fig.tight_layout()
    pdf = out_prefix + ".pdf"
    fig.savefig(pdf)
    fig.savefig(out_prefix + ".svg")
    fig.savefig(out_prefix + ".png", dpi=200)
    plt.close(fig)
    return pdf


def fig_channel_map(bom, rec: Recorder, out_prefix: str) -> str:
    """Eight physical B layers; four instrumented even-position channels.

    The drawn mapping is the documented detector-map contract
    (B2->0, B4->2, B6->4, B8->6, SIM_CONFIG). The #869 odd-layer
    alternative is annotated as an unresolved parity nuisance, never
    silently chosen. Only the every-other-layer structure is drawn as
    robust.
    """
    n_layers = int(_num(bom, "B_stack_physical_layers"))
    labels = _txt(bom, "B_readout_channel_labels").split(",")
    pairs = [p.split("->") for p in _txt(bom, "B_channel_to_G4_layer_map").split(",")]
    drawn = {ch: int(lay) for ch, lay in pairs}

    fig, ax = plt.subplots(figsize=(5.6, 3.2))
    for i in range(n_layers):
        y = i
        inst = [ch for ch, lay in drawn.items() if lay == i]
        fc = "#9ecae1" if inst else "#e8e8e8"
        ax.add_patch(Rectangle((0, y - 0.32), 6.0, 0.64, fc=fc, ec="#555555", lw=0.6))
        ax.text(6.15, y, f"physical layer {i}", fontsize=7, va="center")
        if inst:
            ax.text(3.0, y, inst[0], fontsize=8, ha="center", va="center",
                    fontweight="bold")
            # odd-parity alternative (#869) as open annotation
            ax.text(3.0, y - 0.47, f"alt: layer {i+1} (#869, unbound)",
                    fontsize=5.5, ha="center", va="center", color="#b35808")
        else:
            ax.text(3.0, y, "not instrumented", fontsize=6, ha="center",
                    va="center", color="#777777")
    ax.text(0.0, n_layers - 0.1,
            f"{n_layers} physical B layers"
            + rec.tag("B_stack_physical_layers")
            + "; instrumented readout channels: "
            + ", ".join(labels) + rec.tag("B_readout_channel_labels"),
            fontsize=7)
    ax.text(0.0, n_layers + 0.45,
            "drawn map " + _txt(bom, "B_channel_to_G4_layer_map")
            + rec.tag("B_channel_to_G4_layer_map")
            + "; " + PARITY_CAVEAT,
            fontsize=6.5, color="#b35808")
    ax.text(0.0, n_layers + 0.95,
            f"adjacent instrumented-layer centre spacing "
            f"{_num(bom, 'analysed_B_layer_centre_spacing'):.1f} cm"
            + rec.tag("analysed_B_layer_centre_spacing"),
            fontsize=6.5)
    ax.text(0.0, n_layers + 1.45, STATUS_LEGEND, fontsize=6, color="#555555")
    ax.set_xlim(-0.3, 9.2)
    ax.set_ylim(-0.9, n_layers + 1.9)
    ax.axis("off")
    fig.tight_layout()
    pdf = out_prefix + ".pdf"
    fig.savefig(pdf)
    fig.savefig(out_prefix + ".svg")
    fig.savefig(out_prefix + ".png", dpi=200)
    plt.close(fig)
    return pdf


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
    manifest = {"schema": "ccb-paper-1317-setup-figures/1", "bom": args.bom,
                "figures": {}}
    for name in args.figures.split(","):
        rec = Recorder(bom)
        pdf = FIGURES[name](bom, rec, os.path.join(args.output_dir, name))
        manifest["figures"][name] = {"pdf": os.path.basename(pdf), "annotations": rec.used}
        print(f"figure {name}: {pdf} ({len(rec.used)} BOM annotations)")
    with open(os.path.join(args.output_dir, "annotations.json"), "w") as fh:
        json.dump(manifest, fh, indent=1, sort_keys=True)
    # source table: the BOM rows actually consumed
    used = sorted({c for f in manifest["figures"].values() for c in f["annotations"]})
    with open(os.path.join(args.output_dir, "source_table.csv"), "w", newline="") as fh:
        cols = ["component", "quantity", "value", "unit", "status",
                "evidence_path", "claim_ids"]
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for c in used:
            r = bom[c]
            w.writerow({k: getattr(r, k) for k in cols})
    print("annotations:", len(used), "distinct BOM components")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
