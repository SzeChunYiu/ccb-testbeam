"""Generate lightweight run-summary report artifacts from VALIDATION.json."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def _metric(metrics: dict[str, Any], key: str) -> str:
    val = metrics.get(key, "")
    if isinstance(val, float):
        return f"{val:.12g}"
    return str(val) if val != "" else ""


def generate_run_summary(run_root: Path) -> dict[str, str]:
    """Generate CSV/Markdown/SVG/PNG summary artifacts for a validated run."""
    validation_path = run_root / "VALIDATION.json"
    if not validation_path.is_file():
        raise FileNotFoundError(f"missing validation file: {validation_path}")
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    study_metrics = validation.get("study_metrics", {})
    out_dir = run_root / "reports" / "mc_validation" / "summary"
    fig_dir = run_root / "figures" / "summary"
    out_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
    for study in ("MV1", "MV2", "MV3"):
        rec = study_metrics.get(study, {})
        metrics = rec.get("metrics", {}) if isinstance(rec, dict) else {}
        cutflow = rec.get("cutflow", {}) if isinstance(rec, dict) else {}
        rows.append(
            {
                "study": study,
                "status": str(rec.get("status", "")),
                "n_tracks": str(cutflow.get("n_tracks", "")),
                "hgb_auc": _metric(metrics, "hgb_auc"),
                "hgb_purity_at_90eff": _metric(metrics, "hgb_purity_at_90eff"),
                "proton_ekin_recon_res68": _metric(metrics, "proton_ekin_recon_res68"),
                "deuteron_ekin_recon_res68": _metric(metrics, "deuteron_ekin_recon_res68"),
                "n_sample_I": str(cutflow.get("n_sample_I", "")),
                "n_sample_II": str(cutflow.get("n_sample_II", "")),
            }
        )

    csv_path = out_dir / "metrics_table.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    md_path = out_dir / "RUN_SUMMARY.md"
    lines = [
        "# MC Validation Run Summary",
        "",
        f"- **Run ID:** `{validation.get('run_id')}`",
        f"- **Artifact validation:** `{validation.get('status')}`",
        f"- **Job ID:** `{validation.get('job_state', {}).get('job_id', 'unknown')}`",
        f"- **Job state:** `{validation.get('job_state', {}).get('state', 'unknown')}` / `{validation.get('job_state', {}).get('exit_code', 'unknown')}`",
        "",
        "| Study | Status | n tracks | Key metric |",
        "|---|---:|---:|---|",
    ]
    for row in rows:
        key = row["hgb_auc"] or row["proton_ekin_recon_res68"] or row["n_sample_I"]
        lines.append(f"| {row['study']} | {row['status']} | {row['n_tracks']} | {key} |")
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "This is a compact artifact summary. It is not a final release, thesis, uncertainty study, or detector-physics conclusion by itself.",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    try:
        import matplotlib.pyplot as plt

        studies = [row["study"] for row in rows]
        n_tracks = [float(row["n_tracks"] or 0) for row in rows]
        fig, ax = plt.subplots(figsize=(6, 3.5))
        ax.bar(studies, n_tracks, color=["#0072B2", "#009E73", "#D55E00"])
        ax.set_ylabel("records")
        ax.set_title("MC validation study support")
        ax.ticklabel_format(axis="y", style="plain")
        fig.tight_layout()
        support_svg = fig_dir / "study_support.svg"
        support_png = fig_dir / "study_support.png"
        fig.savefig(support_svg)
        fig.savefig(support_png, dpi=300)
        plt.close(fig)

        mv1_auc = float(rows[0]["hgb_auc"] or 0)
        mv1_purity = float(rows[0]["hgb_purity_at_90eff"] or 0)
        mv2_p = float(rows[1]["proton_ekin_recon_res68"] or 0)
        mv2_d = float(rows[1]["deuteron_ekin_recon_res68"] or 0)
        fig, ax = plt.subplots(figsize=(6, 3.5))
        labels = ["MV1 HGB AUC", "MV1 purity@90%", "MV2 p res68", "MV2 d res68"]
        vals = [mv1_auc, mv1_purity, mv2_p, mv2_d]
        ax.bar(labels, vals, color="#56B4E9")
        ax.set_ylim(0, max(1.0, max(vals) * 1.15))
        ax.set_ylabel("metric value")
        ax.set_title("Selected MC validation metrics")
        ax.tick_params(axis="x", rotation=25)
        fig.tight_layout()
        metrics_svg = fig_dir / "selected_metrics.svg"
        metrics_png = fig_dir / "selected_metrics.png"
        fig.savefig(metrics_svg)
        fig.savefig(metrics_png, dpi=300)
        plt.close(fig)
    except Exception as exc:  # pragma: no cover - matplotlib availability/env dependent
        (fig_dir / "FIGURE_GENERATION_FAILED.txt").write_text(str(exc), encoding="utf-8")
        support_svg = support_png = metrics_svg = metrics_png = Path("")

    return {
        "metrics_table": str(csv_path),
        "markdown": str(md_path),
        "study_support_svg": str(support_svg),
        "study_support_png": str(support_png),
        "selected_metrics_svg": str(metrics_svg),
        "selected_metrics_png": str(metrics_png),
    }
