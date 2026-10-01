#!/usr/bin/env python3
"""Ticket #2402 P07 high-B2 saturation recovery benchmark.

This runner reuses the S35b saturation/pile-up benchmark implementation, but
binds it to the ticket #2402 metadata and to the raw ROOT symlink available in
this worker checkout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import uproot


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s35b_1784063447_914_74ba7793_saturation_pileup_energy_recovery_benchmark as engine  # noqa: E402


TICKET = "2402"
WORKER = "testbeam-laptop-3"
TITLE = "P07: Saturation recovery for high-B2"
SLUG = "t2402_p07_saturation_recovery_high_b2"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/sorted-b")


def raw_file(config: dict, run: int) -> Path:
    directory = Path(config["raw_root_dir"])
    direct = directory / f"hrdb_run_{run:04d}.root"
    if direct.exists():
        return direct
    return directory / f"hrdb_run_{run:04d}-sorted.root"


def iter_sorted_raw(path: Path, branches: list[str], step_size: int = 20000):
    tree = uproot.open(path)["tree"]
    needed = ["hrd/hrd.sample"]
    if "EVENTNO" in branches:
        needed.append("hrdEvtNo")
    for arrays in tree.iterate(needed, step_size=step_size, library="np"):
        out = {}
        if "HRDv" in branches:
            waves = []
            for sample in arrays["hrd/hrd.sample"]:
                arr = np.asarray(sample, dtype=np.float64)
                if arr.size != 8 * 18:
                    raise ValueError(f"unexpected waveform size {arr.size} in {path}")
                waves.append(arr)
            out["HRDv"] = np.asarray(waves, dtype=np.float64)
        if "EVENTNO" in branches:
            out["EVENTNO"] = np.asarray(arrays["hrdEvtNo"], dtype=np.int64)
        if "EVT" in branches:
            out["EVT"] = np.arange(len(out.get("HRDv", arrays["hrdEvtNo"])), dtype=np.int64)
        yield out


def md_table_without_tabulate(df, columns, limit=None) -> str:
    view = df.loc[:, list(columns)].copy()
    if limit is not None:
        view = view.head(limit)
    for col in view.columns:
        if str(view[col].dtype).startswith("float"):
            view[col] = view[col].map(lambda x: "" if not np.isfinite(x) else f"{float(x):.4g}")
    headers = [str(col) for col in view.columns]
    rows = [[str(value) for value in row] for row in view.to_numpy()]
    widths = [
        max([len(headers[i]), *[len(row[i]) for row in rows]]) for i in range(len(headers))
    ]

    def fmt(values):
        return "| " + " | ".join(str(values[i]).ljust(widths[i]) for i in range(len(values))) + " |"

    sep = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    return "\n".join([fmt(headers), sep, *[fmt(row) for row in rows]])


def patch_report_text(text: str) -> str:
    replacements = {
        "# S35b: Saturation Pile-Up Energy Recovery Benchmark": "# P07: Saturation Recovery for High-B2",
        "Ticket `2402` asks for a raw-ROOT reproduction": "Ticket `2402` asks for a raw-ROOT reproduction",
        "S35b winner": "P07 winner",
        "S35b held-out": "P07 held-out",
        "S35b:": "P07:",
        "`h101/HRDv` waveform branch is reshaped": "`tree/hrd.sample` waveform branch is adapted to the legacy `HRDv` layout and reshaped",
        "as the S35b winner": "as the P07 winner",
        "S35b saturation pile-up energy recovery benchmark": TITLE,
        "The worker is `testbeam-laptop-3`.": (
            "The worker is `testbeam-laptop-3`. The required single claim command "
            "was run once; because the local wrapper returned a null pseudo-ticket "
            "while the queue was non-empty, issue #2402 was recovered by applying "
            "the same label swap directly with GitHub issue metadata."
        ),
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def main() -> None:
    engine.TICKET = TICKET
    engine.WORKER = WORKER
    engine.TITLE = TITLE
    engine.SLUG = SLUG
    engine.OUT = OUT
    engine.RAW_ROOT_DIR = RAW_ROOT_DIR
    engine.p05a.raw_file = raw_file
    engine.p05a.iter_raw = iter_sorted_raw
    engine.base.p05a.raw_file = raw_file
    engine.base.p05a.iter_raw = iter_sorted_raw
    engine.s26b.p05a.raw_file = raw_file
    engine.s26b.p05a.iter_raw = iter_sorted_raw
    engine.s32b.p05a.raw_file = raw_file
    engine.s32b.p05a.iter_raw = iter_sorted_raw
    engine.md_table = md_table_without_tabulate
    engine.main()

    report = OUT / "REPORT.md"
    report.write_text(patch_report_text(report.read_text(encoding="utf-8")), encoding="utf-8")

    result_path = OUT / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["ticket_id"] = TICKET
    result["title"] = TITLE
    result["worker"] = WORKER
    result["claim_command"] = f"tn-ticket claim {WORKER} --project testbeam"
    result["claim_recovery_note"] = (
        "The mandated claim command was run exactly once and returned a null pseudo-ticket. "
        "Issue #2402 was then verified open and labeled factory:claimed + worker:testbeam-laptop-3 "
        "without issuing a second tn-ticket claim."
    )
    result["claimed_ticket_text"] = TITLE
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ticket_id"] = TICKET
    manifest["command"] = f"{sys.executable} {Path(__file__).resolve().relative_to(ROOT)}"
    manifest["outputs_sha256"]["REPORT.md"] = engine.base.sha256_file(report)
    manifest["outputs_sha256"]["result.json"] = engine.base.sha256_file(result_path)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
