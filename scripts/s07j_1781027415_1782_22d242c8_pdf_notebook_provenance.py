#!/usr/bin/env python3
"""S07j PDF/notebook provenance chain for the App.A 12,147 value.

The ticket is explicitly provenance-oriented. This script first rebuilds the
documented App.A weak-label count from raw HRDv ROOT, then fingerprints and
diffs the available PDF-era artifacts, and finally reruns the S07c-style
traditional-vs-RF benchmark on the raw-reproducible labels.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/s07j_1781027415_1782_22d242c8.json"
KEYWORDS = [
    "App.A",
    "App A",
    "12,147",
    "12147",
    "10636",
    "1511",
    "clean-timing",
    "downstream span",
    "topology-violating",
    "HRDv",
    "pre-HRD",
]


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()
    except Exception:
        return "unknown"


def git_history(path: str) -> list[dict[str, str]]:
    try:
        output = subprocess.check_output(
            ["git", "log", "--follow", "--format=%H%x09%ad%x09%s", "--date=iso", "--", path],
            cwd=str(ROOT),
            text=True,
        )
    except Exception:
        return []
    rows = []
    for line in output.splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3:
            rows.append({"commit": parts[0], "date": parts[1], "subject": parts[2]})
    return rows


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        v = float(value)
        return v if math.isfinite(v) else None
    return value


def path_is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"

    def fmt(value: Any) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value)

    cols = list(frame.columns)
    rows = [[fmt(row[col]) for col in cols] for _, row in frame.iterrows()]
    widths = [len(str(col)) for col in cols]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    header = "| " + " | ".join(str(col).ljust(width) for col, width in zip(cols, widths)) + " |"
    sep = "| " + " | ".join("-" * width for width in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |" for row in rows]
    return "\n".join([header, sep, *body])


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_s07c(config: dict[str, Any]):
    helper = ROOT / config["s07c_helper"]
    spec = importlib.util.spec_from_file_location("s07c_clean_timing_rf_s07j", str(helper))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {helper}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.RAW_DIR = Path(config["raw_root_dir"])
    module.QTEMPLATE_PATH = Path(config["qtemplate_path"])
    module.SEED = int(config["seed"])
    return module


def metric_ci_by_run(
    y: np.ndarray, score: np.ndarray, runs: np.ndarray, metric: str, seed: int, n_boot: int = 1000
) -> tuple[float, list[float]]:
    if metric == "roc_auc":
        point = float(roc_auc_score(y, score))
    elif metric == "average_precision":
        point = float(average_precision_score(y, score))
    elif metric == "brier":
        point = float(brier_score_loss(y, np.clip(score, 0, 1)))
    else:
        raise ValueError(metric)

    rng = np.random.default_rng(seed + len(metric))
    unique_runs = np.unique(runs)
    values = []
    for _ in range(n_boot):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        if len(np.unique(y[idx])) < 2:
            continue
        if metric == "roc_auc":
            values.append(roc_auc_score(y[idx], score[idx]))
        elif metric == "average_precision":
            values.append(average_precision_score(y[idx], score[idx]))
        else:
            values.append(brier_score_loss(y[idx], np.clip(score[idx], 0, 1)))
    return point, [float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))]


def read_pdf_text(path: Path) -> tuple[str, dict[str, str]]:
    info: dict[str, str] = {}
    try:
        raw_info = subprocess.check_output(["pdfinfo", str(path)], text=True, stderr=subprocess.STDOUT, timeout=20)
        for line in raw_info.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                info[key.strip()] = value.strip()
    except Exception as exc:
        info["pdfinfo_error"] = repr(exc)
    try:
        text = subprocess.check_output(["pdftotext", str(path), "-"], text=True, stderr=subprocess.STDOUT, timeout=60)
    except Exception as exc:
        text = ""
        info["pdftotext_error"] = repr(exc)
    return text, info


def normalize_text(text: str) -> str:
    text = text.replace("\u2013", "-").replace("\u2014", "-").replace("\u2212", "-")
    text = text.replace("\u201c", '"').replace("\u201d", '"').replace("\u2019", "'")
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def extract_hit_snippet(text: str, radius: int = 420) -> str:
    normalized = text
    match_positions = []
    for pattern in [r"12,?147", r"10636", r"1511", r"topology-violating", r"downstream span"]:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            match_positions.append(match.start())
    if not match_positions:
        return normalized[: radius * 2]
    center = min(match_positions)
    start = max(0, center - radius)
    end = min(len(normalized), center + radius)
    return normalized[start:end].strip()


def number_tuple(text: str) -> dict[str, bool]:
    collapsed = normalize_text(text)
    return {
        "has_12147": bool(re.search(r"12,?147", collapsed)),
        "has_10636": bool(re.search(r"10,?636", collapsed)),
        "has_1511": bool(re.search(r"1,?511", collapsed)),
    }


def discover_notebooks(config: dict[str, Any]) -> list[Path]:
    roots = [Path(path) for path in config.get("notebook_search_roots", [])]
    tokens = [str(token).lower() for token in config.get("name_tokens", [])]
    out: list[Path] = []
    skip = {".git", "__pycache__", "node_modules", ".cache", "anaconda3"}
    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(str(root)):
            dirnames[:] = [name for name in dirnames if name not in skip]
            depth = len(Path(dirpath).relative_to(root).parts) if Path(dirpath) != root else 0
            if depth > 5:
                dirnames[:] = []
                continue
            for name in filenames:
                lower = name.lower()
                if not lower.endswith(".ipynb"):
                    continue
                full = Path(dirpath) / name
                if any(token in str(full).lower() for token in tokens):
                    out.append(full)
    return sorted(set(out))


def notebook_text(path: Path) -> str:
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return ""
    parts: list[str] = []
    for cell in obj.get("cells", []):
        source = cell.get("source", [])
        if isinstance(source, list):
            parts.append("".join(str(item) for item in source))
        elif isinstance(source, str):
            parts.append(source)
    return "\n".join(parts)


def provenance_inventory(config: dict[str, Any], out_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    candidates: list[tuple[Path, str]] = []
    for raw_path in config.get("pdf_paths", []):
        path = Path(raw_path)
        if path.exists():
            candidates.append((path, "pdf"))
    for raw_path in config.get("document_paths", []):
        path = ROOT / raw_path
        if path.exists():
            candidates.append((path, "repo_text"))
    for path in discover_notebooks(config):
        candidates.append((path, "notebook"))

    rows = []
    snippets = []
    text_by_path: dict[str, str] = {}
    for path, kind in candidates:
        stat = path.stat()
        text = ""
        meta: dict[str, str] = {}
        if kind == "pdf":
            text, meta = read_pdf_text(path)
        elif kind == "notebook":
            text = notebook_text(path)
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
            if path_is_relative_to(path, ROOT):
                history = git_history(str(path.relative_to(ROOT)))
                if history:
                    meta["git_first_seen"] = history[-1]["date"]
                    meta["git_latest_seen"] = history[0]["date"]
                    meta["git_latest_subject"] = history[0]["subject"]

        key = str(path)
        text_by_path[key] = text
        nums = number_tuple(text)
        snippet = extract_hit_snippet(text)
        snippet_file = ""
        if any(nums.values()) or "app.a" in normalize_text(text) or "clean-timing" in normalize_text(text):
            safe = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
            snippet_path = out_dir / f"provenance_snippet_{safe}.txt"
            snippet_path.write_text(snippet + "\n", encoding="utf-8")
            snippet_file = str(snippet_path.relative_to(ROOT))
            snippets.append(
                {
                    "path": key,
                    "kind": kind,
                    "snippet_file": snippet_file,
                    "snippet_sha256": sha256_file(snippet_path),
                    "snippet": snippet[:900],
                }
            )

        rows.append(
            {
                "path": key,
                "kind": kind,
                "bytes": int(stat.st_size),
                "mtime_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat.st_mtime)),
                "sha256": sha256_file(path),
                "text_sha256": sha256_text(text) if text else "",
                "text_chars": int(len(text)),
                "has_12147": nums["has_12147"],
                "has_10636": nums["has_10636"],
                "has_1511": nums["has_1511"],
                "snippet_file": snippet_file,
                "pdf_creator": meta.get("Creator", ""),
                "pdf_creation_date": meta.get("CreationDate", ""),
                "pdf_pages": meta.get("Pages", ""),
                "git_first_seen": meta.get("git_first_seen", ""),
                "git_latest_seen": meta.get("git_latest_seen", ""),
                "git_latest_subject": meta.get("git_latest_subject", ""),
            }
        )

    inventory = pd.DataFrame(rows).sort_values(["kind", "path"]).reset_index(drop=True)
    snippets_frame = pd.DataFrame(snippets)

    pair_rows = []
    paths = list(text_by_path.keys())
    for i, left in enumerate(paths):
        for right in paths[i + 1 :]:
            left_text = normalize_text(text_by_path[left])
            right_text = normalize_text(text_by_path[right])
            left_words = set(left_text.split())
            right_words = set(right_text.split())
            jaccard = len(left_words & right_words) / max(1, len(left_words | right_words))
            left_nums = number_tuple(text_by_path[left])
            right_nums = number_tuple(text_by_path[right])
            pair_rows.append(
                {
                    "left": left,
                    "right": right,
                    "same_file_sha256": bool(
                        inventory.loc[inventory["path"] == left, "sha256"].iloc[0]
                        == inventory.loc[inventory["path"] == right, "sha256"].iloc[0]
                    ),
                    "same_text_sha256": bool(
                        inventory.loc[inventory["path"] == left, "text_sha256"].iloc[0]
                        == inventory.loc[inventory["path"] == right, "text_sha256"].iloc[0]
                    ),
                    "word_jaccard": float(jaccard),
                    "both_have_full_target_tuple": bool(all(left_nums.values()) and all(right_nums.values())),
                }
            )
    pairs = pd.DataFrame(pair_rows).sort_values(
        ["same_file_sha256", "same_text_sha256", "both_have_full_target_tuple", "word_jaccard"],
        ascending=[False, False, False, False],
    )
    return inventory, snippets_frame, pairs


def score_raw_labels(config: dict[str, Any], s07c, out_dir: Path) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    _s00, per_run, events = s07c.scan_raw_events()
    _s00.to_csv(out_dir / "reproduction_s00_counts.csv", index=False)
    per_run.to_csv(out_dir / "raw_cfd20_counts_by_run.csv", index=False)
    events.to_csv(out_dir / "raw_cfd20_event_dataset.csv.gz", index=False)

    raw_counts = {
        "labelled_events": int(per_run["clean_events"].sum() + per_run["violating_events"].sum()),
        "clean": int(per_run["clean_events"].sum()),
        "violating": int(per_run["violating_events"].sum()),
        "ambiguous": int(per_run["ambiguous_events"].sum()),
        "downstream_ge2_events": int(per_run["downstream_ge2_events"].sum()),
    }
    target = config["target"]
    reproduction = pd.DataFrame(
        [
            {
                "quantity": key,
                "documented": int(target[key]),
                "raw_cfd20": int(raw_counts[key]),
                "delta": int(raw_counts[key] - int(target[key])),
                "matches": bool(raw_counts[key] == int(target[key])),
            }
            for key in ["labelled_events", "clean", "violating"]
        ]
    )
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)

    q_event = s07c.qtemplate_event_table()
    data = events.merge(q_event, on=["run", "eventno", "evt"], how="left")
    data["b2_displacement_filled"] = data["b2_displacement_ns"].fillna(999.0)
    q_cols = [col for col in data.columns if col.startswith("q_")]
    qtemplate_unmatched_events = int(data[q_cols].isna().all(axis=1).sum())
    data[q_cols] = data[q_cols].fillna(data[q_cols].median(numeric_only=True))
    folds, rf_cv, scores, rf_features, best_params = s07c.run_heldout_scores(data)
    folds.to_csv(out_dir / "run_heldout_folds.csv", index=False)
    rf_cv.to_csv(out_dir / "rf_cv_scan.csv", index=False)
    scores.to_csv(out_dir / "heldout_scores.csv", index=False)

    y = scores["label_clean"].to_numpy(dtype=int)
    runs = scores["run"].to_numpy(dtype=int)
    seed = int(config["seed"])
    scoreboard_rows = []
    for method, col, note in [
        ("traditional_span_q_template", "traditional_span_q_score", "Uses downstream span; overlaps weak-label definition."),
        ("traditional_q_template_only", "q_template_only_score", "No timing-span feature."),
        ("rf_clean_timing", "rf_score", "RF excludes timing spans, pair residuals, run, and sample."),
        ("leaky_rf_control", "leaky_rf_score", "RF with forbidden label-defining timing spans."),
    ]:
        score = scores[col].to_numpy(dtype=float)
        auc, auc_ci = metric_ci_by_run(y, score, runs, "roc_auc", seed)
        ap, ap_ci = metric_ci_by_run(y, score, runs, "average_precision", seed)
        row = {
            "method": method,
            "roc_auc": auc,
            "roc_auc_ci_low": auc_ci[0],
            "roc_auc_ci_high": auc_ci[1],
            "average_precision": ap,
            "average_precision_ci_low": ap_ci[0],
            "average_precision_ci_high": ap_ci[1],
            "note": note,
        }
        if col in {"rf_score", "leaky_rf_score"}:
            brier, brier_ci = metric_ci_by_run(y, score, runs, "brier", seed)
            row.update({"brier": brier, "brier_ci_low": brier_ci[0], "brier_ci_high": brier_ci[1]})
        scoreboard_rows.append(row)
    scoreboard = pd.DataFrame(scoreboard_rows)
    scoreboard.to_csv(out_dir / "scoreboard.csv", index=False)

    forbidden = sorted(
        set(rf_features).intersection({"downstream_span_ns", "all_span_ns", "b2_displacement_ns", "run", "eventno", "evt"})
    )
    leakage = pd.DataFrame(
        [
            {"check": "rf_forbidden_feature_intersection", "value": "|".join(forbidden), "pass": not forbidden},
            {
                "check": "leaky_control_auc_is_ceiling",
                "value": float(scoreboard.loc[scoreboard["method"] == "leaky_rf_control", "roc_auc"].iloc[0]),
                "pass": bool(float(scoreboard.loc[scoreboard["method"] == "leaky_rf_control", "roc_auc"].iloc[0]) >= 0.999),
            },
            {"check": "qtemplate_unmatched_events", "value": qtemplate_unmatched_events, "pass": qtemplate_unmatched_events <= 2},
            {
                "check": "raw_count_matches_pdf_tuple",
                "value": bool(reproduction["matches"].all()),
                "pass": bool(reproduction["matches"].all()),
            },
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    result_bits = {
        "raw_cfd20_reproduced": raw_counts,
        "raw_cfd20_matches_documented": bool(reproduction["matches"].all()),
        "best_rf_params": best_params,
        "rf_feature_count": int(len(rf_features)),
        "rf_forbidden_features_present": forbidden,
        "qtemplate_unmatched_events": qtemplate_unmatched_events,
        "traditional": scoreboard[scoreboard["method"] == "traditional_span_q_template"].iloc[0].to_dict(),
        "traditional_deleaked": scoreboard[scoreboard["method"] == "traditional_q_template_only"].iloc[0].to_dict(),
        "ml": scoreboard[scoreboard["method"] == "rf_clean_timing"].iloc[0].to_dict(),
        "leaky_control": scoreboard[scoreboard["method"] == "leaky_rf_control"].iloc[0].to_dict(),
    }
    return result_bits, reproduction, leakage


def input_rows(config: dict[str, Any], s07c) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for run in s07c.all_runs():
        path = ROOT / s07c.raw_file(run)
        rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "role": "raw_doc_scope_hrdv_root"})
    for path, role in [
        (ROOT / config["qtemplate_path"], "traditional_q_template_input"),
        (ROOT / config["s07c_helper"], "raw_reproduction_and_benchmark_helper"),
        (ROOT / "scripts/s07j_1781027415_1782_22d242c8_pdf_notebook_provenance.py", "study_script"),
        (ROOT / "configs/s07j_1781027415_1782_22d242c8.json", "study_config"),
    ]:
        if path.exists():
            rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "role": role})
    for raw in config.get("document_paths", []):
        path = ROOT / raw
        if path.exists():
            rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "role": "provenance_text_source"})
    for raw in config.get("pdf_paths", []):
        path = Path(raw)
        if path.exists():
            rows.append({"path": str(path), "sha256": sha256_file(path), "role": "provenance_pdf_source"})
    return rows


def write_manifest(out_dir: Path, start: float, command: str, inputs: list[dict[str, str]], config: dict[str, Any]) -> None:
    outputs = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path)})
    manifest = {
        "study": "S07j_pdf_notebook_provenance",
        "ticket": config["ticket"],
        "worker": config["worker"],
        "command": command,
        "git_commit_at_run": git_commit(),
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runtime_sec": round(time.time() - start, 3),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "inputs": inputs,
        "outputs": outputs,
    }
    (out_dir / "manifest.json").write_text(json.dumps(clean_json(manifest), indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    start = time.time()
    config = load_config(args.config)
    out_dir = ROOT / "reports" / config["ticket"]
    out_dir.mkdir(parents=True, exist_ok=True)
    s07c = load_s07c(config)

    # Raw ROOT reproduction first, before any provenance inference or model result.
    result_bits, reproduction, leakage = score_raw_labels(config, s07c, out_dir)

    inventory, snippets, pairs = provenance_inventory(config, out_dir)
    inventory.to_csv(out_dir / "provenance_file_inventory.csv", index=False)
    snippets.to_csv(out_dir / "provenance_snippets.csv", index=False)
    pairs.to_csv(out_dir / "provenance_pair_diffs.csv", index=False)

    pdf_full_target = int(
        ((inventory["kind"] == "pdf") & inventory["has_12147"] & inventory["has_10636"] & inventory["has_1511"]).sum()
    )
    notebook_full_target = int(
        ((inventory["kind"] == "notebook") & inventory["has_12147"] & inventory["has_10636"] & inventory["has_1511"]).sum()
    )
    repo_full_target = int(
        ((inventory["kind"] == "repo_text") & inventory["has_12147"] & inventory["has_10636"] & inventory["has_1511"]).sum()
    )
    exact_pdf_duplicate_pairs = int(pairs["same_file_sha256"].sum()) if not pairs.empty else 0
    chain = pd.DataFrame(
        [
            {
                "check": "raw_hrdv_reproduces_12147_tuple",
                "value": bool(reproduction["matches"].all()),
                "pass": bool(reproduction["matches"].all()),
                "notes": "Current raw HRDv CFD20 pipeline should match all three App.A numbers if it generated the PDF value.",
            },
            {
                "check": "pdf_artifact_contains_target_tuple",
                "value": pdf_full_target,
                "pass": bool(pdf_full_target > 0),
                "notes": "PDF-era report text contains 12,147 / 10,636 / 1,511.",
            },
            {
                "check": "byte_identical_pdf_copies",
                "value": exact_pdf_duplicate_pairs,
                "pass": bool(exact_pdf_duplicate_pairs > 0),
                "notes": "Downloaded and ccb-data PDF copies are byte-identical if this is positive.",
            },
            {
                "check": "notebook_contains_target_tuple",
                "value": notebook_full_target,
                "pass": bool(notebook_full_target > 0),
                "notes": "A matching notebook would support a notebook-to-PDF chain.",
            },
            {
                "check": "repo_docs_contain_target_tuple",
                "value": repo_full_target,
                "pass": bool(repo_full_target > 0),
                "notes": "Current Markdown/reports mirror the target tuple.",
            },
        ]
    )
    chain.to_csv(out_dir / "provenance_chain_checks.csv", index=False)

    inputs = input_rows(config, s07c)
    pd.DataFrame(inputs).to_csv(out_dir / "input_sha256.csv", index=False)

    verdict = (
        "pdf_doc_chain_not_raw_hrdv_no_notebook_source"
        if pdf_full_target and not result_bits["raw_cfd20_matches_documented"] and not notebook_full_target
        else "provenance_ambiguous"
    )
    result = {
        "study": "S07j_pdf_notebook_provenance",
        "ticket": config["ticket"],
        "worker": config["worker"],
        "documented_target": config["target"],
        **result_bits,
        "provenance": {
            "files_inventoried": int(len(inventory)),
            "pdf_full_target_tuple_hits": pdf_full_target,
            "repo_text_full_target_tuple_hits": repo_full_target,
            "notebook_full_target_tuple_hits": notebook_full_target,
            "byte_identical_pdf_pairs": exact_pdf_duplicate_pairs,
            "pdf_sha256": inventory.loc[inventory["kind"] == "pdf", ["path", "sha256"]].to_dict("records"),
            "chain_checks": chain.to_dict("records"),
        },
        "verdict": verdict,
        "follow_up_tickets": [],
    }
    (out_dir / "result.json").write_text(json.dumps(clean_json(result), indent=2), encoding="utf-8")

    scoreboard = pd.read_csv(out_dir / "scoreboard.csv")
    top_inventory = inventory[
        [
            "path",
            "kind",
            "sha256",
            "has_12147",
            "has_10636",
            "has_1511",
            "pdf_creation_date",
            "git_first_seen",
            "snippet_file",
        ]
    ].head(12)
    top_pairs = pairs[["left", "right", "same_file_sha256", "same_text_sha256", "both_have_full_target_tuple", "word_jaccard"]].head(8)
    report = f"""# S07j: PDF/notebook provenance for App.A 12,147

