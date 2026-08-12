#!/usr/bin/env python3
"""SiPM sensitivity campaign analyzer (SIPM-P2-001).

For each knob swept by the campaign, reads every per-point .root under
<OUTDIR>/<knob>/, joins the immutable ``*.meta.json`` sidecar (#977/#982),
computes the mean (+ standard error) of the ADC and PE channels, and emits:
  * <OUTDIR>/<knob>/<knob>_sensitivity.png   adc & PE vs knob
  * <OUTDIR>/<knob>/SUMMARY.md                per-knob table + findings
  * <OUTDIR>/<knob>/PROVENANCE.json           per-point requested vs effective
  * <OUTDIR>/SUMMARY.md                       global summary across all knobs

Filename labels are *requests*, never truth. A point is rejected unless the
effective digitizer metadata matches the requested knob within policy and the
producer records one canonical exact ccb-sipm-core revision. Mixed core
revisions are never aggregated into one campaign summary.

Channels (single-stave events ntuple):
  adc_*        canonical ccb-sipm-core production path
  pe_sat_* / detected_*   INDEPENDENT_DIAGNOSTIC_DRAW (#1084) — not upstream of ADC

ADC clip ceiling is derived from effective digitizer metadata
(adc_bits, baseline_adc), not a hard-coded 12-bit/200 default.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Fallback only when metadata lacks ADC fields (should not happen after #977).
from ccb_mc_validation.response_surface import summarize_nuisance_sweep

ADC_CLIP_DEFAULT = 3895.0  # 2**12 - 1 - baseline(200); points at this are saturated
ADC_CLIP_FALLBACK = ADC_CLIP_DEFAULT
CORE_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

ADC_CH = ["adc_readout", "adc_f2near", "adc_f2far"]
PE_CH = ["pe_sat_readout", "detected_readout"]
CTRL_CH = ["edep_scint_MeV"]

# Map filename knob names -> digitizer metadata keys (effective truth).
KNOB_TO_EFFECTIVE: Dict[str, str] = {
    "sipm_n_cells": "number_of_cells",
    "crosstalk": "prompt_crosstalk_probability",
    "afterpulse": "afterpulse_fast_probability",
    "afterpulse_fast": "afterpulse_fast_probability",
    "dark_count": "dark_count_rate_hz",
    "dark_count_rate_hz": "dark_count_rate_hz",
    "recovery": "recovery_time_ns",
    "recovery_time_ns": "recovery_time_ns",
    "pde_scale": "pde_scale",
    "collection_efficiency": "coupling_efficiency",
}


class ProvenanceError(RuntimeError):
    """Requested labels or producer provenance fail the authorisation contract."""


def adc_clip_from_digitizer(digitizer: Dict[str, Any]) -> float:
    bits = int(digitizer.get("adc_bits", 12))
    baseline = float(digitizer.get("baseline_adc", 200.0))
    return float((2**bits) - 1) - baseline


def canonical_core_sha(value: Any, *, context: str) -> str:
    """Return one exact lowercase 40-hex core revision or fail closed."""
    if not isinstance(value, str) or not CORE_SHA_RE.fullmatch(value) or value == "0" * 40:
        raise ProvenanceError(
            f"{context}: ccb_sipm_core_commit missing or invalid: {value!r}; "
            "require canonical lowercase 40-hex producer identity"
        )
    return value


def load_sidecar(root_path: Path, *, expected_core_sha: Optional[str] = None) -> Dict[str, Any]:
    meta_path = Path(str(root_path) + ".meta.json")
    if not meta_path.is_file():
        # Also accept stem.meta.json next to foo.root
        alt = root_path.with_suffix(root_path.suffix + ".meta.json")
        if alt.is_file():
            meta_path = alt
        else:
            raise ProvenanceError(f"missing sidecar for {root_path}: {meta_path}")
    data = json.loads(meta_path.read_text())
    dig = data.get("digitizer")
    if not isinstance(dig, dict):
        raise ProvenanceError(f"{meta_path}: digitizer block missing")
    if dig.get("validation_status") != "OK":
        raise ProvenanceError(
            f"{meta_path}: digitizer.validation_status="
            f"{dig.get('validation_status')!r} (non-authorising)"
        )
    if not dig.get("digitizer_config_sha256"):
        raise ProvenanceError(f"{meta_path}: digitizer_config_sha256 missing")
    actual_core_sha = canonical_core_sha(
        dig.get("ccb_sipm_core_commit"), context=str(meta_path)
    )
    if expected_core_sha is not None:
        expected = canonical_core_sha(expected_core_sha, context="expected core SHA")
        if actual_core_sha != expected:
            raise ProvenanceError(
                f"{meta_path}: ccb_sipm_core_commit={actual_core_sha} "
                f"!= expected {expected}"
            )
    return data


def effective_knob_value(digitizer: Dict[str, Any], knob: str) -> Any:
    key = KNOB_TO_EFFECTIVE.get(knob, knob)
    if key not in digitizer:
        raise ProvenanceError(
            f"digitizer metadata lacks effective key {key!r} for knob {knob!r}"
        )
    return digitizer[key]


def values_match(requested: str, effective: Any, *, rtol: float = 0.0, atol: float = 0.0) -> bool:
    """Exact match for ints/strings; float compare with optional tolerance."""
    if isinstance(effective, bool):
        return requested.lower() in ("1", "true", "yes") if effective else requested.lower() in (
            "0",
            "false",
            "no",
        )
    try:
        req_f = float(requested)
        eff_f = float(effective)
        return abs(req_f - eff_f) <= atol + rtol * abs(eff_f)
    except (TypeError, ValueError):
        return str(requested) == str(effective)


def assert_requested_matches_effective(
    knob: str,
    requested: str,
    meta: Dict[str, Any],
) -> Dict[str, Any]:
    dig = meta["digitizer"]
    effective = effective_knob_value(dig, knob)
    if not values_match(requested, effective):
        raise ProvenanceError(
            f"requested {knob}={requested!r} != effective {effective!r} "
            f"(digitizer_config_sha256={dig.get('digitizer_config_sha256')})"
        )
    core_sha = canonical_core_sha(
        dig.get("ccb_sipm_core_commit"), context="digitizer metadata"
    )
    return {
        "knob": knob,
        "requested": requested,
        "effective": effective,
        "digitizer_config_sha256": dig.get("digitizer_config_sha256"),
        "ccb_sipm_core_commit": core_sha,
        "core_identity_status": "EXACT_40HEX_CAMPAIGN_CONSISTENT",
        "adc_bits": dig.get("adc_bits"),
        "baseline_adc": dig.get("baseline_adc"),
        "adc_clip": adc_clip_from_digitizer(dig),
    }


def _stderr(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 2:
        return float("nan")
    return float(np.std(x, ddof=1) / math.sqrt(n))


def _mean(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return float("nan")
    return float(np.mean(x))


def read_point(root_path: Path, adc_clip: float) -> Dict[str, float]:
    """Return per-point means for the channels of interest + n_events."""
    import uproot

    cols = ADC_CH + PE_CH + CTRL_CH + ["adc_f1far", "pe_sat_f2near", "detected_f2near"]
    df = uproot.open(str(root_path))["events"].arrays(cols, library="pd")
    out: Dict[str, float] = {}
    for c in cols:
        if c in df.columns:
            out[f"mean_{c}"] = _mean(df[c].to_numpy())
            out[f"sem_{c}"] = _stderr(df[c].to_numpy())
    out["n_events"] = int(len(df))
    if "adc_readout" in df.columns:
        out["frac_clipped_readout"] = float(
            np.mean(df["adc_readout"].to_numpy() >= adc_clip - 0.5)
        )
    else:
        out["frac_clipped_readout"] = float("nan")
    out["adc_clip"] = float(adc_clip)
    return out


def _parse_label(label: str) -> Tuple[str, str]:
    if "=" not in label:
        return label, label
    knob, val = label.split("=", 1)
    return knob, val


def _is_numeric_column(vals: List[str]) -> bool:
    try:
        for v in vals:
            float(v)
        return True
    except ValueError:
        return False


def collect_knob(
    knob_dir: Path,
    *,
    expected_core_sha: Optional[str] = None,
) -> Tuple[List[str], List[Dict[str, float]], List[str], List[Dict[str, Any]]]:
    """Return (values, stats, labels, provenance_rows). Fail-closed on mismatch."""
    files = sorted(knob_dir.glob("*.root"))
    if not files:
        return [], [], [], []
    values: List[str] = []
    stats: List[Dict[str, float]] = []
    labels: List[str] = []
    prov_rows: List[Dict[str, Any]] = []
    digests: set[str] = set()
    observed_core_sha: Optional[str] = None
    for fp in files:
        knob, val = _parse_label(fp.stem)
        meta = load_sidecar(fp, expected_core_sha=expected_core_sha)
        row = assert_requested_matches_effective(knob, val, meta)
        core_sha = str(row["ccb_sipm_core_commit"])
        if observed_core_sha is None:
            observed_core_sha = core_sha
        elif core_sha != observed_core_sha:
            raise ProvenanceError(
                f"{knob_dir}: mixed ccb_sipm_core_commit values "
                f"{observed_core_sha} and {core_sha}; do not aggregate code revisions"
            )
        digests.add(str(row["digitizer_config_sha256"]))
        # Refuse mixed profile digests within one knob dir unless values differ
        # only by the scanned knob (digest is allowed to change with the knob).
        st = read_point(fp, float(row["adc_clip"]))
        st["digitizer_config_sha256_hash"] = float(
            int(hashlib.sha256(str(row["digitizer_config_sha256"]).encode()).hexdigest()[:8], 16)
        )
        values.append(val)
        stats.append(st)
        labels.append(fp.stem)
        prov_rows.append({**row, "root": str(fp), "meta": str(fp) + ".meta.json"})
    return values, stats, labels, prov_rows


def _safe_float(v: str) -> float:
    try:
        return float(v)
    except ValueError:
        return float("nan")


def plot_knob(
    knob: str,
    unit: str,
    values: List[str],
    stats: List[Dict[str, float]],
    out_png: Path,
    adc_clip: float,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    numeric = _is_numeric_column(values)
    x = [_safe_float(v) for v in values] if numeric else range(len(values))

    fig, (ax_adc, ax_pe) = plt.subplots(2, 1, figsize=(7, 7), sharex=numeric)
    for ch, marker in zip(ADC_CH, ["o", "s", "^"]):
        ys = [s.get(f"mean_{ch}", float("nan")) for s in stats]
        es = [s.get(f"sem_{ch}", 0.0) for s in stats]
        ax_adc.errorbar(x, ys, yerr=es, marker=marker, capsize=3, label=ch)
    ax_adc.axhline(
        adc_clip, color="red", ls="--", lw=1, label=f"ADC clip ({adc_clip:.0f})"
    )
    ax_adc.set_ylabel("peak ADC above baseline")
    ax_adc.set_title(f"SiPM sensitivity: {knob}  [{unit}]")
    ax_adc.legend(fontsize=8)
    ax_adc.grid(alpha=0.3)
    for ch, marker in zip(PE_CH, ["o", "s"]):
        ys = [s.get(f"mean_{ch}", float("nan")) for s in stats]
        es = [s.get(f"sem_{ch}", 0.0) for s in stats]
        ax_pe.errorbar(
            x,
            ys,
            yerr=es,
            marker=marker,
            capsize=3,
            label=f"{ch} (independent diagnostic)",
        )
    ax_pe.set_ylabel("photo-electrons / event (diagnostic)")
    if numeric:
        ax_pe.set_xlabel(f"{knob}  [{unit}]")
    else:
        ax_pe.set_xticks(list(range(len(values))))
        ax_pe.set_xticklabels(values, rotation=30, ha="right")
        ax_pe.set_xlabel(knob)
    ax_pe.legend(fontsize=8)
    ax_pe.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_png, dpi=130)
    plt.close(fig)


def summarize_knob(
    knob: str,
    unit: str,
    rationale: str,
    values: List[str],
    stats: List[Dict[str, float]],
) -> str:
    lines = [
        f"# {knob}",
        "",
        f"- **unit**: {unit}",
        f"- **rationale**: {rationale}",
        f"- **points**: {len(values)}",
        "- **note**: `pe_sat_*` / `detected_*` are independent diagnostic draws "
        "(#1084); causal calibration must use `adc_*` only.",
        "",
        "| value | n_events | adc_readout | pe_sat_readout (diag) | detected_readout (diag) | edep_scint_MeV | frac_clipped |",
        "|-------|----------|-------------|----------------------|-------------------------|----------------|--------------|",
    ]
    for v, s in zip(values, stats):
        lines.append(
            f"| {v} | {int(s.get('n_events', 0))} | "
            f"{s.get('mean_adc_readout', float('nan')):.1f} | "
            f"{s.get('mean_pe_sat_readout', float('nan')):.2f} | "
            f"{s.get('mean_detected_readout', float('nan')):.2f} | "
            f"{s.get('mean_edep_scint_MeV', float('nan')):.3f} | "
            f"{s.get('frac_clipped_readout', float('nan')):.2f} |"
        )
    # #985: local/asymmetric response near nominal — not a forced global line.
    if _is_numeric_column(values) and len(values) >= 2:
        xs = np.array([_safe_float(v) for v in values], dtype=float)
        clips = np.array(
            [s.get("frac_clipped_readout", 0.0) for s in stats], dtype=float
        )
        for obs, label in [
            ("mean_adc_readout", "adc_readout"),
            ("mean_pe_sat_readout", "pe_sat_readout"),
            ("mean_detected_readout", "detected_readout"),
        ]:
            ys = np.array([s.get(obs, float("nan")) for s in stats], dtype=float)
            summary = summarize_nuisance_sweep(xs, ys, frac_clipped=clips)
            slope = summary.get("recommended_slope", float("nan"))
            elast = summary.get("recommended_elasticity", float("nan"))
            lines.append(
                f"  - `{label}` local d(obs)/d({knob}) near nominal = "
                f"{slope:.4g} per {unit}; local elasticity = {elast:.3f}"
            )
            if summary.get("global_linear_misleading"):
                reasons = ",".join(summary.get("misleading_reasons") or [])
                lines.append(
                    f"  - `{label}` **global linear slope MISLEADING** "
                    f"({reasons}); use local/asymmetric response (#985)."
                )
            asym = summary.get("asymmetric_excursion") or {}
            lines.append(
                f"  - `{label}` asymmetric unsaturated Δy: "
                f"below={asym.get('delta_y_min_below', float('nan')):.4g}, "
                f"above={asym.get('delta_y_max_above', float('nan')):.4g}"
            )
    frac_clip = [s.get("frac_clipped_readout", 0.0) for s in stats]
    if any(f > 0.5 for f in frac_clip):
        lines.append("")
        lines.append(
            "> **ADC saturation**: >=1 point has >50% of events at the clip "
            "ceiling; the ADC response is uninformative there."
        )
    lines.append("")
    return "\n".join(lines)


def load_grid_meta(grids_dir: Path, knob: str) -> Tuple[str, str]:
    csv = grids_dir / f"points_{knob}.csv"
    unit, rationale = "?", ""
    if csv.exists():
        for ln in csv.read_text().splitlines():
            if ln.startswith("# channel"):
                m = re.search(r"unit:\s*(.+)$", ln)
                if m:
                    unit = m.group(1).strip()
            elif ln.startswith("# rationale:"):
                rationale = ln.split("rationale:", 1)[1].strip()
    return unit, rationale


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("outdir", help="campaign output root (contains <knob>/ dirs)")
    ap.add_argument(
        "--grids-dir",
        default=None,
        help="points_<knob>.csv dir for unit/rationale (default: infer from repo)",
    )
    ap.add_argument(
        "--knob",
        action="append",
        default=None,
        help="specific knob(s) to analyze (default: every <knob>/ subdir)",
    )
    ap.add_argument(
        "--expected-core-sha",
        default=None,
        help=(
            "optional externally pinned canonical 40-hex ccb-sipm-core revision; "
            "every sidecar must match exactly"
        ),
    )
    args = ap.parse_args()

    outdir = Path(args.outdir)
    if not outdir.is_dir():
        print(f"error: {outdir} is not a directory", file=sys.stderr)
        return 2

    expected_core_sha: Optional[str] = None
    if args.expected_core_sha is not None:
        try:
            expected_core_sha = canonical_core_sha(
                args.expected_core_sha, context="--expected-core-sha"
            )
        except ProvenanceError as e:
            print(f"error: provenance gate failed: {e}", file=sys.stderr)
            return 3

    grids_dir = Path(args.grids_dir) if args.grids_dir else None
    if grids_dir is None:
        here = Path(__file__).resolve()
        cand = here.parents[2] / "geant4" / "single_stave" / "slurm" / "grids"
        if cand.is_dir():
            grids_dir = cand

    knobs = args.knob if args.knob else sorted(
        d.name for d in outdir.iterdir() if d.is_dir()
    )
    if not knobs:
        print(f"no knob sweep dirs found under {outdir}", file=sys.stderr)
        return 1

    global_sections: List[str] = [
        "# SiPM Sensitivity Campaign — SUMMARY",
        "",
        f"Output root: `{outdir}`",
        "",
        "Filename labels are requests; points are admitted only when effective "
        "digitizer metadata matches (#982), an exact canonical 40-hex "
        "ccb-sipm-core revision is present (#977), and one code revision is "
        "used across the campaign. `adc_*` is the production path; "
        "`pe_sat_*`/`detected_*` are independent diagnostics (#1084). "
        "Elasticity uses local unsaturated response near nominal (#985).",
        "",
    ]
    if expected_core_sha is not None:
        global_sections += [f"Externally expected ccb-sipm-core: `{expected_core_sha}`", ""]
    else:
        global_sections += [
            "External core pin: not supplied; exact producer identity is still required "
            "and campaign-internal mixed revisions are rejected.",
            "",
        ]

    n_total_points = 0
    n_clipped_points = 0
    observed_campaign_core_sha: Optional[str] = None
    per_knob_rows = [
        "| knob | unit | npoints | adc_readout range | clipped pts | elasticity(adc) |",
        "|------|------|---------|--------------------|-------------|------------------|",
    ]

    for knob in knobs:
        kdir = outdir / knob
        if not kdir.is_dir():
            print(f"warn: no dir for knob {knob}", file=sys.stderr)
            continue
        unit, rationale = ("?", "")
        if grids_dir:
            unit, rationale = load_grid_meta(grids_dir, knob)
        try:
            values, stats, labels, prov_rows = collect_knob(
                kdir, expected_core_sha=expected_core_sha
            )
            if prov_rows:
                knob_core_shas = {str(row["ccb_sipm_core_commit"]) for row in prov_rows}
                if len(knob_core_shas) != 1:
                    raise ProvenanceError(
                        f"{kdir}: mixed ccb_sipm_core_commit values within knob"
                    )
                knob_core_sha = next(iter(knob_core_shas))
                if observed_campaign_core_sha is None:
                    observed_campaign_core_sha = knob_core_sha
                elif knob_core_sha != observed_campaign_core_sha:
                    raise ProvenanceError(
                        "mixed ccb_sipm_core_commit values across campaign: "
                        f"{observed_campaign_core_sha} and {knob_core_sha}"
                    )
        except ProvenanceError as e:
            print(f"error: provenance gate failed for {knob}: {e}", file=sys.stderr)
            return 3
        if not stats:
            print(f"warn: no readable .root for knob {knob}", file=sys.stderr)
            continue
        (kdir / "PROVENANCE.json").write_text(json.dumps(prov_rows, indent=2) + "\n")
        adc_clip = float(stats[0].get("adc_clip", ADC_CLIP_FALLBACK))
        n_total_points += len(stats)
        n_clipped_points += sum(
            1 for s in stats if s.get("frac_clipped_readout", 0.0) > 0.5
        )
        out_png = kdir / f"{knob}_sensitivity.png"
        try:
            plot_knob(knob, unit, values, stats, out_png, adc_clip)
            print(f"  wrote {out_png}")
        except Exception as e:  # pragma: no cover
            print(f"warn: plot failed for {knob}: {e}", file=sys.stderr)
        (kdir / "SUMMARY.md").write_text(
            summarize_knob(knob, unit, rationale, values, stats)
        )
        adcs = [s.get("mean_adc_readout", float("nan")) for s in stats]
        clipped = sum(1 for s in stats if s.get("frac_clipped_readout", 0.0) > 0.5)
        elast_str = "n/a"
        if _is_numeric_column(values) and len(values) >= 2:
            xs = np.array([_safe_float(v) for v in values], dtype=float)
            ys = np.array(adcs, dtype=float)
            clips = np.array(
                [s.get("frac_clipped_readout", 0.0) for s in stats], dtype=float
            )
            summary = summarize_nuisance_sweep(xs, ys, frac_clipped=clips)
            elast = summary.get("recommended_elasticity", float("nan"))
            if np.isfinite(elast):
                elast_str = f"{elast:.3f}"
                if summary.get("global_linear_misleading"):
                    elast_str += " (local; global-linear misleading)"
        finite_adcs = [v for v in adcs if math.isfinite(v)]
        rng = (
            f"{min(finite_adcs):.0f}..{max(finite_adcs):.0f}" if finite_adcs else "n/a"
        )
        per_knob_rows.append(
            f"| {knob} | {unit} | {len(stats)} | {rng} | {clipped} | {elast_str} |"
        )
        global_sections.append(f"## {knob}")
        global_sections.append(f"![{knob}]({knob}/{knob}_sensitivity.png)")
        global_sections.append("")
        global_sections.append(f"see `{knob}/SUMMARY.md` / `{knob}/PROVENANCE.json`.")

    global_sections += ["", "## Cross-knob sensitivity", ""]
    global_sections += per_knob_rows
    global_sections += [
        "",
        f"**Observed ccb-sipm-core revision**: `{observed_campaign_core_sha or 'NONE'}`",
        f"**Totals**: {n_total_points} points across {len(knobs)} knobs; "
        f"{n_clipped_points} point(s) ADC-clipped.",
        "",
    ]
    (outdir / "SUMMARY.md").write_text("\n".join(global_sections) + "\n")
    print(f"\nwrote {outdir / 'SUMMARY.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
