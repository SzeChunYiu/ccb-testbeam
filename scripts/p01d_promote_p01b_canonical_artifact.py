#!/usr/bin/env python3
"""P01d: promote the P01b embedding artifact to a canonical data archive."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import uproot


TICKET_ID = "1781016189.1003.2607526c"
UPSTREAM_P01B_TICKET = "1781005204.1292.46e43fb0"
UPSTREAM_P01C_TICKET = "1781010024.910.7fbe14e8"
EXPECTED_SELECTED = 640737
EXPECTED_HASHES = {
    "p01b_embedding_latents.npz": "9dcffdb123a8c091781771ba9f1c6667a65af91cfabbfb64328427dfd7f865be",
    "p01b_autoencoder_state.pt": "20ca87b4df2a1d31ef99130423101772f6f293fe5fe0e0af3c859038d9d082d1",
}
SOURCE_DIR = Path(
    "/home/billy/.tb-workers/testbeam-laptop-2/artifacts/"
    "p01b_full_data_embedding_artifact/1781005204.1292.46e43fb0"
)
CANONICAL_TARGETS = [
    Path("/home/billy/ccb-data/artifacts/p01b_full_data_embedding_artifact/1781005204.1292.46e43fb0"),
    Path("/projects/hep/fs9/shared/nnbar/billy/ccb-testbeam/data/artifacts/p01b_full_data_embedding_artifact/1781005204.1292.46e43fb0"),
]
RAW_ROOT_CANDIDATES = [
    Path("data/extracted/root/root"),
    Path("data/root/root"),
    Path("/home/billy/ccb-data/extracted/root/root"),
    Path("/home/billy/Desktop/test_beam/data/root/root"),
]
RUN_GROUPS = {
    "sample_i_calib": [31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42],
    "sample_i_analysis": [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57],
    "sample_ii_calib": [64],
    "sample_ii_analysis": [58, 59, 60, 61, 62, 63, 65],
}
STAVES = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
BASELINE_SAMPLES = [0, 1, 2, 3]
SAMPLES_PER_CHANNEL = 18
AMPLITUDE_CUT_ADC = 1000.0


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def configured_runs() -> List[int]:
    runs: List[int] = []
    for group_runs in RUN_GROUPS.values():
        runs.extend(group_runs)
    return sorted(set(runs))


def run_group_lookup() -> Dict[int, str]:
    lookup: Dict[int, str] = {}
    for group, runs in RUN_GROUPS.items():
        for run in runs:
            lookup[int(run)] = group
    return lookup


def resolve_raw_root_dir() -> Path:
    for candidate in RAW_ROOT_CANDIDATES:
        if candidate.exists() and list(candidate.glob("hrdb_run_*.root")):
            return candidate
    raise FileNotFoundError("No raw B-stack ROOT directory found")


def iter_raw_events(path: Path, step_size: int = 20000) -> Iterable[np.ndarray]:
    tree = uproot.open(path)["h101"]
    for batch in tree.iterate(["HRDv"], step_size=step_size, library="np"):
        yield np.stack(batch["HRDv"]).astype(np.float32)


def recount_selected(raw_root_dir: Path) -> Tuple[List[dict], List[dict], int]:
    groups = run_group_lookup()
    stave_names = list(STAVES)
    stave_channels = np.asarray([STAVES[name] for name in stave_names], dtype=int)
    rows: List[dict] = []
    group_rows = {
        group: {"group": group, "events_total": 0, "events_with_selected": 0, "selected_pulses": 0, **{name: 0 for name in stave_names}}
        for group in RUN_GROUPS
    }

    for run in configured_runs():
        path = raw_root_dir / "hrdb_run_{:04d}.root".format(run)
        if not path.exists():
            raise FileNotFoundError("Missing configured run {}".format(path))
        group = groups[run]
        row = {"run": run, "group": group, "events_total": 0, "events_with_selected": 0, "selected_pulses": 0}
        row.update({name: 0 for name in stave_names})

        for raw in iter_raw_events(path):
            event_waves = raw.reshape(-1, 8, SAMPLES_PER_CHANNEL)
            selected_waves = event_waves[:, stave_channels, :]
            baseline = np.median(selected_waves[..., BASELINE_SAMPLES], axis=-1)
            amplitude = (selected_waves - baseline[..., None]).max(axis=-1)
            selected = amplitude > AMPLITUDE_CUT_ADC
            row["events_total"] += int(len(event_waves))
            row["events_with_selected"] += int(selected.any(axis=1).sum())
            row["selected_pulses"] += int(selected.sum())
            for idx, name in enumerate(stave_names):
                row[name] += int(selected[:, idx].sum())

        for key, value in row.items():
            if key not in ("run", "group"):
                group_rows[group][key] += int(value)
        rows.append(row)
        print("run {:04d}: {} selected pulses".format(run, row["selected_pulses"]))

    total = int(sum(row["selected_pulses"] for row in rows))
    return rows, [group_rows[group] for group in RUN_GROUPS], total


def target_status(target: Path) -> dict:
    parent = target.parent
    if target.exists():
        probe_dir = target
    else:
        probe_dir = parent
    return {
        "target": str(target),
        "parent_exists": parent.exists(),
        "target_exists": target.exists(),
        "probe_dir": str(probe_dir),
        "writable_probe": os.access(probe_dir, os.W_OK) if probe_dir.exists() else False,
    }


def try_promote(targets: List[Path]) -> Tuple[dict, List[dict]]:
    attempts: List[dict] = []
    selected = None
    for target in targets:
        attempt = target_status(target)
        try:
            target.mkdir(parents=True, exist_ok=True)
            copied = []
            for name, expected_hash in EXPECTED_HASHES.items():
                src = SOURCE_DIR / name
                dst = target / name
                shutil.copy2(src, dst)
                got = sha256_file(dst)
                copied.append(
                    {
                        "file": name,
                        "path": str(dst),
                        "bytes": dst.stat().st_size,
                        "sha256": got,
                        "matches_expected_sha256": got == expected_hash,
                    }
                )
                if got != expected_hash:
                    raise RuntimeError("{} hash mismatch after copy".format(name))
            attempt.update({"status": "promoted", "artifacts": copied})
            selected = {"status": "promoted", "path": str(target), "artifacts": copied}
            attempts.append(attempt)
            break
        except Exception as exc:  # noqa: BLE001 - report the filesystem boundary verbatim.
            attempt.update({"status": "failed", "error": str(exc)})
            attempts.append(attempt)
    if selected is None:
        selected = {"status": "blocked", "path": None, "artifacts": []}
    return selected, attempts


def write_csv(path: Path, rows: List[dict], fieldnames: List[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_report(out_dir: Path, result: dict) -> None:
    promoted = result["canonical_promotion"]["status"] == "promoted"
    selected_path = result["canonical_promotion"].get("path")
    lines = [
        "# P01d: promote P01b artifact to canonical ccb-data archive",
        "",
        "**Ticket:** `{}`".format(TICKET_ID),
        "",
        "## Raw ROOT reproduction",
        "",
        "The first audit step rescanned the raw B-stack ROOT files before artifact promotion, using the P01b/S00 gate: B2/B4/B6/B8 channels, median samples 0-3 baseline, and `A > 1000` ADC.",
        "",
        "| quantity | expected | reproduced | pass |",
        "|---|---:|---:|---|",
        "| selected B-stave pulses | {expected} | {got} | {passed} |".format(
            expected=EXPECTED_SELECTED,
            got=result["raw_root_recount"]["reproduced_selected_pulses"],
            passed="yes" if result["raw_root_recount"]["passed"] else "no",
        ),
        "",
        "## Artifact hash preservation",
        "",
        "| file | source bytes | source sha256 | matches P01c |",
        "|---|---:|---|---|",
    ]
    for artifact in result["source_artifacts"]:
        lines.append(
            "| `{file}` | {bytes} | `{sha256}` | {match} |".format(
                file=artifact["file"],
                bytes=artifact["bytes"],
                sha256=artifact["sha256"],
                match="yes" if artifact["matches_expected_sha256"] else "no",
            )
        )
    lines.extend(["", "## Canonical promotion", ""])
    if promoted:
        lines.extend(
            [
                "Promotion succeeded. The canonical retrieval path is:",
                "",
                "`{}`".format(selected_path),
                "",
                "| file | destination bytes | destination sha256 |",
                "|---|---:|---|",
            ]
        )
        for artifact in result["canonical_promotion"]["artifacts"]:
            lines.append(
                "| `{file}` | {bytes} | `{sha256}` |".format(
                    file=artifact["file"], bytes=artifact["bytes"], sha256=artifact["sha256"]
                )
            )
    else:
        lines.extend(
            [
                "Promotion is blocked in this worker: no requested canonical data path is writable.",
                "",
                "| target | status | error |",
                "|---|---|---|",
            ]
        )
        for attempt in result["promotion_attempts"]:
            lines.append(
                "| `{}` | {} | {} |".format(
                    attempt["target"],
                    attempt["status"],
                    "`{}`".format(attempt.get("error", "")) if attempt.get("error") else "",
                )
            )
        lines.extend(
            [
                "",
                "The preserved worker-local retrieval path from P01c remains:",
                "",
                "`{}`".format(SOURCE_DIR),
            ]
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- `input_sha256.csv` records all raw ROOT inputs scanned plus the two source artifact hashes.",
            "- `manifest.json` records the copy attempts and generated files.",
            "- The upstream P01b method comparison remains PCA-4 held-out MSE `0.013372` versus masked-denoising AE-4 MSE `0.014277`; P01d performs artifact promotion/audit only and does not refit models.",
        ]
    )
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="reports/{}".format(TICKET_ID))
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_root_dir = resolve_raw_root_dir()

    counts_by_run, counts_by_group, selected = recount_selected(raw_root_dir)
    source_artifacts = []
    for name, expected_hash in EXPECTED_HASHES.items():
        path = SOURCE_DIR / name
        got = sha256_file(path)
        source_artifacts.append(
            {
                "file": name,
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": got,
                "expected_sha256": expected_hash,
                "matches_expected_sha256": got == expected_hash,
            }
        )
        if got != expected_hash:
            raise RuntimeError("{} source hash mismatch".format(name))

    canonical_promotion, attempts = try_promote(CANONICAL_TARGETS)
    raw_inputs = []
    for run in configured_runs():
        path = raw_root_dir / "hrdb_run_{:04d}.root".format(run)
        raw_inputs.append({"kind": "raw_root", "path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    input_rows = raw_inputs + [
        {"kind": "source_artifact", "path": artifact["path"], "bytes": artifact["bytes"], "sha256": artifact["sha256"]}
        for artifact in source_artifacts
    ]

    result = {
        "ticket_id": TICKET_ID,
        "study_id": "P01d",
        "title": "promote P01b artifact to canonical ccb-data archive",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if canonical_promotion["status"] == "promoted" and selected == EXPECTED_SELECTED else "blocked",
        "upstream": {
            "p01b_ticket_id": UPSTREAM_P01B_TICKET,
            "p01c_ticket_id": UPSTREAM_P01C_TICKET,
            "p01c_report_dir": "reports/1781010024.910.7fbe14e8__p01c_publish_p01b_latent_artifact",
        },
        "raw_root_recount": {
            "raw_root_dir": str(raw_root_dir),
            "expected_selected_pulses": EXPECTED_SELECTED,
            "reproduced_selected_pulses": selected,
            "passed": selected == EXPECTED_SELECTED,
        },
        "source_artifacts": source_artifacts,
        "canonical_promotion": canonical_promotion,
        "promotion_attempts": attempts,
        "worker_local_fallback_path": str(SOURCE_DIR),
        "artifact_index": "reports/{}/P01D_ARTIFACT_INDEX.md".format(TICKET_ID),
    }

    write_csv(
        out_dir / "reproduction_counts_by_run.csv",
        counts_by_run,
        ["run", "group", "events_total", "events_with_selected", "selected_pulses", "B2", "B4", "B6", "B8"],
    )
    write_csv(
        out_dir / "reproduction_counts_by_group.csv",
        counts_by_group,
        ["group", "events_total", "events_with_selected", "selected_pulses", "B2", "B4", "B6", "B8"],
    )
    write_csv(out_dir / "input_sha256.csv", input_rows, ["kind", "path", "bytes", "sha256"])
    (out_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "ticket_id": TICKET_ID,
        "generated_at": result["generated_at"],
        "script": "scripts/p01d_promote_p01b_canonical_artifact.py",
        "raw_root_dir": str(raw_root_dir),
        "status": result["status"],
        "canonical_promotion": canonical_promotion,
        "promotion_attempts": attempts,
        "artifacts": [
            "REPORT.md",
            "P01D_ARTIFACT_INDEX.md",
            "result.json",
            "manifest.json",
            "input_sha256.csv",
            "reproduction_counts_by_run.csv",
            "reproduction_counts_by_group.csv",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, result)

    if result["status"] != "passed":
        print("P01d blocked: no canonical target was writable")
    else:
        print("P01d promoted: {}".format(canonical_promotion["path"]))
    print("raw selected pulses: {}".format(selected))


if __name__ == "__main__":
    main()
