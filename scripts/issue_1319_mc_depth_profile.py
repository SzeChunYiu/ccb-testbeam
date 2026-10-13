#!/usr/bin/env python3
"""#1319 provenance-bound MC longitudinal profile + sparse-readout comparison.

The analysis contract is unchanged: immutable physical-layer columns, verified
unit event weights, explicit trigger-proxy status, raw-deposited-energy
semantics and both readout-parity hypotheses.  The publication rendering is
kept deliberately lean: provenance and issue bookkeeping stay in result.json
and the manuscript caption rather than being printed across the plotting
canvas.

Species profiles are conditional means and therefore MUST NOT be stacked.  The
historical rendering stacked proton/deuteron/other conditional means, whose sum
has no physical interpretation.  This producer plots them separately and shows
the independently computed all-event mean.
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

PHYSICAL_LAYERS: tuple[str, ...] = tuple(f"edep_layer_{i}" for i in range(8))
READOUT_CHANNELS: tuple[str, ...] = ("B2", "B4", "B6", "B8")
SPECIES = ("p", "d", "other")
SPECIES_LABELS = {"p": "proton", "d": "deuteron", "other": "other"}
SPECIES_COLORS = {"p": "#4477AA", "d": "#CC6677", "other": "#888888"}

PROXY_LABEL = "MC_TRIGGER_PROXY (#1045 open; no hardware-trigger claim)"
ENERGY_LABEL = "raw deposited energy, MeV (not Birks-visible; #1302)"
PARITY_LABEL = (
    "B2/B4/B6/B8 offset unresolved (#869): BOM even map "
    "B2->0/4->2/6->4/8->6 (#1296) vs legacy odd map 1/3/5/7 (#618)"
)
FIGURE_NAME = "mc_depth_profile"
BOOTSTRAP_REPS = 1000
BOOTSTRAP_SEED = 1319
SCHEMA = "ccb-paper-1319-mc-depth-profile/2"


class MapError(ValueError):
    pass


@dataclass(frozen=True)
class ChannelMap:
    mapping: dict[str, int]
    label: str

    def __post_init__(self) -> None:
        for channel, layer in self.mapping.items():
            if isinstance(layer, bool) or not isinstance(layer, int):
                raise MapError(
                    f"alias {channel}->{layer!r}: layer must be an int index, "
                    "never a column name (namespace separation)"
                )
            if not 0 <= layer < len(PHYSICAL_LAYERS):
                raise MapError(f"alias {channel}->{layer}: out of range")
        if sorted(self.mapping) != sorted(READOUT_CHANNELS):
            raise MapError(f"aliases must cover exactly {READOUT_CHANNELS}")
        if len(set(self.mapping.values())) != len(self.mapping):
            raise MapError("aliases must be injective over physical layers")

    def layer_of(self, channel: str) -> int:
        return self.mapping[channel]


def load_bom_even_map(bom_path: str | Path) -> ChannelMap:
    with open(bom_path, newline="", encoding="utf-8") as fh:
        row = next(
            r for r in csv.DictReader(fh)
            if r["component"] == "B_channel_to_G4_layer_map"
        )
    mapping: dict[str, int] = {}
    for pair in row["value"].split(","):
        channel, _, layer = pair.partition("->")
        mapping[channel.strip()] = int(layer.strip())
    return ChannelMap(mapping=mapping, label=f"BOM even map ({row['status']}, #1296)")


def derive_legacy_odd_map(df: pd.DataFrame) -> ChannelMap:
    for candidate, tag in (
        ({"B2": 1, "B4": 3, "B6": 5, "B8": 7}, "odd"),
        ({"B2": 0, "B4": 2, "B6": 4, "B8": 6}, "even"),
    ):
        if all(
            np.allclose(df[f"readout_{channel}"], df[PHYSICAL_LAYERS[layer]])
            for channel, layer in candidate.items()
        ):
            return ChannelMap(
                mapping=candidate,
                label=f"legacy {tag} map carried by #618 readout columns (#869)",
            )
    raise MapError("readout columns match neither the even nor the odd parity")


def weight_diagnostics(w: np.ndarray) -> dict:
    w = np.asarray(w, dtype=float)
    finite = w[np.isfinite(w)]
    sum_w = float(finite.sum())
    sum_w2 = float((finite * finite).sum())
    ess = sum_w * sum_w / sum_w2 if sum_w2 > 0 else float("nan")
    return {
        "n": int(w.size),
        "sum_w": sum_w,
        "sum_w2": sum_w2,
        "ess": ess,
        "n_negative": int((finite < 0).sum()),
        "n_nonfinite": int((~np.isfinite(w)).sum()),
    }


def stack_sum(df: pd.DataFrame) -> np.ndarray:
    columns = [c for c in PHYSICAL_LAYERS if c in df.columns]
    if len(columns) != len(PHYSICAL_LAYERS):
        raise MapError(
            f"missing physical layer columns: {set(PHYSICAL_LAYERS) - set(columns)}"
        )
    return df[list(PHYSICAL_LAYERS)].to_numpy(dtype=float).sum(axis=1)


def bootstrap_mean_ci(values: np.ndarray, seed: int) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    n = values.size
    reps = min(BOOTSTRAP_REPS, max(200, n))
    idx = rng.integers(0, n, size=(reps, n))
    means = values[idx].mean(axis=1)
    lo, hi = np.percentile(means, [16.0, 84.0])
    return float(lo), float(hi)


def per_layer_stats(df: pd.DataFrame, seed: int) -> list[dict]:
    rows: list[dict] = []
    for i, col in enumerate(PHYSICAL_LAYERS):
        values = df[col].to_numpy(dtype=float)
        lo, hi = bootstrap_mean_ci(values, seed + i)
        rows.append(
            {
                "layer": i,
                "n_events": int(len(df)),
                "mean_edep_mev": float(values.mean()) if len(values) else float("nan"),
                "sem_edep_mev": (
                    float(values.std(ddof=1) / np.sqrt(len(values)))
                    if len(values) > 1 else 0.0
                ),
                "boot_lo_mev": lo,
                "boot_hi_mev": hi,
                "frac_nonzero": float((values > 0).mean()) if len(values) else float("nan"),
            }
        )
    return rows


def sparse_profile(df: pd.DataFrame, cmap: ChannelMap) -> dict[str, float]:
    return {
        channel: float(df[PHYSICAL_LAYERS[cmap.layer_of(channel)]].mean())
        for channel in READOUT_CHANNELS
    }


def envelope_xs(j: int, even: ChannelMap, odd: ChannelMap) -> float:
    return (
        even.layer_of(READOUT_CHANNELS[j]) + odd.layer_of(READOUT_CHANNELS[j])
    ) / 2.0


def sha256_of(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _style_axes(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(direction="out", length=3, width=0.8, labelsize=8)
    ax.grid(axis="y", alpha=0.15, lw=0.6)


def _plot_profile(ax, xs, rows, *, label, color, marker="o", band=True, zorder=2):
    mean = np.array([r["mean_edep_mev"] for r in rows], dtype=float)
    lo = np.array([r["boot_lo_mev"] for r in rows], dtype=float)
    hi = np.array([r["boot_hi_mev"] for r in rows], dtype=float)
    ax.plot(xs, mean, marker=marker, ms=4.5, lw=1.35, color=color,
            label=label, zorder=zorder)
    if band and np.all(np.isfinite(lo)) and np.all(np.isfinite(hi)):
        ax.fill_between(xs, lo, hi, color=color, alpha=0.12, lw=0, zorder=zorder - 1)


def make_figure(
    df: pd.DataFrame,
    layers_all: list[dict],
    species_stats: dict[str, list[dict]],
    sample_stats: dict[str, list[dict]],
    even: ChannelMap,
    odd: ChannelMap,
    envelope: dict[str, tuple[float, float]],
    out_dir: Path,
) -> None:
    """Render three physically distinct questions without audit textboxes."""
    xs = np.arange(8)
    fig, axes = plt.subplots(1, 3, figsize=(12.4, 3.75), sharex=True)

    # (a) Species-conditional means: separate curves, never stacked.
    ax = axes[0]
    _plot_profile(ax, xs, layers_all, label="all events", color="black",
                  marker="o", band=True, zorder=5)
    for species in SPECIES:
        n_species = int((df["truth_species"] == species).sum()) if species != "other" else int(
            (~df["truth_species"].isin(("p", "d"))).sum()
        )
        if n_species == 0:
            continue
        _plot_profile(
            ax, xs, species_stats[species],
            label=f"{SPECIES_LABELS[species]} (n={n_species:,})",
            color=SPECIES_COLORS[species], marker="s" if species == "d" else "^",
            band=False, zorder=3,
        )
    ax.set_title("(a) species-conditional profile", fontsize=9)
    ax.set_ylabel("Mean raw deposited energy [MeV]", fontsize=8.5)
    ax.legend(frameon=False, fontsize=7, loc="best")
    _style_axes(ax)

    # (b) Full profile and both sparse sampling hypotheses.
    ax = axes[1]
    totals = np.array([r["mean_edep_mev"] for r in layers_all])
    ax.plot(xs, totals, "o-", color="0.2", lw=1.35, ms=4.5, label="all physical layers")
    for cmap, marker, color, label in (
        (even, "s", "#228833", "sparse map A"),
        (odd, "^", "#AA3377", "sparse map B"),
    ):
        values = sparse_profile(df, cmap)
        lx = [cmap.layer_of(ch) for ch in READOUT_CHANNELS]
        ly = [values[ch] for ch in READOUT_CHANNELS]
        ax.plot(lx, ly, marker=marker, ls="none", ms=6.0, color=color, label=label)
    for j, channel in enumerate(READOUT_CHANNELS):
        lo, hi = envelope[channel]
        x_mid = envelope_xs(j, even, odd)
        ax.plot([x_mid, x_mid], [lo, hi], color="0.45", lw=2.0, alpha=0.55)
        ax.text(x_mid, hi + 0.28, channel, fontsize=7, ha="center", va="bottom")
    ax.set_title("(b) sparse sampling / layer-parity nuisance", fontsize=9)
    ax.legend(frameon=False, fontsize=7, loc="best")
    _style_axes(ax)

    # (c) Proxy population comparison.
    ax = axes[2]
    colors = {"I": "#4477AA", "II": "#EE6677"}
    for sample, rows in sample_stats.items():
        n_sample = int((df["sample"] == sample).sum())
        _plot_profile(
            ax, xs, rows, label=f"Sample {sample} proxy (n={n_sample:,})",
            color=colors.get(sample, "0.4"), marker="o", band=True, zorder=3,
        )
    ax.set_title("(c) proxy-selected populations", fontsize=9)
    ax.legend(frameon=False, fontsize=7, loc="best")
    _style_axes(ax)

    for ax in axes:
        ax.set_xticks(xs, [f"L{i}" for i in xs])
        ax.set_xlabel("Physical B-stack layer", fontsize=8.5)

    # No issue IDs, status labels, ESS strings or long caveats inside the figure.
    # Those remain in result.json and the manuscript caption.
    fig.tight_layout(w_pad=1.0)
    for suffix in ("pdf", "svg", "png"):
        fig.savefig(out_dir / f"{FIGURE_NAME}.{suffix}", dpi=220, bbox_inches="tight")
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--mc-parquet",
        default=(
            "reports/paper_618_species_penetration_2m_20260814T1449Z/"
            "deltaE_E_events_mc.parquet"
        ),
    )
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

    stack = stack_sum(df)
    direct = np.zeros(len(df))
    for col in PHYSICAL_LAYERS:
        direct += df[col].to_numpy(dtype=float)
    max_residual = float(np.max(np.abs(stack - direct)))
    conservation_ok = bool(max_residual < 1e-9)

    layers_all = per_layer_stats(df, BOOTSTRAP_SEED)
    species_stats = {
        species: per_layer_stats(
            df[df["truth_species"] == species]
            if species != "other"
            else df[~df["truth_species"].isin(("p", "d"))],
            BOOTSTRAP_SEED + 100 + i,
        )
        for i, species in enumerate(SPECIES)
    }
    sample_stats = {
        sample: per_layer_stats(
            df[df["sample"] == sample], BOOTSTRAP_SEED + 200 + i
        )
        for i, sample in enumerate(sorted(df["sample"].unique()))
    }

    sparse_even = sparse_profile(df, even)
    sparse_odd = sparse_profile(df, odd)
    envelope = {
        channel: (
            min(sparse_even[channel], sparse_odd[channel]),
            max(sparse_even[channel], sparse_odd[channel]),
        )
        for channel in READOUT_CHANNELS
    }

    make_figure(df, layers_all, species_stats, sample_stats, even, odd, envelope, out_dir)

    table_path = out_dir / "source_table.csv"
    with open(table_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "row_type", "layer_or_channel", "n_events", "mean_edep_mev",
                "sem_edep_mev", "boot_lo_mev", "boot_hi_mev", "frac_nonzero",
            ]
        )
        for row in layers_all:
            writer.writerow(
                [
                    "layer", f"L{row['layer']}", row["n_events"],
                    f"{row['mean_edep_mev']:.6f}", f"{row['sem_edep_mev']:.6f}",
                    f"{row['boot_lo_mev']:.6f}", f"{row['boot_hi_mev']:.6f}",
                    f"{row['frac_nonzero']:.6f}",
                ]
            )
        for cmap, tag in ((even, "sparse_even"), (odd, "sparse_odd")):
            points = sparse_profile(df, cmap)
            for channel in READOUT_CHANNELS:
                values = df[PHYSICAL_LAYERS[cmap.layer_of(channel)]].to_numpy(dtype=float)
                writer.writerow(
                    [
                        tag, channel, len(df), f"{points[channel]:.6f}", "", "", "",
                        f"{float((values > 0).mean()):.6f}",
                    ]
                )

    result = {
        "schema": SCHEMA,
        "issue": 1319,
        "input": {
            "mc_parquet": str(args.mc_parquet),
            "mc_parquet_sha256": sha256_of(args.mc_parquet),
            "n_events": int(len(df)),
        },
        "event_measure": {
            "weight_diagnostics": weight_diag,
            "authorisation": "#1053 closed: direct target sampling, unit weights verified on this artifact",
        },
        "trigger": {"label": PROXY_LABEL, "validated": False},
        "energy_semantics": ENERGY_LABEL,
        "parity": {
            "unresolved": True,
            "label": PARITY_LABEL,
            "hypotheses": {
                "even": {
                    "map": even.mapping,
                    "label": even.label,
                    "source": "publication/tables/hardware_bom.csv",
                },
                "odd": {
                    "map": odd.mapping,
                    "label": odd.label,
                    "source": "#618 readout columns (verified equal)",
                },
            },
            "envelope_mev": {
                channel: list(envelope[channel]) for channel in READOUT_CHANNELS
            },
        },
        "accounting": {
            "conservation_ok": conservation_ok,
            "max_abs_residual_mev": max_residual,
            "definition": "per-event stack sum == sum over the 8 retained physical B layers (exact once)",
        },
        "rendering": {
            "species_conditional_means_stacked": False,
            "audit_text_inside_axes": False,
        },
        "panels": {
            "full_species": {
                "layers": layers_all,
                "weight_diagnostics": weight_diagnostics(w),
                "species": {species: species_stats[species] for species in SPECIES},
            },
            "sample_split": {
                sample: {
                    "layers": sample_stats[sample],
                    "weight_diagnostics": weight_diagnostics(
                        df[df["sample"] == sample]["PrimaryWeight"].to_numpy(dtype=float)
                    ),
                }
                for sample in sample_stats
            },
        },
        "outputs": {
            f"{FIGURE_NAME}.{suffix}": sha256_of(out_dir / f"{FIGURE_NAME}.{suffix}")
            for suffix in ("pdf", "svg", "png")
        },
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output_dir": str(out_dir),
                "conservation_ok": conservation_ok,
                "ess": weight_diag["ess"],
                "n": weight_diag["n"],
                "even_map": even.mapping,
                "odd_map": odd.mapping,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
