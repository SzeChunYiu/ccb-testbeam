#!/usr/bin/env python3
"""Thin wrapper: MV3 stopping-depth / Sample I vs II profile study."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml

from ccb_mc_validation.studies.common import write_study_result
from ccb_mc_validation.studies.mv3_stopping_depth import run_mv3
from ccb_mc_validation.truth.tracks import load_tracks_from_root


def main() -> None:
    ap = argparse.ArgumentParser(description="MV3 stopping-depth profile validation")
    ap.add_argument("--config", default="configs/mc_validation/mv3.yaml")
    ap.add_argument("--mc", help="override MC ROOT path")
    ap.add_argument("--out", help="override output directory")
    ap.add_argument("--fixture", action="store_true")
    args = ap.parse_args()

    with Path(args.config).open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    mc_path = args.mc or config["mc_file"]
    out_dir = Path(args.out or config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    records = load_tracks_from_root(
        mc_path,
        tree_name=config.get("tree", "hibeam"),
        max_events=int(config.get("max_events", 0)),
    )

    data_profiles = config.get("data_reference_profiles")
    result = run_mv3(records, config, data_profiles=data_profiles, fixture=args.fixture)
    result.provenance["mc_file"] = str(Path(mc_path).resolve())
    write_study_result(result, out_dir)

    print(json.dumps({"status": result.status.value, "cutflow": result.cutflow}, indent=2))
    print(f"[ok] wrote {out_dir}/study_result.json")


if __name__ == "__main__":
    main()