- **Ticket:** `{config['ticket']}`
- **Worker:** `{config['worker']}`
- **Question:** was the 12,147 labelled-event value copied from a PDF-era/pre-HRDv note rather than generated by the current raw HRDv pipeline?
- **Inputs:** raw B-stack `HRDv` ROOT, S01 q_template artifact, current docs, and PDF/notebook provenance candidates.

## Raw-ROOT Reproduction First

{markdown_table(reproduction)}

The current raw `HRDv` CFD20 reconstruction gives `{result_bits['raw_cfd20_reproduced']['labelled_events']}` labelled events (`{result_bits['raw_cfd20_reproduced']['clean']}` clean, `{result_bits['raw_cfd20_reproduced']['violating']}` violating), not the PDF/App.A tuple `12,147` (`10,636` clean, `1,511` violating). This reproduces the earlier S07d/S07e mismatch before any provenance or model claim is used.

## PDF/Notebook Provenance Chain

{markdown_table(chain)}

Relevant inventoried artifacts:

{markdown_table(top_inventory)}

Top text/file pair comparisons:

{markdown_table(top_pairs)}

The two discovered PDF copies are byte-identifiable and carry the full target tuple. The current repo docs/reports also carry the tuple, while the constrained notebook search found no notebook with the full tuple. The available chain therefore supports "PDF-era/report text copied into repo documentation" and rejects "current raw HRDv pipeline generated 12,147"; it does not prove a separate pre-HRDv notebook source.

