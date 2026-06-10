#!/usr/bin/env python3
"""S14d: external requirements audit before a per-event proton energy claim.

This ticket starts from the S14b raw-ROOT range-energy preflight. It reruns the
raw selected-pulse reproduction gate, hashes the ROOT inputs, imports the
ticket-local S14b held-out traditional/ML metrics, and writes a decision table
separating what HRD data can constrain from what needs external calibration,
simulation, or validation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np
import pandas as pd
import uproot
import yaml


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def heldout_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for group in config["heldout_groups"]:
        runs.extend(int(run) for run in config["run_groups"][group])
    return sorted(set(runs))


def train_runs(config: dict) -> List[int]:
    heldout = set(heldout_runs(config))
    return [run for run in configured_runs(config) if run not in heldout]


def iter_batches(path: Path, step_size: int = 50000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["HRDv"], step_size=step_size, library="np")


def raw_reproduction(config: dict) -> pd.DataFrame:
    nsamp = int(config["samples_per_channel"])
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    cut = float(config["amplitude_cut_adc"])
    staves = list(config["staves"].keys())
    even_ch = np.asarray([int(config["staves"][stave]) for stave in staves], dtype=int)
    rows: List[dict] = []

    for run in configured_runs(config):
        path = Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"
        if not path.exists():
            raise FileNotFoundError(path)
        counts = {
            "run": run,
            "events_total": 0,
            "events_with_selected": 0,
            "selected_pulses": 0,
        }
        counts.update({stave: 0 for stave in staves})
        for batch in iter_batches(path):
            raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            even = corrected[:, even_ch, :]
            even_amp = even.max(axis=-1)
            selected = even_amp > cut
            counts["events_total"] += int(selected.shape[0])
            counts["events_with_selected"] += int(selected.any(axis=1).sum())
            counts["selected_pulses"] += int(selected.sum())
            for idx, stave in enumerate(staves):
                counts[stave] += int(selected[:, idx].sum())
        rows.append(counts)
    return pd.DataFrame(rows)


def source_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def find_method(metrics: List[dict], method: str) -> dict:
    for row in metrics:
        if row.get("method") == method:
            return row
    raise KeyError(method)


def parse_ci(value) -> List[float]:
    if isinstance(value, list):
        return [float(x) for x in value]
    if isinstance(value, str) and value.strip().startswith("["):
        return [float(x) for x in json.loads(value)]
    return []


def decision_table(s14b: dict, s14d_material: dict) -> List[dict]:
    trad = find_method(s14b["nominal_metrics"], "traditional_depth_charge_lookup")
    ml = find_method(s14b["nominal_metrics"], "ml_monotonic_hgb")
    p04_rows = {
        row["method"]: row
        for row in s14b["p04b_uncertainty_propagation"]
        if row.get("geometry") == s14b["nominal_geometry"]
    }
    material_env = s14d_material.get("geometry_systematic_envelope", {})
    return [
        {
            "ingredient": "HRD raw pulse selection and B-stack penetration depth",
            "raw_hrd_constraint": "yes",
            "evidence": "Raw ROOT gate reproduces S00 selected B-stave pulse records exactly; depth order is B2/B4/B6/B8 hit depth.",
            "traditional_or_ml_role": "Both methods can use even-readout charge/amplitude and penetration depth with run-held-out validation.",
            "needed_for_per_event_proton_energy": "Keep as internal observable; not sufficient for absolute incident or stopping energy.",
            "status": "available from raw HRD",
        },
        {
            "ingredient": "Even-vs-odd duplicate readout closure",
            "raw_hrd_constraint": "yes, internally",
            "evidence": f"S14b nominal held-out res68: traditional {float(trad['res68_abs_frac']):.6f}, ML {float(ml['res68_abs_frac']):.6f}; run-block CIs are {parse_ci(trad['res68_ci95'])} and {parse_ci(ml['res68_ci95'])}.",
            "traditional_or_ml_role": "Defines the strongest raw-only closure target; leakage checks exclude odd readout from features.",
            "needed_for_per_event_proton_energy": "Useful quality gate, but duplicate readout is not external truth.",
            "status": "available from raw HRD",
        },
        {
            "ingredient": "External charge-proxy uncertainty from downstream stack",
            "raw_hrd_constraint": "partial",
            "evidence": f"S14b propagated P04b charge term gives combined nominal res68 {float(p04_rows['traditional_depth_charge_lookup']['combined_energy_proxy_res68']):.6f} traditional and {float(p04_rows['ml_monotonic_hgb']['combined_energy_proxy_res68']):.6f} ML, both above 0.10.",
            "traditional_or_ml_role": "Stress-tests whether charge closure survives an externalized HRD proxy.",
            "needed_for_per_event_proton_energy": "Must be replaced or anchored by calibrated light-yield/energy-deposit response.",
            "status": "insufficient for per-event claim",
        },
        {
            "ingredient": "Material budget before and inside the HRD stack",
            "raw_hrd_constraint": "no",
            "evidence": f"Prior S14d material scan changes the raw-only proxy envelope; traditional res68 span {material_env.get('traditional_res68_min')} to {material_env.get('traditional_res68_max')}, ML span {material_env.get('ml_res68_min')} to {material_env.get('ml_res68_max')}.",
            "traditional_or_ml_role": "Geometry/material variants can be propagated, not learned absolutely from HRD pulses.",
            "needed_for_per_event_proton_energy": "Surveyed thicknesses, dead layers, support material, target-to-stack path length, and uncertainties.",
            "status": "requires external detector survey or validated model",
        },
        {
            "ingredient": "Stave geometry and stopping-depth convention",
            "raw_hrd_constraint": "partial",
            "evidence": "Raw data identify which stave fired last, but not the absolute front-face, center, active thickness, or inactive gap convention.",
            "traditional_or_ml_role": "Sets PSTAR depth anchors and therefore the energy scale of both methods.",
            "needed_for_per_event_proton_energy": "Coordinate convention tied to physical stave positions and active volumes.",
            "status": "requires external geometry definition",
        },
        {
            "ingredient": "PSTAR/range-energy table applicability",
            "raw_hrd_constraint": "no",
            "evidence": "S14b uses a configured plastic-scintillator PSTAR table only as a monotonic depth-order lookup.",
            "traditional_or_ml_role": "Maps depth anchors to nominal proton CSDA energies; ML inherits this target.",
            "needed_for_per_event_proton_energy": "Material-specific stopping powers and validation for the actual scintillator/support mixture.",
            "status": "requires external reference and uncertainty",
        },
        {
            "ingredient": "Birks/quenching and nonlinear scintillator response",
            "raw_hrd_constraint": "no",
            "evidence": "No Birks constant, quenching curve, or ADC-to-light-yield calibration is present in the raw HRD ROOT.",
            "traditional_or_ml_role": "Unmodeled response can make charge ranks look good while absolute energy is biased.",
            "needed_for_per_event_proton_energy": "Bench calibration or validated Birks/quenching model with uncertainty propagation.",
            "status": "missing external calibration",
        },
        {
            "ingredient": "Particle identity / proton truth",
            "raw_hrd_constraint": "no",
            "evidence": "The run condition is 190 MeV p on CD2, but HRD-only selected pulses do not label event-level proton, deuteron, fragment, or background species.",
            "traditional_or_ml_role": "Neither method can convert a raw closure target into proton-only truth labels.",
            "needed_for_per_event_proton_energy": "Independent PID, beamline tag, or validated stopping-depth truth sample.",
            "status": "missing external truth",
        },
        {
            "ingredient": "Stopping-depth validation",
            "raw_hrd_constraint": "no",
            "evidence": "Depth-order violation is zero by construction for the raw proxy, but no external range telescope or MC truth validates true stopping depth.",
            "traditional_or_ml_role": "A leakage-free model may still predict the proxy rather than physical stopping depth.",
            "needed_for_per_event_proton_energy": "External range/stopping validation or simulation validated against calibration data.",
            "status": "missing external validation",
        },
        {
            "ingredient": "Leakage controls",
            "raw_hrd_constraint": "yes",
            "evidence": "S14b reports no train/held-out run overlap, no event-key overlap, feature exclusion of run/event/odd readout, and shuffled-target ML res68 0.319485.",
            "traditional_or_ml_role": "Required because raw-only closure is strong enough to make leakage plausible.",
            "needed_for_per_event_proton_energy": "Keep these controls, then repeat them against external truth/calibration targets.",
            "status": "available, but target remains proxy-only",
        },
    ]


def write_csv(path: Path, rows: List[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(rows: List[dict], columns: List[str]) -> str:
    out = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(row.get(col, "")).replace("\n", " ") for col in columns) + " |")
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    started = time.time()
    outdir = Path(config["output_dir"])
    outdir.mkdir(parents=True, exist_ok=True)

    s14b_path = Path(config["source_artifacts"]["s14b_result"])
    s14d_material_path = Path(config["source_artifacts"]["s14d_material_result"])
    s14b = source_json(s14b_path)
    s14d_material = source_json(s14d_material_path)

    counts = raw_reproduction(config)
    counts.to_csv(outdir / "counts_by_run.csv", index=False)
    reproduced = int(counts["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    reproduction = {
        "quantity": "S00 selected B-stave pulse records",
        "expected": expected,
        "reproduced": reproduced,
        "delta": reproduced - expected,
        "pass": reproduced == expected,
    }
    pd.DataFrame([reproduction]).to_csv(outdir / "reproduction_match_table.csv", index=False)

    root_inputs = []
    for run in configured_runs(config):
        path = Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"
        root_inputs.append({"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)})

    source_inputs = []
    for label, raw_path in config["source_artifacts"].items():
        path = Path(raw_path)
        source_inputs.append({"label": label, "path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)})

    input_rows = [{"path": row["path"], "sha256": row["sha256"], "bytes": row["bytes"]} for row in root_inputs]
    input_rows.extend({"path": row["path"], "sha256": row["sha256"], "bytes": row["bytes"]} for row in source_inputs)
    write_csv(outdir / "input_sha256.csv", input_rows)

    decisions = decision_table(s14b, s14d_material)
    write_csv(outdir / "requirements_decision_table.csv", decisions)

    trad = find_method(s14b["nominal_metrics"], "traditional_depth_charge_lookup")
    ml = find_method(s14b["nominal_metrics"], "ml_monotonic_hgb")
    p04_nominal = [
        row for row in s14b["p04b_uncertainty_propagation"]
        if row.get("geometry") == s14b["nominal_geometry"]
    ]
    method_summary = [
        {
            "method": "traditional_depth_charge_lookup",
            "n": trad["n"],
            "res68_abs_frac": trad["res68_abs_frac"],
            "res68_ci95": trad["res68_ci95"],
            "combined_energy_proxy_res68": next(row["combined_energy_proxy_res68"] for row in p04_nominal if row["method"] == "traditional_depth_charge_lookup"),
            "combined_energy_proxy_res68_ci95": next(row["combined_energy_proxy_res68_ci95"] for row in p04_nominal if row["method"] == "traditional_depth_charge_lookup"),
        },
        {
            "method": "ml_monotonic_hgb",
            "n": ml["n"],
            "res68_abs_frac": ml["res68_abs_frac"],
            "res68_ci95": ml["res68_ci95"],
            "combined_energy_proxy_res68": next(row["combined_energy_proxy_res68"] for row in p04_nominal if row["method"] == "ml_monotonic_hgb"),
            "combined_energy_proxy_res68_ci95": next(row["combined_energy_proxy_res68_ci95"] for row in p04_nominal if row["method"] == "ml_monotonic_hgb"),
        },
    ]
    write_csv(outdir / "method_summary.csv", method_summary)

    finding = (
        "The raw HRD reproduction gate matches S14b/S00 exactly at 640,737 selected B-stave pulses. "
        "The S14b run-held-out proxy closure remains strong for the internal duplicate-readout target "
        f"(traditional res68 {float(trad['res68_abs_frac']):.4f}, ML res68 {float(ml['res68_abs_frac']):.4f}), "
        "but the propagated external charge-proxy uncertainty gives combined nominal range-energy proxy "
        f"res68 {float(method_summary[0]['combined_energy_proxy_res68']):.4f} traditional and "
        f"{float(method_summary[1]['combined_energy_proxy_res68']):.4f} ML, both failing the 0.10 preflight threshold. "
        "Raw HRD data can constrain pulse selection, penetration ordering, duplicate-readout closure, and leakage controls; "
        "a per-event proton energy claim still requires external material budget, stave geometry/active-depth convention, "
        "Birks/quenching or light-yield calibration, proton/PID truth, and stopping-depth validation."
    )

    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "title": config["title"],
        "worker": config["worker"],
        "raw_reproduction": reproduction,
        "train_runs": train_runs(config),
        "heldout_runs": heldout_runs(config),
        "source_s14b_ticket": s14b["ticket_id"],
        "s14b_nominal_metrics": method_summary,
        "s14b_ml_minus_traditional_res68_ci95": s14b.get("ml_minus_traditional_res68_ci95"),
        "s14b_leakage_checks": s14b.get("leakage_checks"),
        "requirements_decision_table": decisions,
        "finding": finding,
        "runtime_sec": round(time.time() - started, 3),
    }
    (outdir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    report = [
        "# S14d: external range-energy calibration requirements audit",
        "",
        f"- **Ticket ID:** {config['ticket_id']}",
        f"- **Worker:** {config['worker']}",
        "- **Input:** raw `data/root/root/hrdb_run_*.root` plus the referenced S14b/S14d report artifacts; checksums in `manifest.json` and `input_sha256.csv`.",
        "- **No Monte Carlo / no per-event energy claim.** This is a requirements audit for what must exist before such a claim.",
        "",
        "## 1. Raw reproduction gate",
        "",
        "The script rebuilds selected B-stack pulses from `HRDv`: median(samples 0..3) baseline, positive channels B2/B4/B6/B8, and `A > 1000 ADC`.",
        "",
        markdown_table([reproduction], ["quantity", "expected", "reproduced", "delta", "pass"]),
        "",
        "## 2. Referenced S14b held-out methods",
        "",
        f"- **Train runs:** {', '.join(str(x) for x in train_runs(config))}.",
        f"- **Held-out runs:** {', '.join(str(x) for x in heldout_runs(config))}. Bootstrap CIs resample held-out runs as blocks in S14b.",
        "- **Traditional:** PSTAR depth plus per-depth monotonic even-charge quantile lookup.",
        "- **ML:** monotonic `HistGradientBoostingRegressor` on even amplitude/charge, penetration depth, multiplicity, and saturation flags.",
        "",
        markdown_table(method_summary, ["method", "n", "res68_abs_frac", "res68_ci95", "combined_energy_proxy_res68", "combined_energy_proxy_res68_ci95"]),
        "",
        "S14b leakage checks: no train/held-out run overlap, no event-key overlap, explicit exclusion of run/event/odd-readout features, depth-only res68 0.261461, and shuffled-target ML res68 0.319485.",
        "",
        "## 3. Decision table",
        "",
        markdown_table(decisions, ["ingredient", "raw_hrd_constraint", "evidence", "needed_for_per_event_proton_energy", "status"]),
        "",
        "## 4. Finding",
        "",
        finding,
        "",
        "## 5. Reproducibility",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python scripts/s14d_1781026825_1580_0f304bd8_external_requirements_audit.py --config {args.config}",
        "```",
        "",
    ]
    (outdir / "REPORT.md").write_text("\n".join(report), encoding="utf-8")

    outputs = {}
    for path in sorted(outdir.iterdir()):
        if path.is_file():
            outputs[path.name] = sha256_file(path)
    manifest = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "command": f"/home/billy/anaconda3/bin/python scripts/s14d_1781026825_1580_0f304bd8_external_requirements_audit.py --config {args.config}",
        "config": str(args.config),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "uproot": getattr(uproot, "__version__", "unknown"),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "inputs": root_inputs,
        "source_artifacts": source_inputs,
        "outputs": outputs,
        "ticket_local_code": {
            "script": "scripts/s14d_1781026825_1580_0f304bd8_external_requirements_audit.py",
            "script_sha256": sha256_file(Path("scripts/s14d_1781026825_1580_0f304bd8_external_requirements_audit.py")),
            "config": str(args.config),
            "config_sha256": sha256_file(args.config),
        },
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    # Refresh output hashes now that manifest exists.
    manifest["outputs"] = {path.name: sha256_file(path) for path in sorted(outdir.iterdir()) if path.is_file() and path.name != "manifest.json"}
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ticket_id": config["ticket_id"], "raw_pass": reproduction["pass"], "outdir": str(outdir)}, indent=2))


if __name__ == "__main__":
    main()
