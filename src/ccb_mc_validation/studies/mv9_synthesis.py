"""MV9: synthesis report from registry of MV study results.

Extended to (a) auto-discover study-result JSONs under ``reports/`` and build a
registry, (b) render a master comparison plot grid, in addition to the original
registry->markdown synthesizer.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping


VERDICT_ORDER = ("PRODUCTION", "FIXTURE", "NOT_RUN", "BLOCKED")


def _load_registry(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _verdict_line(study_id: str, entry: Mapping[str, Any]) -> str:
    status = entry.get("status", "NOT_RUN")
    metrics = entry.get("metrics", {})
    reason = metrics.get("reason", "")
    if status == "PRODUCTION":
        return f"- **{study_id}**: PRODUCTION — metrics recorded."
    if status == "FIXTURE":
        return f"- **{study_id}**: FIXTURE — synthetic or reduced-statistics run."
    if status == "BLOCKED":
        return f"- **{study_id}**: BLOCKED — {reason}"
    return f"- **{study_id}**: NOT_RUN — {reason}"


def synthesize(registry_path: str | Path, out_path: str | Path | None = None) -> str:
    """Read MV study registry JSON and generate MV9_SYNTHESIS markdown report."""
    registry = _load_registry(registry_path)
    studies: dict[str, Any] = registry.get("studies", registry)

    lines = [
        "# MV9 — MC Validation Synthesis",
        "",
        "Auto-generated verdict column for the MC validation program.",
        "",
        "## Study verdicts",
        "",
    ]
    for study_id in sorted(studies.keys()):
        lines.append(_verdict_line(study_id, studies[study_id]))

    lines.extend(["", "## Summary table", "", "| Study | Status | Key metric |", "| --- | --- | --- |"])
    for study_id in sorted(studies.keys()):
        entry = studies[study_id]
        status = entry.get("status", "NOT_RUN")
        metrics = entry.get("metrics", {})
        key_metric = ""
        for candidate in ("logreg_auc", "hgb_auc", "proton_ekin_recon_res68", "reason"):
            if candidate in metrics:
                key_metric = f"{candidate}={metrics[candidate]}"
                break
        lines.append(f"| {study_id} | {status} | {key_metric} |")

    lines.append("")
    markdown = "\n".join(lines)
    if out_path is not None:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown, encoding="utf-8")
    return markdown


# ---------------------------------------------------------------------------
# Report auto-discovery + master plot (MV9 extension)
# ---------------------------------------------------------------------------

# study_id -> (filename glob for the summary JSON, human key-result extractor)
_STUDY_SPECS: dict[str, dict[str, Any]] = {
    "MV1": {"glob": "mv1_mv2_truth_pid_energy_*/mv1_mv2_truth_summary.json"},
    "MV2": {"glob": "mv1_mv2_truth_pid_energy_*/mv1_mv2_truth_summary.json"},
    "MV3": {"glob": "mv3_stopping_*/*.json"},
    "MV4": {"glob": "mv4_timing_*/*.json"},
    "MV5": {"glob": "mv5_pileup_*/mv5_pileup_summary.json"},
    "MV6": {"glob": "mv6_representation_*/mv6_representation_summary.json"},
}


def _latest(report_root: Path, glob: str) -> Path | None:
    matches = sorted(report_root.glob(glob))
    matches += sorted((report_root / "mc_validation").glob(glob))
    if not matches:
        return None
    # newest by embedded unix stamp if present, else mtime
    def stamp(p: Path) -> float:
        m = re.search(r"_(\d{9,})", str(p))
        return float(m.group(1)) if m else p.stat().st_mtime
    return max(matches, key=stamp)


def _key_result(study_id: str, data: Mapping[str, Any]) -> str:
    """Pull a one-line headline metric from a study's summary JSON."""
    if study_id == "MV1":
        for k in ("logreg_auc", "hgb_auc", "pid_auc"):
            if k in data:
                return f"PID AUC={data[k]:.3f}"
        return "PID p/d separation"
    if study_id == "MV2":
        for k in ("proton_ekin_recon_res68", "ekin_res68"):
            if k in data:
                return f"Ekin res68={data[k]}"
        return "range-energy calibration"
    if study_id == "MV3":
        return "stopping-depth Sample I/II"
    if study_id == "MV4":
        return data.get("timing_res68_ns", "single-stave timing")
    if study_id == "MV5":
        rm = {r["tau_eff_ns"]: r for r in data.get("rmax_by_tau_eff", [])}
        if 124.8 in rm:
            return f"Rmax={rm[124.8]['rmax_duty_corrected_mhz']:.2f} MHz (tau=124.8ns)"
        return "pile-up / Rmax"
    if study_id == "MV6":
        ep = data.get("early_peak_species_composition", {})
        top = next(iter(ep)) if ep else "?"
        return f"anomaly={data.get('anomaly_frac_total', 0)*100:.1f}% -> {top}"
    return "n/a"


def build_registry_from_reports(report_root: str | Path) -> dict[str, Any]:
    """Scan ``report_root`` for MV study JSONs; return a registry dict."""
    root = Path(report_root)
    studies: dict[str, Any] = {}
    for study_id, spec in _STUDY_SPECS.items():
        path = _latest(root, spec["glob"])
        if path is None:
            studies[study_id] = {"status": "NOT_RUN",
                                 "metrics": {"reason": "no report json found"}}
            continue
        try:
            data = json.loads(path.read_text())
        except Exception as exc:  # noqa: BLE001
            studies[study_id] = {"status": "BLOCKED",
                                 "metrics": {"reason": f"unreadable: {exc}"}}
            continue
        studies[study_id] = {
            "status": "PRODUCTION",
            "report": str(path),
            "key_result": _key_result(study_id, data),
            "metrics": {"key_result": _key_result(study_id, data)},
        }
    return {"studies": studies}


def master_plot(registry: Mapping[str, Any], report_root: str | Path,
                out_png: str | Path) -> None:
    """Render a grid of per-study PNG thumbnails (the study's own headline plot)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.image as mpimg
    import matplotlib.pyplot as plt

    studies = registry.get("studies", registry)
    # study_id -> headline png glob (relative to the report dir)
    png_for = {
        "MV1": "mv1_mv2_truth.png", "MV2": "mv1_mv2_truth.png",
        "MV3": "*.png", "MV4": "*.png",
        "MV5": "mv5_pileup.png", "MV6": "mv6_representation.png",
    }
    items = []
    for sid in sorted(studies.keys()):
        entry = studies[sid]
        rpt = entry.get("report")
        png = None
        if rpt:
            d = Path(rpt).parent
            cands = sorted(d.glob(png_for.get(sid, "*.png")))
            png = cands[0] if cands else None
        items.append((sid, entry.get("status", "NOT_RUN"),
                      entry.get("key_result", ""), png))

    n = len(items)
    cols = 3
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(6 * cols, 4.2 * rows))
    axes = np.atleast_1d(axes).ravel()
    for ax, (sid, status, key, png) in zip(axes, items):
        ax.axis("off")
        if png and Path(png).exists():
            ax.imshow(mpimg.imread(str(png)))
        else:
            ax.text(0.5, 0.5, f"{sid}\n{status}", ha="center", va="center",
                    fontsize=14, transform=ax.transAxes)
        ax.set_title(f"{sid} [{status}] {key}", fontsize=9)
    for ax in axes[n:]:
        ax.axis("off")
    fig.suptitle("MV9 — MC Validation master synthesis", fontsize=15)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=130)
    plt.close(fig)


# numpy is only needed by master_plot; import lazily-safe at module level
import numpy as np  # noqa: E402
