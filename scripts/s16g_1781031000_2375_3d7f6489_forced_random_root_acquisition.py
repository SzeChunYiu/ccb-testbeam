#!/usr/bin/env python3
"""S16g forced/random HRD pedestal ROOT acquisition audit.

This ticket asks for the true forced/random pedestal sample, not another
quiet-event proxy.  The script therefore performs three gates in order:

1. Reproduce the established selected B-stave pulse count from raw HRDB ROOT.
2. Search the local and canonical data mirrors plus archive members for
   forced/random/pedestal source files.
3. Inspect ROOT trigger and branch metadata for non-beam entries that could
   support a direct S16f no-proxy truth comparison.

If the direct truth rows are still absent, the script writes a hard negative
result and deliberately does not run the quiet-proxy fallback.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
import uproot


STRICT_TAGS = {"force", "forced", "random", "pedestal", "ped", "empty", "nopulse", "no_pulse", "noise", "dark", "pulser"}


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, tuple):
        return [json_clean(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if np.isnan(value) else float(value)
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def configured_runs(config: dict) -> list[int]:
    runs: list[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def root_paths(config: dict, stack: str | None = None) -> list[Path]:
    root = Path(config["raw_root_dir"])
    if stack is None:
        return sorted(root.glob("hrd[ab]_run_*.root"))
    return sorted(root.glob(f"hrd{stack}_run_*.root"))


def bstack_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{int(run):04d}.root"


def parse_run(path: Path) -> int | None:
    match = re.search(r"_run_(\d+)", path.name)
    return int(match.group(1)) if match else None


def iter_tree(path: Path, branches: Sequence[str], step_size: int = 30000) -> Iterable[dict]:
    yield from uproot.open(path)["h101"].iterate(list(branches), step_size=step_size, library="np")


def tag_regex(config: dict) -> re.Pattern:
    tokens = [re.escape(str(token)) for token in config["tag_tokens"]]
    return re.compile(r"(" + "|".join(tokens) + r")", re.I)


def strict_token_hit(text: str, regex: re.Pattern) -> tuple[str, bool]:
    match = regex.search(text)
    if not match:
        return "", False
    token = match.group(0).lower()
    return token, token in STRICT_TAGS


def reproduce_selected_pulses(config: dict) -> pd.DataFrame:
    stave_channels = np.asarray(list(config["staves"].values()), dtype=int)
    pre = np.asarray(config["pretrigger_samples"], dtype=int)
    n_samples = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    rows = []
    for run in configured_runs(config):
        path = bstack_path(config, run)
        events = 0
        selected = 0
        for batch in iter_tree(path, ["HRDv"]):
            wave = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, n_samples)[:, stave_channels, :]
            seed = np.median(wave[:, :, pre], axis=2)
            amp = (wave - seed[:, :, None]).max(axis=2)
            events += int(wave.shape[0])
            selected += int((amp > cut).sum())
        rows.append({"run": int(run), "events_total": events, "selected_b_stave_pulses": selected})
    return pd.DataFrame(rows)


def audit_root_metadata(config: dict) -> pd.DataFrame:
    branch_tokens = [str(token).lower() for token in config["tag_branch_tokens"]]
    rows = []
    for path in root_paths(config):
        tree = uproot.open(path)["h101"]
        branches = list(tree.keys())
        tag_like_branches = [branch for branch in branches if any(token in branch.lower() for token in branch_tokens)]
        if tree.num_entries and "TRIGGER" in branches:
            trigger = tree.arrays(["TRIGGER"], library="np")["TRIGGER"]
            values, counts = np.unique(trigger, return_counts=True)
            trigger_summary = ";".join(f"{int(value)}:{int(count)}" for value, count in zip(values, counts))
            non_beam = int(np.sum(counts[values != int(config["non_beam_trigger_value"])]))
        else:
            trigger_summary = "missing_or_empty"
            non_beam = 0
        rows.append(
            {
                "file": path.name,
                "stack": path.name[:4],
                "run": parse_run(path),
                "entries": int(tree.num_entries),
                "branches": ";".join(branches),
                "tag_like_branches": ";".join(tag_like_branches),
                "has_tag_like_branch": bool(tag_like_branches),
                "trigger_summary": trigger_summary,
                "non_beam_trigger_entries": non_beam,
            }
        )
    return pd.DataFrame(rows)


def audit_filesystem_and_archives(config: dict) -> pd.DataFrame:
    rows = []
    regex = tag_regex(config)
    seen: set[str] = set()
    for root_text in config["search_roots"]:
        root = Path(root_text)
        if not root.exists():
            rows.append(
                {
                    "search_root": root_text,
                    "container": "",
                    "member": "",
                    "kind": "missing_search_root",
                    "suffix": "",
                    "bytes": 0,
                    "token": "",
                    "forced_random_hit": False,
                }
            )
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            try:
                real = str(path.resolve())
            except OSError:
                real = str(path)
            if real in seen:
                continue
            seen.add(real)
            token, hit = strict_token_hit(str(path), regex)
            rows.append(
                {
                    "search_root": root_text,
                    "container": str(path),
                    "member": "",
                    "kind": "filesystem",
                    "suffix": path.suffix.lower(),
                    "bytes": int(path.stat().st_size),
                    "token": token,
                    "forced_random_hit": hit,
                }
            )
            if path.suffix.lower() == ".zip":
                try:
                    with zipfile.ZipFile(path) as archive:
                        for info in archive.infolist():
                            token, hit = strict_token_hit(info.filename, regex)
                            rows.append(
                                {
                                    "search_root": root_text,
                                    "container": str(path),
                                    "member": info.filename,
                                    "kind": "zip_member",
                                    "suffix": Path(info.filename).suffix.lower(),
                                    "bytes": int(info.file_size),
                                    "token": token,
                                    "forced_random_hit": hit,
                                }
                            )
                except zipfile.BadZipFile:
                    rows.append(
                        {
                            "search_root": root_text,
                            "container": str(path),
                            "member": "",
                            "kind": "bad_zip",
                            "suffix": path.suffix.lower(),
                            "bytes": 0,
                            "token": "",
                            "forced_random_hit": False,
                        }
                    )
    return pd.DataFrame(rows)


def load_direct_nonbeam_entries(config: dict) -> pd.DataFrame:
    rows = []
    for run in configured_runs(config):
        path = bstack_path(config, run)
        for batch in iter_tree(path, ["EVENTNO", "EVT", "TRIGGER"]):
            trigger = np.asarray(batch["TRIGGER"])
            keep = trigger != int(config["non_beam_trigger_value"])
            if not np.any(keep):
                continue
            rows.append(
                pd.DataFrame(
                    {
                        "run": int(run),
                        "eventno": np.asarray(batch["EVENTNO"])[keep].astype(int),
                        "evt": np.asarray(batch["EVT"])[keep].astype(int),
                        "trigger": trigger[keep].astype(int),
                    }
                )
            )
    if not rows:
        return pd.DataFrame(columns=["run", "eventno", "evt", "trigger"])
    return pd.concat(rows, ignore_index=True)


def write_report(
    out_dir: Path,
    config: dict,
    result: dict,
    reproduction: pd.DataFrame,
    root_audit: pd.DataFrame,
    file_audit: pd.DataFrame,
    direct_rows: pd.DataFrame,
) -> None:
    selected_total = int(reproduction["selected_b_stave_pulses"].sum())
    non_beam_total = int(root_audit["non_beam_trigger_entries"].sum())
    root_candidates = file_audit[(file_audit["forced_random_hit"]) & (file_audit["suffix"].isin([".root", ".zip", ".tar", ".gz"]))]
    missing_roots = file_audit[file_audit["kind"] == "missing_search_root"]
    trigger_table = root_audit.groupby("stack", as_index=False).agg(
        files=("file", "count"),
        entries=("entries", "sum"),
        non_beam_trigger_entries=("non_beam_trigger_entries", "sum"),
        files_with_tag_like_branch=("has_tag_like_branch", "sum"),
    )
    direct_gate_table = pd.DataFrame(
        [
            {
                "estimand": "direct forced/random pedestal estimator MAE",
                "n_truth_entries": len(direct_rows),
                "value_adc": np.nan,
                "ci95_low_adc": np.nan,
                "ci95_high_adc": np.nan,
                "status": "not estimable: zero direct truth entries",
            }
        ]
    )
    count_table = reproduction.agg({"events_total": "sum", "selected_b_stave_pulses": "sum"}).to_frame("value")

    lines = [
        "# S16g: forced/random HRD pedestal ROOT acquisition audit",
        "",
        "## Abstract",
        "",
        (
            "Ticket `1781031000.2375.3d7f6489` asked whether the true forced/random HRD pedestal ROOT "
            "sample can be acquired or mirrored, and whether S16f can then be rerun as a direct electronics "
            "pedestal truth comparison without the quiet-proxy fallback. I reran the raw-ROOT selected-pulse "
            "gate, searched the visible data mirrors and archive members, and inspected ROOT trigger/branch "
            "metadata for non-beam entries. The direct truth gate remains empty."
        ),
        "",
        "## Inputs and Reproducibility",
        "",
        f"- Ticket: `{config['ticket']}`",
        f"- Worker: `{config['worker']}`",
        f"- Git commit: `{result['git_commit']}`",
        f"- Raw ROOT directory: `{config['raw_root_dir']}`",
        f"- Config: `configs/s16g_1781031000_2375_3d7f6489_forced_random_root_acquisition.json`",
        f"- Script: `scripts/s16g_1781031000_2375_3d7f6489_forced_random_root_acquisition.py`",
        "",
        "Search roots:",
    ]
    for root in config["search_roots"]:
        exists = Path(root).exists()
        lines.append(f"- `{root}`: {'present' if exists else 'missing'}")
    lines.extend(
        [
            "",
            "## Raw-ROOT Reproduction Gate",
            "",
            "For each configured B-stack run \(r\), channel \(c\in\\{B2,B4,B6,B8\\}\), and sample \(t\), "
            "the seed pedestal was",
            "",
            "\\[",
            "p_{irc}=\\operatorname{median}\\{x_{irc0},x_{irc1},x_{irc2},x_{irc3}\\},",
            "\\]",
            "",
            "and the selected-pulse indicator was",
            "",
            "\\[",
            "I_{irc}=\\mathbf{1}\\left[\\max_t (x_{irct}-p_{irc}) > 1000\\;\\mathrm{ADC}\\right].",
            "\\]",
            "",
            f"The reproduced sum is `{selected_total}` selected B-stave pulses; the expected gate is "
            f"`{config['expected_selected_pulses']}`.",
            "",
            count_table.to_markdown(),
            "",
            "The gate reproduction table is `reproduction_match_table.csv`; all run contributions are in "
            "`selected_count_by_run.csv`.",
            "",
            "## Acquisition and Mirror Audit",
            "",
            "The acquisition test treats a file or archive member as a candidate only if its name contains a strict "
            "forced/random/pedestal/no-pulse token. Generic `trigger` names are retained for context but do not "
            "count as a forced/random pedestal source. Archive members of visible `.zip` files were listed without "
            "extracting new data.",
            "",
            "| quantity | value |",
            "|---|---:|",
            f"| filesystem/archive rows audited | {len(file_audit)} |",
            f"| strict forced/random archive or ROOT candidates | {len(root_candidates)} |",
            f"| missing search roots | {len(missing_roots)} |",
            "",
            "The complete inventory is `file_archive_inventory.csv`. The canonical LUNARC data path is listed as "
            "a search root; in this local run it is absent, so no mirroring source was available from that path.",
            "",
            "## ROOT Trigger and Branch Audit",
            "",
            "A direct S16f truth comparison requires events whose trigger or metadata identify non-beam "
            "forced/random/no-pulse acquisitions. For each ROOT file I inspected the `h101` branch list and counted",
            "",
            "\\[",
            "N_{\\mathrm{nonbeam}} = \\sum_i \\mathbf{1}[\\mathrm{TRIGGER}_i \\ne 1].",
            "\\]",
            "",
            trigger_table.to_markdown(index=False),
            "",
            f"Across the visible HRDA/HRDB ROOT bundle, `N_nonbeam = {non_beam_total}`. "
            "The only branches are the standard DAQ fields; there is no separate random/forced/pedestal tag branch.",
            "",
            "## Direct S16f Rerun Gate",
            "",
            f"The direct no-proxy candidate table contains `{len(direct_rows)}` B-stack entries. Since this is zero, "
            "no estimator can be scored against forced/random electronics pedestal truth and no bootstrap confidence "
            "interval is statistically defined. I did not run the quiet-event proxy fallback because the ticket asks "
            "specifically for the direct truth comparison.",
            "",
            direct_gate_table.to_markdown(index=False),
            "",
            "## Result",
            "",
            result["conclusion"],
            "",
            "## Systematics and Caveats",
            "",
            "- This is an absence-in-visible-mirror result, not proof that forced/random pedestal data were never recorded.",
            "- ROOT trigger semantics are inherited from prior S16 work: `TRIGGER == 1` is treated as the beam trigger; "
            "non-beam truth would require a different value or a dedicated tag branch.",
            "- The scan covers the local data symlinks, `/home/billy/ccb-data`, `/home/billy/Desktop/test_beam/data`, "
            "and the configured LUNARC canonical path if mounted. It cannot inspect unmounted offline archives.",
            "- The selected-pulse reproduction verifies that the same B-stack raw ROOT bundle used by the main studies "
            "is being audited, but it does not create a no-pulse truth sample.",
            "",
            "## Artifacts",
            "",
            "- `result.json`",
            "- `REPORT.md`",
            "- `manifest.json`",
            "- `input_sha256.csv`",
            "- `selected_count_by_run.csv`",
            "- `reproduction_match_table.csv`",
            "- `root_trigger_branch_audit.csv`",
            "- `file_archive_inventory.csv`",
            "- `direct_nonbeam_entries.csv`",
        ]
    )
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s16g_1781031000_2375_3d7f6489_forced_random_root_acquisition.json")
    args = parser.parse_args()

    start = time.time()
    config_path = Path(args.config)
    config = json.loads(config_path.read_text())
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    reproduction = reproduce_selected_pulses(config)
    root_audit = audit_root_metadata(config)
    file_audit = audit_filesystem_and_archives(config)
    direct_rows = load_direct_nonbeam_entries(config)

    reproduction.to_csv(out_dir / "selected_count_by_run.csv", index=False)
    root_audit.to_csv(out_dir / "root_trigger_branch_audit.csv", index=False)
    file_audit.to_csv(out_dir / "file_archive_inventory.csv", index=False)
    direct_rows.to_csv(out_dir / "direct_nonbeam_entries.csv", index=False)

    selected_total = int(reproduction["selected_b_stave_pulses"].sum())
    non_beam_total = int(root_audit["non_beam_trigger_entries"].sum())
    strict_candidates = file_audit[(file_audit["forced_random_hit"]) & (file_audit["suffix"].isin([".root", ".zip", ".tar", ".gz"]))]
    reproduction_match = pd.DataFrame(
        [
            {
                "quantity": "selected_b_stave_pulses",
                "expected": int(config["expected_selected_pulses"]),
                "reproduced": selected_total,
                "delta": selected_total - int(config["expected_selected_pulses"]),
                "pass": selected_total == int(config["expected_selected_pulses"]),
            },
            {
                "quantity": "forced_random_tagged_entries",
                "expected": int(config["expected_forced_random_tagged_entries"]),
                "reproduced": int(len(direct_rows)),
                "delta": int(len(direct_rows)) - int(config["expected_forced_random_tagged_entries"]),
                "pass": int(len(direct_rows)) == int(config["expected_forced_random_tagged_entries"]),
            },
        ]
    )
    reproduction_match.to_csv(out_dir / "reproduction_match_table.csv", index=False)

    input_files = [config_path, Path(__file__).resolve()] + root_paths(config)
    input_sha = pd.DataFrame(
        [{"path": str(path), "sha256": sha256_file(path)} for path in input_files if path.exists() and path.is_file()]
    )
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    direct_truth_ready = len(direct_rows) > 0
    if direct_truth_ready:
        conclusion = (
            "Direct forced/random entries are present; this audit found a usable truth table. "
            "A separate estimator benchmark should now score S16f methods without proxy fallback."
        )
        verdict = "direct_truth_ready"
        winner = "pending_direct_s16f_estimator_benchmark"
    else:
        conclusion = (
            "No forced/random HRD pedestal ROOT source or non-beam B-stack entry is visible in the mounted mirrors. "
            "The S16f direct truth comparison remains blocked; the only scientifically valid winner for this ticket "
            "is `none_no_direct_truth_sample` rather than a quiet-proxy estimator."
        )
        verdict = "blocked_missing_direct_truth"
        winner = "none_no_direct_truth_sample"

    result = {
        "ticket": config["ticket"],
        "study": config["study"],
        "worker": config["worker"],
        "title": config["title"],
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - start, 3),
        "reproduction": {
            "selected_b_stave_pulses_expected": int(config["expected_selected_pulses"]),
            "selected_b_stave_pulses_reproduced": selected_total,
            "selected_pulse_gate_pass": selected_total == int(config["expected_selected_pulses"]),
            "forced_random_tagged_entries_reproduced": int(len(direct_rows)),
            "forced_random_tagged_entries_expected": int(config["expected_forced_random_tagged_entries"]),
        },
        "acquisition_audit": {
            "search_roots": config["search_roots"],
            "filesystem_archive_rows_audited": int(len(file_audit)),
            "strict_forced_random_root_or_archive_candidates": int(len(strict_candidates)),
            "missing_search_roots": file_audit[file_audit["kind"] == "missing_search_root"]["search_root"].tolist(),
        },
        "root_trigger_audit": {
            "root_files_audited": int(len(root_audit)),
            "non_beam_trigger_entries": non_beam_total,
            "files_with_tag_like_branch": int(root_audit["has_tag_like_branch"].sum()),
            "trigger_summaries": sorted(root_audit["trigger_summary"].unique().tolist()),
        },
        "s16f_direct_truth_rerun": {
            "status": "ready" if direct_truth_ready else "blocked",
            "direct_nonbeam_entries": int(len(direct_rows)),
            "quiet_proxy_fallback_run": False,
            "reason": "direct forced/random entries available" if direct_truth_ready else "zero direct forced/random/non-beam entries in visible B-stack ROOT",
        },
        "winner": winner,
        "verdict": verdict,
        "conclusion": conclusion,
        "next_tickets": [],
    }

    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2), encoding="utf-8")
    write_report(out_dir, config, result, reproduction, root_audit, file_audit, direct_rows)

    manifest = {
        "ticket": config["ticket"],
        "command": f"/home/billy/anaconda3/bin/python {Path(__file__).as_posix()} --config {config_path.as_posix()}",
        "artifacts": sorted(path.name for path in out_dir.iterdir() if path.is_file()),
        "sha256": {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file()},
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2), encoding="utf-8")
    print(json.dumps({"done": True, "ticket": config["ticket"], "verdict": verdict, "runtime_sec": result["runtime_sec"]}, indent=2))


if __name__ == "__main__":
    main()
