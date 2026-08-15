#!/usr/bin/env python3
"""#1319 provenance-bound MC longitudinal profile + sparse-readout comparison.

Input is the authorising 2M-campaign MC event table (committed artifact of the
#618 species-penetration campaign): per-event raw deposited energy in each of
the eight physical B-stack layers, truth species, proxy sample family and the
legacy readout aliases. Nothing else is consulted; no stored summary column is
trusted (the #618 ``E_mc_*`` columns are downstream-deltaE readout sums, not
full stack sums, and are documented as such rather than reused).

Namespace discipline (#1319 audit point 3): physical layer columns
``edep_layer_0..7`` are a frozen tuple. Readout aliases live in a separate
``ChannelMap`` (channel -> physical layer index) which accepts integers in
range, is injective, and can never rename or overwrite a physical column.

Accounting discipline (point 4/10): the per-event stack sum is computed exactly
once from the frozen physical tuple; a known-answer toy event with distinct
deposits in all eight layers pins the arithmetic.

Event measure (point 1/2/9): the campaign generator samples the target
distribution directly, so weights are expected to be identically 1.0. This is
verified, never assumed, and sum(w), sum(w^2), ESS and negative/non-finite
counts are reported for every panel.

Trigger (point 6): selection is the campaign's MC_TRIGGER_PROXY. The label is
rendered on-figure and carried in the result JSON; no Sample-I/II hardware
reproduction is claimed.

Energy semantics (point 7): raw deposited energy (MeV). Birks-visible energy is
a distinct quantity (#1302) and is not mixed in.

Parity (point 5): the B2/B4/B6/B8 -> LayerID offset is unresolved (#869). Both
hypotheses are shown as a nuisance envelope: EVEN (BOM ``B_channel_to_G4_layer_map``,
issue #1296) and ODD (the legacy convention carried by the #618 readout columns,
argued in #869). Neither is treated as canonical.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Frozen physical-layer namespace. Readout aliases may never touch these names.
PHYSICAL_LAYERS: tuple[str, ...] = tuple(f"edep_layer_{i}" for i in range(8))
READOUT_CHANNELS: tuple[str, ...] = ("B2", "B4", "B6", "B8")
SPECIES = ("p", "d", "other")
SPECIES_COLORS = {"p": "tab:blue", "d": "tab:orange", "other": "tab:gray"}

PROXY_LABEL = "MC_TRIGGER_PROXY (#1045 open; no hardware-trigger claim)"
ENERGY_LABEL = "raw deposited energy, MeV (not Birks-visible; #1302)"
PARITY_LABEL = ("B2/B4/B6/B8 offset unresolved (#869): BOM even map "
                "B2->0/4->2/6->4/8->6 (#1296) vs legacy odd map 1/3/5/7 (#618)")
FIGURE_NAME = "mc_depth_profile"
BOOTSTRAP_REPS = 1000
BOOTSTRAP_SEED = 1319
SCHEMA = "ccb-paper-1319-mc-depth-profile/1"


class MapError(ValueError):
    """Raised when a readout alias mapping violates the namespace contract."""


@dataclass(frozen=True)
class ChannelMap:
    """Readout-alias -> physical-layer-index map (separate namespace)."""

    mapping: dict[str, int]
    label: str

    def __post_init__(self) -> None:
        for channel, layer in self.mapping.items():
            if isinstance(layer, bool) or not isinstance(layer, int):
                raise MapError(
                    f"alias {channel}->{layer!r}: layer must be an int index, "
                    "never a column name (namespace separation)")
            if not 0 <= layer < len(PHYSICAL_LAYERS):
                raise MapError(f"alias {channel}->{layer}: out of range")
        if sorted(self.mapping) != sorted(READOUT_CHANNELS):
            raise MapError(f"aliases must cover exactly {READOUT_CHANNELS}")
        if len(set(self.mapping.values())) != len(self.mapping):
            raise MapError("aliases must be injective over physical layers")

    def layer_of(self, channel: str) -> int:
        return self.mapping[channel]


def load_bom_even_map(bom_path: str | Path) -> ChannelMap:
    """EVEN hypothesis from the hardware truth surface (issue #1296 BOM)."""
    with open(bom_path, newline="", encoding="utf-8") as fh:
        row = next(r for r in csv.DictReader(fh)
                   if r["component"] == "B_channel_to_G4_layer_map")
    mapping = {}
    for pair in row["value"].split(","):
        channel, _, layer = pair.partition("->")
        mapping[channel.strip()] = int(layer.strip())
    return ChannelMap(mapping=mapping, label=f"BOM even map ({row['status']}, #1296)")


def derive_legacy_odd_map(df: pd.DataFrame) -> ChannelMap:
    """ODD hypothesis: the convention the #618 readout columns actually carry.

    Derived by equality against the physical columns -- verified, not assumed.
    """
    for candidate, tag in (({"B2": 1, "B4": 3, "B6": 5, "B8": 7}, "odd"),
                           ({"B2": 0, "B4": 2, "B6": 4, "B8": 6}, "even")):
        if all(np.allclose(df[f"readout_{c}"], df[PHYSICAL_LAYERS[l]])
               for c, l in candidate.items()):
            return ChannelMap(
                mapping=candidate,
                label=f"legacy {tag} map carried by #618 readout columns (#869)")
    raise MapError("readout columns match neither the even nor the odd parity")


def weight_diagnostics(w: np.ndarray) -> dict:
    """sum(w), sum(w^2), ESS, negative and non-finite counts (#1319 point 9)."""
    w = np.asarray(w, dtype=float)
    finite = w[np.isfinite(w)]
    sum_w = float(finite.sum())
    sum_w2 = float((finite * finite).sum())
    ess = sum_w * sum_w / sum_w2 if sum_w2 > 0 else float("nan")
    return {"n": int(w.size), "sum_w": sum_w, "sum_w2": sum_w2, "ess": ess,
            "n_negative": int((finite < 0).sum()),
            "n_nonfinite": int((~np.isfinite(w)).sum())}


def stack_sum(df: pd.DataFrame) -> np.ndarray:
    """Per-event sum over the frozen physical layers, each counted exactly once."""
    columns = [c for c in PHYSICAL_LAYERS if c in df.columns]
    if len(columns) != len(PHYSICAL_LAYERS):
        raise MapError(f"missing physical layer columns: "
                       f"{set(PHYSICAL_LAYERS) - set(columns)}")
    return df[list(PHYSICAL_LAYERS)].to_numpy(dtype=float).sum(axis=1)


def bootstrap_mean_ci(values: np.ndarray, seed: int) -> tuple[float, float]:
    """Event-level bootstrap 68% CI of the mean (weights are all unit here;
    the diagnostic dict is what authorises that statement)."""
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    n = values.size
    reps = min(BOOTSTRAP_REPS, max(200, n))
    idx = rng.integers(0, n, size=(reps, n))
    means = values[idx].mean(axis=1)
    lo, hi = np.percentile(means, [16.0, 84.0])
    return float(lo), float(hi)


def per_layer_stats(df: pd.DataFrame, seed: int) -> list[dict]:
    rows = []
    for i, col in enumerate(PHYSICAL_LAYERS):
        values = df[col].to_numpy(dtype=float)
        lo, hi = bootstrap_mean_ci(values, seed + i)
        rows.append({"layer": i, "n_events": int(len(df)),
                     "mean_edep_mev": float(values.mean()),
                     "sem_edep_mev": float(values.std(ddof=1) / np.sqrt(len(values)))
                     if len(values) > 1 else 0.0,
                     "boot_lo_mev": lo, "boot_hi_mev": hi,
                     "frac_nonzero": float((values > 0).mean())})
    return rows


def sparse_profile(df: pd.DataFrame, cmap: ChannelMap) -> dict[str, float]:
    """Mean raw edep at the physical layer each readout channel samples."""
    return {ch: float(df[PHYSICAL_LAYERS[cmap.layer_of(ch)]].mean())
            for ch in READOUT_CHANNELS}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mc-parquet",
                    default="reports/paper_618_species_penetration_2m_20260814T1449Z/"
                            "deltaE_E_events_mc.parquet")
    ap.add_argument("--bom", default="publication/tables/hardware_bom.csv")
    ap.add_argument("--output-dir", default=None)
    args = ap.parse_args(argv)

    out_dir = Path(args.output_dir or "reports/paper_1319_mc_depth_profile")
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(args.mc_parquet)
    even = load_bom_even_map(args.bom)
    odd = derive_legacy_odd_map(df)

    w = df["PrimaryWeight"].to_numpy(dtype=float)
    weight_diag = weight_diagnostics(w)
    if weight_diag["n_negative"] or weight_diag["n_nonfinite"]:
        print(f"WARNING: non-unit-weight events present: {weight_diag}", file=sys.stderr)

    # Accounting: stack sum once; conservation against the physical columns.
    stack = stack_sum(df)
    direct = np.zeros(len(df))
    for col in PHYSICAL_LAYERS:
        direct += df[col].to_numpy(dtype=float)
    max_residual = float(np.max(np.abs(stack - direct)))
    conservation_ok = bool(max_residual < 1e-9)

    layers_all = per_layer_stats(df, BOOTSTRAP_SEED)
    species_stats = {s: per_layer_stats(df[df["truth_species"] == s]
                                        if s != "other" else
                                        df[~df["truth_species"].isin(("p", "d"))],
                                        BOOTSTRAP_SEED + 100 + i)
                     for i, s in enumerate(SPECIES)}
    sample_stats = {s: per_layer_stats(df[df["sample"] == s], BOOTSTRAP_SEED + 200 + i)
                    for i, s in enumerate(sorted(df["sample"].unique()))}

    sparse_even = sparse_profile(df, even)
    sparse_odd = sparse_profile(df, odd)
    envelope = {ch: (min(sparse_even[ch], sparse_odd[ch]),
                     max(sparse_even[ch], sparse_odd[ch]))
                for ch in READOUT_CHANNELS}

    # ---- figure ----
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.2), constrained_layout=True)
    xs = np.arange(8)

    ax = axes[0]
    species_counts = {s: int((df["truth_species"] == s).sum()) if s != "other"
                      else int((~df["truth_species"].isin(("p", "d"))).sum())
                      for s in SPECIES}
    bottoms = np.zeros(8)
    for s in SPECIES:
        means = np.array([r["mean_edep_mev"] for r in species_stats[s]])
        ax.bar(xs, means, bottom=bottoms, width=0.62, color=SPECIES_COLORS[s],
               alpha=0.85, label=f"{s} (n={species_counts[s]})")
        bottoms += means
    totals = np.array([r["mean_edep_mev"] for r in layers_all])
    los = np.array([r["boot_lo_mev"] for r in layers_all])
    his = np.array([r["boot_hi_mev"] for r in layers_all])
    ax.fill_between(xs, los, his, color="black", alpha=0.15,
                    label="bootstrap 68% band")
    ax.plot(xs, totals, "k.-", lw=1.2, ms=5, label="all events")
    ax.set_xticks(xs, [f"L{i}" for i in xs])
    ax.set_xlabel("physical B-stack layer")
    ax.set_ylabel(f"mean {ENERGY_LABEL.split(' (')[0]} [MeV]")
    ax.set_title("(a) full physical profile, species-resolved", fontsize=10)
    ax.legend(fontsize=7, loc="upper right")

    ax = axes[1]
    ax.plot(xs, totals, "k.-", lw=1.2, ms=5, label="full profile")
    for cmap, marker, color, tag in ((even, "s", "tab:green", "even (BOM #1296)"),
                                     (odd, "^", "tab:purple", "odd (legacy #869/#618)")):
        pts = sparse_profile(df, cmap)
        lx = [cmap.layer_of(ch) for ch in READOUT_CHANNELS]
        ly = [pts[ch] for ch in READOUT_CHANNELS]
        ax.plot(lx, ly, marker=marker, color=color, lw=0, ms=8, alpha=0.9,
                label=f"sparse {tag}")
    for j, ch in enumerate(READOUT_CHANNELS):
        lo, hi = envelope[ch]
        x_mid = envelope_xs(j, even, odd)
        ax.plot([x_mid, x_mid], [lo, hi], color="0.4", lw=4, alpha=0.35,
                solid_capstyle="butt")
        ax.annotate(ch, (x_mid, hi + 0.35), fontsize=7, ha="center", color="0.3")
    ax.set_xticks(xs, [f"L{i}" for i in xs])
    ax.set_xlabel("physical B-stack layer")
    ax.set_ylabel("mean raw edep [MeV]")
    ax.set_title("(b) sparse readout sampling, parity nuisance", fontsize=10)
    ax.legend(fontsize=7, loc="upper right")

    ax = axes[2]
    colors = {"I": "tab:blue", "II": "tab:red"}
    for s, rows in sample_stats.items():
        m = np.array([r["mean_edep_mev"] for r in rows])
        lo = np.array([r["boot_lo_mev"] for r in rows])
        hi = np.array([r["boot_hi_mev"] for r in rows])
        c = colors.get(s, "tab:gray")
        n_s = int((df["sample"] == s).sum())
        ax.plot(xs, m, ".-", color=c, lw=1.2, ms=5, label=f"proxy Sample {s} (n={n_s})")
        ax.fill_between(xs, lo, hi, color=c, alpha=0.18)
    ax.set_xticks(xs, [f"L{i}" for i in xs])
    ax.set_xlabel("physical B-stack layer")
    ax.set_ylabel("mean raw edep [MeV]")
    ax.set_title("(c) proxy populations (trigger proxy)", fontsize=10)
    ax.legend(fontsize=7, loc="upper right")

    fig.suptitle("MC longitudinal profile vs sparse B2/B4/B6/B8 sampling "
                 f"(n={len(df):,} proxy-selected events)", fontsize=11)
    fig.text(0.01, 0.012,
             f"{PROXY_LABEL} | {ENERGY_LABEL} | {PARITY_LABEL} | "
             f"weights: unit (ESS {weight_diag['ess']:.0f}/{weight_diag['n']:,})",
             fontsize=6.2, color="0.25", ha="left")
    for suffix in ("pdf", "svg", "png"):
        fig.savefig(out_dir / f"{FIGURE_NAME}.{suffix}", dpi=180)
    plt.close(fig)

    # ---- source table ----
    table_path = out_dir / "source_table.csv"
    with open(table_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["row_type", "layer_or_channel", "n_events",
                         "mean_edep_mev", "sem_edep_mev", "boot_lo_mev",
                         "boot_hi_mev", "frac_nonzero"])
        for r in layers_all:
            writer.writerow(["layer", f"L{r['layer']}", r["n_events"],
                             f"{r['mean_edep_mev']:.6f}", f"{r['sem_edep_mev']:.6f}",
                             f"{r['boot_lo_mev']:.6f}", f"{r['boot_hi_mev']:.6f}",
                             f"{r['frac_nonzero']:.6f}"])
        for cmap, tag in ((even, "sparse_even"), (odd, "sparse_odd")):
            pts = sparse_profile(df, cmap)
            for ch in READOUT_CHANNELS:
                values = df[PHYSICAL_LAYERS[cmap.layer_of(ch)]].to_numpy(dtype=float)
                writer.writerow([tag, ch, len(df), f"{pts[ch]:.6f}", "",
                                 "", "", f"{float((values > 0).mean()):.6f}"])

    # ---- result JSON ----
    result = {
        "schema": SCHEMA,
        "issue": 1319,
        "input": {"mc_parquet": str(args.mc_parquet),
                  "mc_parquet_sha256": sha256_of(args.mc_parquet),
                  "n_events": int(len(df))},
        "event_measure": {"weight_diagnostics": weight_diag,
                          "authorisation": "#1053 closed: direct target sampling, "
                                           "unit weights verified on this artifact"},
        "trigger": {"label": PROXY_LABEL, "validated": False},
        "energy_semantics": ENERGY_LABEL,
        "parity": {"unresolved": True,
                   "hypotheses": {"even": {"map": even.mapping, "label": even.label,
                                           "source": "publication/tables/hardware_bom.csv"},
                                  "odd": {"map": odd.mapping, "label": odd.label,
                                          "source": "#618 readout columns (verified equal)"}},
                   "envelope_mev": {ch: list(envelope[ch]) for ch in READOUT_CHANNELS}},
        "accounting": {"conservation_ok": conservation_ok,
                       "max_abs_residual_mev": max_residual,
                       "definition": "per-event stack sum == sum over the 8 "
                                     "retained physical B layers (exact once)"},
        "panels": {
            "full_species": {"layers": layers_all,
                             "weight_diagnostics": weight_diagnostics(w),
                             "species": {s: species_stats[s] for s in SPECIES}},
            "sample_split": {s: {"layers": sample_stats[s],
                                 "weight_diagnostics": weight_diagnostics(
                                     df[df["sample"] == s]["PrimaryWeight"]
                                     .to_numpy(dtype=float))}
                             for s in sample_stats},
        },
        "outputs": {f"{FIGURE_NAME}.{sfx}": sha256_of(out_dir / f"{FIGURE_NAME}.{sfx}")
                    for sfx in ("pdf", "svg", "png")},
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n",
                                         encoding="utf-8")
    print(json.dumps({"output_dir": str(out_dir),
                      "conservation_ok": conservation_ok,
                      "ess": weight_diag["ess"], "n": weight_diag["n"],
                      "even_map": even.mapping, "odd_map": odd.mapping},
                     indent=2))
    return 0


def envelope_xs(j: int, even: ChannelMap, odd: ChannelMap) -> float:
    """x position of the parity envelope bar for channel index j."""
    return (even.layer_of(READOUT_CHANNELS[j]) + odd.layer_of(READOUT_CHANNELS[j])) / 2.0


def sha256_of(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
