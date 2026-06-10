#!/usr/bin/env python3
"""P10f automatic conditional-template claim linter.

This ticket is intentionally report-corpus only.  It does not read raw ROOT:
the object under test is the P10e report/result schema that future summary
builders should enforce before promoting any q-space conditional-template win.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import re
import subprocess
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
CONTROL_LABELS = {
    "mean_template": "mean-template control",
    "shuffled_target": "shuffled-target control",
    "train_eval_run_overlap": "train/eval run-overlap check",
    "train_eval_key_overlap": "train/eval key-overlap check",
    "no_run_event_features": "no run/event feature check",
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()
    except Exception:
        return "unknown"


def flatten_items(value: Any, prefix: str = "") -> Iterable[Tuple[str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            yield from flatten_items(child, next_prefix)
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            next_prefix = f"{prefix}[{idx}]"
            yield from flatten_items(child, next_prefix)
    else:
        yield prefix, value


def text_blob(data: Any, report_text: str = "") -> str:
    return (json.dumps(data, sort_keys=True, default=str) + "\n" + report_text).lower()


def as_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return float("nan")


def ci_high(value: Any) -> float:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return as_float(value[1])
    return float("nan")


def ci_low(value: Any) -> float:
    if isinstance(value, (list, tuple)) and len(value) >= 1:
        return as_float(value[0])
    return float("nan")


def ticket_id(data: Dict[str, Any], path: Path) -> str:
    return str(data.get("ticket_id") or data.get("ticket") or path.parent.name.split("__")[0])


def study_id(data: Dict[str, Any]) -> str:
    return str(data.get("study") or data.get("study_id") or "")


def report_text_for_result(result_path: Path) -> str:
    report = result_path.with_name("REPORT.md")
    if report.exists():
        return report.read_text(encoding="utf-8", errors="replace")
    return ""


def is_p10_or_template_report(data: Dict[str, Any], blob: str) -> bool:
    study = study_id(data).lower()
    identity = " ".join(
        [
            study,
            str(data.get("title") or "").lower(),
            str(data.get("finding") or "").lower(),
        ]
    )
    return (
        study.startswith("p10")
        or "conditional template" in identity
        or "conditional-template" in identity
    )


def extract_win_evidence(data: Dict[str, Any], blob: str) -> List[str]:
    evidence: List[str] = []

    if data.get("ml_beats_baseline") is True or data.get("ml_beats_traditional") is True:
        if "q_template" in blob or "conditional" in blob or "template" in blob:
            evidence.append("top_level_ml_beats_flag")

    trad = data.get("traditional")
    ml = data.get("ml")
    if isinstance(trad, dict) and isinstance(ml, dict):
        for key in ("q_value", "q_template_mse", "mse", "value"):
            if key in trad and key in ml and as_float(ml[key]) < as_float(trad[key]):
                if "q" in key or "template" in blob or "conditional" in blob:
                    evidence.append(f"ml_{key}_below_traditional")

    for path, value in flatten_items(data):
        leaf = path.split(".")[-1]
        if leaf in {
            "delta_conditional_minus_empirical",
            "delta_extra_trees_mse_minus_empirical",
            "delta_ml_minus_traditional",
            "delta",
        }:
            parent_path = path.rsplit(".", 1)[0] if "." in path else ""
            parent = data
            for chunk in re.split(r"\.|\[\d+\]", parent_path):
                if not chunk:
                    continue
                if isinstance(parent, dict):
                    parent = parent.get(chunk, {})
            metric_blob = json.dumps(parent, sort_keys=True, default=str).lower()
            if ("q_template" in metric_blob or "mse" in leaf or "conditional" in leaf) and as_float(value) < 0:
                high = float("nan")
                if isinstance(parent, dict):
                    high = ci_high(
                        parent.get(f"{leaf}_ci")
                        or parent.get(f"{leaf}_ci95")
                        or parent.get("delta_ci95")
                        or parent.get("delta_ci")
                    )
                if math.isnan(high) or high < 0:
                    evidence.append(path)

    for item in data.get("ml_minus_traditional_deltas", []) if isinstance(data.get("ml_minus_traditional_deltas"), list) else []:
        if not isinstance(item, dict):
            continue
        metric = str(item.get("metric", "")).lower()
        if "q_template" in metric and as_float(item.get("delta")) < 0 and ci_high(item.get("delta_ci95") or item.get("delta_ci")) < 0:
            evidence.append(f"ml_minus_traditional_deltas:{metric}")

    return sorted(set(evidence))


def promoted_claim(win_evidence: Sequence[str], blob: str, caution_terms: Sequence[str]) -> bool:
    if not win_evidence:
        return False
    return not any(term.lower() in blob for term in caution_terms)


def numeric_values_for_key(data: Any, name_pattern: str) -> List[float]:
    rx = re.compile(name_pattern)
    values = []
    for path, value in flatten_items(data):
        if rx.search(path):
            if isinstance(value, bool):
                values.append(1.0 if value else 0.0)
            else:
                val = as_float(value)
                if not math.isnan(val):
                    values.append(val)
    return values


def has_forbidden_feature_text(blob: str) -> bool:
    dirty_phrases = [
        '"uses_run_or_event_features": true',
        '"no_run_or_event_features": false',
        "forbidden_features_present\": true",
        "run/event feature failure",
    ]
    return any(phrase in blob for phrase in dirty_phrases)


def control_status(data: Dict[str, Any], blob: str) -> Tuple[Dict[str, bool], Dict[str, bool], List[str]]:
    statuses = {
        "mean_template": ("mean_template_mse" in blob or "mean template" in blob or "mean-template" in blob),
        "shuffled_target": ("shuffled" in blob and ("target" in blob or "conditional" in blob or "control" in blob)),
        "train_eval_run_overlap": ("train_eval_run_overlap" in blob or "run overlap" in blob or "heldout_absent_from_train" in blob),
        "train_eval_key_overlap": ("train_eval_key_overlap" in blob or "key overlap" in blob),
        "no_run_event_features": (
            "no_run_or_event_features" in blob
            or "uses_run_or_event_features" in blob
            or "excluded_features" in blob
            or "excludes run id" in blob
        ),
    }

    clean = {name: bool(statuses[name]) for name in statuses}

    run_overlap_values = numeric_values_for_key(data, r"train_eval_run_overlap$")
    key_overlap_values = numeric_values_for_key(data, r"train_eval_key_overlap$")
    if run_overlap_values and any(v != 0.0 for v in run_overlap_values):
        clean["train_eval_run_overlap"] = False
    if key_overlap_values and any(v != 0.0 for v in key_overlap_values):
        clean["train_eval_key_overlap"] = False
    if has_forbidden_feature_text(blob):
        clean["no_run_event_features"] = False

    reasons = []
    for key in statuses:
        if not statuses[key]:
            reasons.append(f"missing {CONTROL_LABELS[key]}")
        elif not clean[key]:
            reasons.append(f"dirty {CONTROL_LABELS[key]}")

    return statuses, clean, reasons


def lint_report(path: Path, data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    report_text = report_text_for_result(path)
    blob = text_blob(data, report_text)
    win_evidence = extract_win_evidence(data, blob)
    is_promoted = promoted_claim(win_evidence, blob, config["promoted_claim_caution_terms"])
    statuses, clean, control_reasons = control_status(data, blob)
    all_controls_clean = all(statuses.values()) and all(clean.values())
    in_scope = is_p10_or_template_report(data, blob)
    should_fail = bool(in_scope and is_promoted and not all_controls_clean)
    return {
        "ticket_id": ticket_id(data, path),
        "study": study_id(data),
        "path": str(path.relative_to(ROOT)),
        "title": str(data.get("title") or data.get("finding") or "")[:220],
        "in_scope": in_scope,
        "win_evidence": ";".join(win_evidence),
        "claimed_qspace_template_win": bool(win_evidence),
        "promoted_claim": bool(is_promoted),
        "all_controls_present": all(statuses.values()),
        "all_controls_clean": all_controls_clean,
        "linter_fail": should_fail,
        "fail_reasons": "; ".join(control_reasons if should_fail else []),
        **{f"has_{key}": statuses[key] for key in statuses},
        **{f"clean_{key}": clean[key] for key in clean},
        "document_token_count": len(tokenize(blob)),
    }


def tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", text.lower())


def build_nb_dataset(rows: Sequence[Dict[str, Any]], docs: Dict[str, str]) -> Tuple[List[str], List[int], List[str]]:
    kept_rows = [row for row in rows if row["in_scope"]]
    labels = [1 if row["all_controls_present"] and row["all_controls_clean"] else 0 for row in kept_rows]
    texts = [docs[row["path"]] for row in kept_rows]
    paths = [row["path"] for row in kept_rows]
    return texts, labels, paths


def train_nb(texts: Sequence[str], labels: Sequence[int]) -> Tuple[Dict[str, Any], List[str]]:
    vocab_counter: Counter[str] = Counter()
    for text in texts:
        vocab_counter.update(tokenize(text))
    vocab = [word for word, count in vocab_counter.most_common(600) if count >= 1]
    vocab_set = set(vocab)

    class_counts = {0: 0, 1: 0}
    token_counts = {0: Counter(), 1: Counter()}
    total_tokens = {0: 0, 1: 0}
    for text, label in zip(texts, labels):
        class_counts[int(label)] += 1
        counts = Counter(tok for tok in tokenize(text) if tok in vocab_set)
        token_counts[int(label)].update(counts)
        total_tokens[int(label)] += sum(counts.values())

    model = {
        "class_counts": class_counts,
        "token_counts": token_counts,
        "total_tokens": total_tokens,
        "n_docs": len(texts),
        "vocab_size": max(1, len(vocab)),
    }
    return model, vocab


def nb_predict_proba(model: Dict[str, Any], vocab: Sequence[str], text: str) -> float:
    vocab_set = set(vocab)
    counts = Counter(tok for tok in tokenize(text) if tok in vocab_set)
    logps = {}
    for cls in (0, 1):
        class_prior = (model["class_counts"][cls] + 1.0) / (model["n_docs"] + 2.0)
        logp = math.log(class_prior)
        denom = model["total_tokens"][cls] + model["vocab_size"]
        for token, count in counts.items():
            num = model["token_counts"][cls][token] + 1.0
            logp += count * math.log(num / denom)
        logps[cls] = logp
    hi = max(logps.values())
    p1 = math.exp(logps[1] - hi)
    p0 = math.exp(logps[0] - hi)
    return p1 / (p0 + p1)


def ml_leave_one_report_out(rows: Sequence[Dict[str, Any]], docs: Dict[str, str]) -> List[Dict[str, Any]]:
    texts, labels, paths = build_nb_dataset(rows, docs)
    out = []
    for idx, (text, label, path) in enumerate(zip(texts, labels, paths)):
        train_texts = [t for j, t in enumerate(texts) if j != idx]
        train_labels = [y for j, y in enumerate(labels) if j != idx]
        if not train_texts:
            score = 0.5
        else:
            model, vocab = train_nb(train_texts, train_labels)
            score = nb_predict_proba(model, vocab, text)
        out.append(
            {
                "path": path,
                "label_controls_complete": int(label),
                "ml_controls_complete_score": score,
                "ml_controls_complete_pred": int(score >= 0.5),
            }
        )
    return out


def bootstrap_ci(values: Sequence[float], rng: random.Random, n_iter: int) -> Tuple[float, float]:
    if not values:
        return float("nan"), float("nan")
    draws = []
    n = len(values)
    for _ in range(n_iter):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        draws.append(sum(sample) / n)
    draws.sort()
    return draws[int(0.025 * (n_iter - 1))], draws[int(0.975 * (n_iter - 1))]


def roc_auc(labels: Sequence[int], scores: Sequence[float]) -> float:
    pos = [(s, y) for s, y in zip(scores, labels) if y == 1]
    neg = [(s, y) for s, y in zip(scores, labels) if y == 0]
    if not pos or not neg:
        return float("nan")
    wins = 0.0
    total = 0.0
    for ps, _ in pos:
        for ns, _ in neg:
            total += 1.0
            if ps > ns:
                wins += 1.0
            elif ps == ns:
                wins += 0.5
    return wins / total


def ml_summary(ml_rows: Sequence[Dict[str, Any]], rng: random.Random, n_iter: int) -> Dict[str, Any]:
    if not ml_rows:
        return {
            "method": "multinomial_naive_bayes_text_triage",
            "n_reports": 0,
            "accuracy": float("nan"),
            "accuracy_ci95": [float("nan"), float("nan")],
            "roc_auc": float("nan"),
        }
    labels = [int(row["label_controls_complete"]) for row in ml_rows]
    preds = [int(row["ml_controls_complete_pred"]) for row in ml_rows]
    scores = [float(row["ml_controls_complete_score"]) for row in ml_rows]
    correct = [1.0 if y == p else 0.0 for y, p in zip(labels, preds)]
    ci = bootstrap_ci(correct, rng, n_iter)
    return {
        "method": "multinomial_naive_bayes_text_triage",
        "task": "advisory detection of control-complete P10/P-template result schemas",
        "split": "leave-one-report-out; report-bootstrap confidence interval",
        "n_reports": len(ml_rows),
        "positive_control_complete_reports": int(sum(labels)),
        "accuracy": sum(correct) / len(correct),
        "accuracy_ci95": list(ci),
        "roc_auc": roc_auc(labels, scores),
        "use_in_gate": False,
    }


def reproduce_p10e_registry(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    result = load_json(ROOT / config["p10e_registry_result"])
    rows = []
    reproduction = result.get("reproduction", {})
    rows.append(
        {
            "quantity": "P10e selected B-stave pulses",
            "expected": 640737,
            "observed": reproduction.get("selected_b_stave_pulses"),
            "pass": reproduction.get("selected_b_stave_pulses") == 640737,
        }
    )
    rows.append(
        {
            "quantity": "P10e analysis selected rows",
            "expected": 377362,
            "observed": reproduction.get("analysis_selected_rows"),
            "pass": reproduction.get("analysis_selected_rows") == 377362,
        }
    )
    rows.append(
        {
            "quantity": "P10e required registry controls",
            "expected": 5,
            "observed": len(result.get("controls", [])),
            "pass": len(result.get("controls", [])) == 5,
        }
    )
    rows.append(
        {
            "quantity": "P10e registry status",
            "expected": "pass",
            "observed": result.get("registry_status"),
            "pass": result.get("registry_status") == "pass",
        }
    )
    folds = result.get("folds", [])
    rows.append(
        {
            "quantity": "P10e family-heldout folds",
            "expected": 2,
            "observed": len(folds),
            "pass": len(folds) == 2,
        }
    )
    for fold in folds:
        delta = fold.get("delta_conditional_minus_empirical")
        rows.append(
            {
                "quantity": f"{fold.get('fold')} conditional-minus-empirical delta",
                "expected": "positive no q-space win",
                "observed": delta,
                "pass": as_float(delta) > 0,
            }
        )
    return rows


def write_csv(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: List[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def markdown_table(rows: Sequence[Dict[str, Any]], columns: Sequence[str]) -> str:
    if not rows:
        return "_No rows._"
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = []
    for row in rows:
        vals = []
        for col in columns:
            value = row.get(col, "")
            text = str(value)
            if len(text) > 90:
                text = text[:87] + "..."
            vals.append(text.replace("\n", " "))
        body.append("| " + " | ".join(vals) + " |")
    return "\n".join([header, sep] + body)


def write_report(out_dir: Path, config: Dict[str, Any], repro_rows: List[Dict[str, Any]], lint_rows: List[Dict[str, Any]], ml_info: Dict[str, Any], result: Dict[str, Any]) -> None:
    scoped = [row for row in lint_rows if row["in_scope"]]
    failures = [row for row in scoped if row["linter_fail"]]
    promoted = [row for row in scoped if row["promoted_claim"]]
    control_complete = [row for row in scoped if row["all_controls_clean"]]
    lines = [
        "# P10f: Automatic conditional-template claim linter",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Input:** existing `reports/*/{result.json,REPORT.md}` artifacts only; no Monte Carlo and no raw ROOT reread for this infrastructure ticket.",
        "",
        "## Reproduction First",
        "",
        "The linter reproduces the P10e registry anchor from the committed P10e result before scanning the wider report corpus.",
        "",
        markdown_table(repro_rows, ["quantity", "expected", "observed", "pass"]),
        "",
        "## Traditional Gate",
        "",
        "The production method is a schema-aware deterministic linter. It marks a report as failing only when a promoted q-space conditional/template ML win is present and at least one required P10e control is missing or dirty: mean-template, shuffled-target, train/eval run overlap, train/eval key overlap, and no run/event feature use.",
        "",
        markdown_table(
            [
                {
                    "scanned_result_json": len(lint_rows),
                    "in_scope_p10_or_template": len(scoped),
                    "promoted_claims": len(promoted),
                    "control_complete": len(control_complete),
                    "linter_failures": len(failures),
                }
            ],
            ["scanned_result_json", "in_scope_p10_or_template", "promoted_claims", "control_complete", "linter_failures"],
        ),
        "",
        "Current failures:",
        "",
        markdown_table(failures, ["ticket_id", "study", "path", "fail_reasons"]) if failures else "No current committed P10/P-template result fails the promoted-claim gate.",
        "",
        "## ML Triage",
        "",
        "The ML method is deliberately advisory: a leave-one-report-out multinomial Naive Bayes text model predicts whether a result schema is control-complete. It is not allowed to override the deterministic gate.",
        "",
        markdown_table(
            [
                {
                    "method": ml_info["method"],
                    "split": ml_info["split"],
                    "n_reports": ml_info["n_reports"],
                    "positive": ml_info["positive_control_complete_reports"],
                    "accuracy": f"{ml_info['accuracy']:.3f}" if not math.isnan(ml_info["accuracy"]) else "nan",
                    "accuracy_ci95": ml_info["accuracy_ci95"],
                    "roc_auc": f"{ml_info['roc_auc']:.3f}" if not math.isnan(ml_info["roc_auc"]) else "nan",
                    "used_in_gate": ml_info["use_in_gate"],
                }
            ],
            ["method", "split", "n_reports", "positive", "accuracy", "accuracy_ci95", "roc_auc", "used_in_gate"],
        ),
        "",
        "## Leakage Check",
        "",
        "The linter treats suspiciously good ML/template claims as unsafe unless the control names and clean overlap/feature checks are present in the report artifact. Reports that say the result is diagnostic or not promoted are not failed as promoted claims, but their missing controls remain visible in `linter_decisions.csv`.",
        "",
        "## Verdict",
        "",
        result["finding"],
        "",
        "## Reproduce",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python scripts/p10f_1781025208_1030_73ae38c0_claim_linter.py --config configs/p10f_1781025208_1030_73ae38c0_claim_linter.json",
        "```",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def collect_inputs(lint_rows: Sequence[Dict[str, Any]], config: Dict[str, Any]) -> List[Path]:
    paths = {ROOT / config["p10e_registry_result"], ROOT / config["p10e_registry_report"], ROOT / "configs/p10f_1781025208_1030_73ae38c0_claim_linter.json"}
    for row in lint_rows:
        result_path = ROOT / row["path"]
        paths.add(result_path)
        report = result_path.with_name("REPORT.md")
        if report.exists():
            paths.add(report)
    return sorted(path for path in paths if path.exists())


def make_manifest(out_dir: Path, config: Dict[str, Any], input_paths: Sequence[Path], command: str) -> Dict[str, Any]:
    input_rows = []
    for path in input_paths:
        input_rows.append(
            {
                "path": str(path.relative_to(ROOT)),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    write_csv(out_dir / "input_sha256.csv", input_rows)
    output_rows = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_rows.append(
                {
                    "path": str(path.relative_to(ROOT)),
                    "sha256": sha256_file(path),
                    "bytes": path.stat().st_size,
                }
            )
    return {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "command": command,
        "inputs": input_rows,
        "outputs": output_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p10f_1781025208_1030_73ae38c0_claim_linter.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = ROOT / args.config
    config = load_json(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    repro_rows = reproduce_p10e_registry(config)
    write_csv(out_dir / "p10e_reproduction.csv", repro_rows)
    if not all(bool(row["pass"]) for row in repro_rows):
        raise RuntimeError("P10e reproduction anchor failed")

    lint_rows: List[Dict[str, Any]] = []
    docs: Dict[str, str] = {}
    for result_path in sorted((ROOT / "reports").glob("*/result.json")):
        if result_path.parent.resolve() == out_dir.resolve():
            continue
        data = load_json(result_path)
        report_text = report_text_for_result(result_path)
        rel_path = str(result_path.relative_to(ROOT))
        docs[rel_path] = text_blob(data, report_text)
        lint_rows.append(lint_report(result_path, data, config))

    write_csv(out_dir / "linter_decisions.csv", lint_rows)
    ml_rows = ml_leave_one_report_out(lint_rows, docs)
    write_csv(out_dir / "ml_report_triage.csv", ml_rows)
    rng = random.Random(int(config["random_seed"]))
    ml_info = ml_summary(ml_rows, rng, int(config["bootstrap_iterations"]))

    scoped = [row for row in lint_rows if row["in_scope"]]
    failures = [row for row in scoped if row["linter_fail"]]
    promoted = [row for row in scoped if row["promoted_claim"]]
    finding = (
        "The P10e control schema is reproducible from committed artifacts, and the deterministic linter finds no current promoted q-space conditional/template claim that lacks the required clean controls."
        if not failures
        else "The deterministic linter finds promoted q-space conditional/template claims with missing or dirty P10e controls; these should fail summary promotion until repaired."
    )

    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "ticket_body": config["ticket_body"],
        "reproduced": all(bool(row["pass"]) for row in repro_rows),
        "reproduction": {
            "source": config["p10e_registry_result"],
            "rows": repro_rows,
            "raw_root_reread": False,
            "reason_no_raw_root": "ticket explicitly says use existing reports only; the object under test is result.json/report schema enforcement",
        },
        "input_sha256": "input_sha256.csv",
        "split": "report-corpus scan; held-out report bootstrap for advisory ML, not event/run ROOT split",
        "traditional": {
            "method": "deterministic schema-aware P10e control gate",
            "metric": "number of promoted q-space conditional/template claims failing required controls",
            "value": len(failures),
            "ci": [len(failures), len(failures)],
            "n_scanned_result_json": len(lint_rows),
            "n_in_scope": len(scoped),
            "n_promoted_claims": len(promoted),
        },
        "ml": ml_info,
        "ml_beats_baseline": False,
        "falsification": {
            "preregistered_failure_condition": "any promoted q-space conditional/template win missing mean-template, shuffled-target, run/key-overlap, or no-run/event-feature controls",
            "failed_reports": [row["path"] for row in failures],
            "leakage_hunt": "too-good or promoted claims are failed unless controls are present and clean; diagnostic/non-promoted claims are reported but not promoted",
            "n_tries": 1,
        },
        "finding": finding,
        "next_tickets": [],
        "runtime_sec": round(time.time() - t0, 3),
        "git_commit": git_commit(),
        "critic": "pending",
    }
    write_json(out_dir / "result.json", result)
    write_report(out_dir, config, repro_rows, lint_rows, ml_info, result)
    input_paths = collect_inputs(lint_rows, config)
    manifest = make_manifest(
        out_dir,
        config,
        input_paths,
        f"/home/billy/anaconda3/bin/python scripts/p10f_1781025208_1030_73ae38c0_claim_linter.py --config {args.config}",
    )
    write_json(out_dir / "manifest.json", manifest)
    print(json.dumps({"done": True, "ticket_id": config["ticket_id"], "failures": len(failures), "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
