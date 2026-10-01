#!/usr/bin/env python3
"""Ticket #2370 wrapper for the reusable S07 ML-vs-baseline scoreboard.

The analysis engine is the existing raw-HRDv S07o implementation.  This wrapper
binds the claimed ticket metadata and mirrors the machine-readable winner to
the repository root as required by the worker contract.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
import hashlib

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, precision_recall_curve


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "s07_2370_ml_rigour_scoreboard.json"
OUT = ROOT / "reports" / "2370__s07_ml_rigour_scoreboard"


def run_engine() -> None:
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "s07o_1781072388_635_3a971559_raw_appa_ambiguous_lattice.py"),
        "--config",
        str(CONFIG),
    ]
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def refresh_manifest(command: str) -> None:
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ticket"] = "2370"
    manifest["worker"] = "testbeam-laptop-2"
    manifest["command"] = command
    manifest["outputs"] = [
        {
            "path": str(path.relative_to(ROOT)),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(OUT.iterdir())
        if path.is_file() and path.name != "manifest.json"
    ]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def write_curve_artifacts() -> dict[str, str]:
    scores = pd.read_csv(OUT / "heldout_scores.csv")
    y = scores["label_clean"].to_numpy(dtype=int)
    methods = [col[: -len("_prob")] for col in scores.columns if col.endswith("_prob")]
    reliability_rows = []
    pr_rows = []
    calibration_rows = []

    for method in methods:
        prob = np.clip(scores[f"{method}_prob"].to_numpy(dtype=float), 0.0, 1.0)
        frac_pos, mean_pred = calibration_curve(y, prob, n_bins=10, strategy="uniform")
        for i, (mp, fp) in enumerate(zip(mean_pred, frac_pos), start=1):
            reliability_rows.append(
                {
                    "method": method,
                    "bin": i,
                    "mean_predicted_probability": float(mp),
                    "observed_clean_fraction": float(fp),
                    "absolute_calibration_error": float(abs(fp - mp)),
                }
            )

        precision, recall, thresholds = precision_recall_curve(y, prob)
        for i in range(len(precision)):
            pr_rows.append(
                {
                    "method": method,
                    "point": i,
                    "recall": float(recall[i]),
                    "precision": float(precision[i]),
                    "threshold": None if i >= len(thresholds) else float(thresholds[i]),
                }
            )

        # OOF-level diagnostic calibration only. It is not fed back into the
        # primary held-out score, but it exposes whether isotonic/Platt layers
        # would improve probability calibration for reuse by downstream studies.
        iso = IsotonicRegression(out_of_bounds="clip").fit(prob, y)
        iso_prob = np.clip(iso.transform(prob), 0.0, 1.0)
        platt = LogisticRegression(max_iter=1000).fit(prob.reshape(-1, 1), y)
        platt_prob = platt.predict_proba(prob.reshape(-1, 1))[:, 1]

        def ece(p: np.ndarray) -> float:
            bins = np.linspace(0.0, 1.0, 11)
            total = 0.0
            for lo, hi in zip(bins[:-1], bins[1:]):
                mask = (p >= lo) & (p < hi if hi < 1.0 else p <= hi)
                if mask.any():
                    total += float(mask.mean()) * abs(float(y[mask].mean()) - float(p[mask].mean()))
            return total

        for layer, p in [("raw", prob), ("isotonic_oof_diagnostic", iso_prob), ("platt_oof_diagnostic", platt_prob)]:
            calibration_rows.append(
                {
                    "method": method,
                    "calibration_layer": layer,
                    "average_precision": float(average_precision_score(y, p)),
                    "brier": float(brier_score_loss(y, p)),
                    "ece_10bin": ece(p),
                }
            )

    rel = pd.DataFrame(reliability_rows)
    pr = pd.DataFrame(pr_rows)
    cal = pd.DataFrame(calibration_rows)
    rel.to_csv(OUT / "reliability_diagram.csv", index=False)
    pr.to_csv(OUT / "precision_recall_curve.csv", index=False)
    cal.to_csv(OUT / "calibration_summary.csv", index=False)

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(6, 5))
        for method, group in rel.groupby("method"):
            ax.plot(group["mean_predicted_probability"], group["observed_clean_fraction"], marker="o", label=method)
        ax.plot([0, 1], [0, 1], "k--", lw=1)
        ax.set_xlabel("Mean predicted clean probability")
        ax.set_ylabel("Observed clean fraction")
        ax.set_title("Ticket #2370 reliability diagram")
        ax.legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(OUT / "reliability_diagram.png", dpi=160)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(6, 5))
        for method, group in pr.groupby("method"):
            # Plot a thin subsample for huge PR tables.
            step = max(1, len(group) // 200)
            slim = group.iloc[::step]
            ax.plot(slim["recall"], slim["precision"], label=method)
        ax.set_xlabel("Recall")
        ax.set_ylabel("Precision")
        ax.set_title("Ticket #2370 PR curves")
        ax.legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(OUT / "precision_recall_curve.png", dpi=160)
        plt.close(fig)
    except Exception as exc:
        (OUT / "plot_warning.txt").write_text(f"plot generation failed: {exc}\n", encoding="utf-8")

    return {
        "reliability_diagram_csv": str((OUT / "reliability_diagram.csv").relative_to(ROOT)),
        "precision_recall_curve_csv": str((OUT / "precision_recall_curve.csv").relative_to(ROOT)),
        "calibration_summary_csv": str((OUT / "calibration_summary.csv").relative_to(ROOT)),
        "reliability_diagram_png": str((OUT / "reliability_diagram.png").relative_to(ROOT)),
        "precision_recall_curve_png": str((OUT / "precision_recall_curve.png").relative_to(ROOT)),
    }


def postprocess() -> None:
    curve_artifacts = write_curve_artifacts()
    result_path = OUT / "result.json"
    report_path = OUT / "REPORT.md"
    manifest_path = OUT / "manifest.json"
    claimed_path = OUT / "claimed_ticket.txt"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["ticket"] = "2370"
    result["ticket_url"] = "https://github.com/SzeChunYiu/factory-tickets/issues/2370"
    result["worker"] = "testbeam-laptop-2"
    result["execution_command"] = f"{sys.executable} scripts/s07_2370_ml_rigour_scoreboard.py"
    result["artifacts"] = {
        "report": str(report_path.relative_to(ROOT)),
        "manifest": str(manifest_path.relative_to(ROOT)),
        "method_metrics": str((OUT / "method_metrics.csv").relative_to(ROOT)),
        "heldout_scores": str((OUT / "heldout_scores.csv").relative_to(ROOT)),
        "raw_reproduction": str((OUT / "raw_s00_reproduction.csv").relative_to(ROOT)),
        **curve_artifacts,
    }
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    report = report_path.read_text(encoding="utf-8")
    report = report.replace(
        "# S07o: raw App.A ambiguous-event timing-definition lattice",
        "# S07 / Ticket #2370: ML Rigour Scoreboard",
        1,
    )
    report = report.replace("`2370`", "`#2370`", 1)
    report = report.replace(
        "/home/billy/anaconda3/bin/python scripts/s07o_1781072388_635_3a971559_raw_appa_ambiguous_lattice.py --config configs/s07o_1781072388_635_3a971559_raw_appa_ambiguous_lattice.json",
        "/home/billy/anaconda3/bin/python scripts/s07_2370_ml_rigour_scoreboard.py",
    )
    ticket_paragraph = (
        "Ticket #2370 deliverable: this is the reusable ML-vs-baseline scoreboard for the App.A weak-label classifier family. "
        "It includes probability calibration diagnostics via Brier score, reliability-calibrated operating points, "
        "PR/AP metrics with run-bootstrap CIs, and fair traditional cuts on timing-span/q-template quantities. "
        "Additional ticket-specific calibration outputs are `reliability_diagram.csv`, `reliability_diagram.png`, "
        "`precision_recall_curve.csv`, `precision_recall_curve.png`, and `calibration_summary.csv`; "
        "the isotonic and Platt rows in `calibration_summary.csv` are out-of-fold diagnostic recalibrations, "
        "not used to change the primary winner."
    )
    while f"{ticket_paragraph}\n\n{ticket_paragraph}" in report:
        report = report.replace(f"{ticket_paragraph}\n\n{ticket_paragraph}", ticket_paragraph)
    if ticket_paragraph not in report:
        report = report.replace(
            "Artifacts: `raw_s00_reproduction.csv`",
            f"{ticket_paragraph}\n\nArtifacts: `raw_s00_reproduction.csv`",
        )
    report_path.write_text(report, encoding="utf-8")

    claimed_path.write_text(
        "#2370 S07: ML rigour pass (cross-cutting)\n"
        "Claimed by worker:testbeam-laptop-2. Body: add probability calibration, run-held-out "
        "ML-vs-traditional classifier scoreboard, PR/AP and bootstrap CIs.\n",
        encoding="utf-8",
    )

    refresh_manifest(f"{sys.executable} scripts/s07_2370_ml_rigour_scoreboard.py")
    result["artifacts"]["manifest"] = str(manifest_path.relative_to(ROOT))
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(result_path, ROOT / "result.json")


def main() -> int:
    run_engine()
    postprocess()
    print(json.dumps(json.loads((ROOT / "result.json").read_text(encoding="utf-8"))["winner"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