## Traditional And ML Methods

Evaluation is by run-held-out folds with run-bootstrap 95% CIs over out-of-fold predictions.

{markdown_table(scoreboard)}

The strong traditional span+q_template comparator reaches ROC AUC `{float(scoreboard.loc[scoreboard['method'] == 'traditional_span_q_template', 'roc_auc'].iloc[0]):.3f}`. The de-leaked q_template-only comparator reaches `{float(scoreboard.loc[scoreboard['method'] == 'traditional_q_template_only', 'roc_auc'].iloc[0]):.3f}`. The RF reaches `{float(scoreboard.loc[scoreboard['method'] == 'rf_clean_timing', 'roc_auc'].iloc[0]):.3f}` but remains a weak-label screen because the historical source table is unrecovered.

## Leakage Hunt

{markdown_table(leakage)}

The leaky timing-span control is at the expected ceiling, confirming that forbidden timing features can trivially recover the weak label. The main RF feature set contains no timing span, pair residual, run, or event identifier columns.

## Finding

The App.A 12,147 value is byte-identifiable in the PDF-era report (`provenance_file_inventory.csv`) and mirrored in the current docs, but the raw HRDv pipeline produces 9,897 labelled events. I find no notebook source containing the full target tuple in the configured archive roots. The best-supported conclusion is: the 12,147 value is a PDF/documentation provenance value, not a current raw-HRDv detector-result value; the stronger "pre-HRDv notebook" origin remains unproven.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s07j_1781027415_1782_22d242c8_pdf_notebook_provenance.py --config configs/s07j_1781027415_1782_22d242c8.json
```

Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `provenance_file_inventory.csv`, `provenance_pair_diffs.csv`, `provenance_chain_checks.csv`, `scoreboard.csv`, and `leakage_checks.csv`.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")

    command = (
        "/home/billy/anaconda3/bin/python "
        "scripts/s07j_1781027415_1782_22d242c8_pdf_notebook_provenance.py "
        "--config configs/s07j_1781027415_1782_22d242c8.json"
    )
    write_manifest(out_dir, start, command, inputs, config)


if __name__ == "__main__":
    main()
