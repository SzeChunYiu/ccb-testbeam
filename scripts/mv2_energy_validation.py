#!/usr/bin/env python3
"""Thin wrapper: MV2 range-energy validation on GEANT4 truth tracks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml

from ccb_mc_validation.studies.common import write_study_result
from ccb_mc_validation.studies.mv2_energy_range import run_mv2
from ccb_mc_validation.studies.splits import SplitRegistry
from ccb_mc_validation.truth.tracks import load_tracks_from_root


def main() -> None:
    ap = argparse.ArgumentParser(description="MV2 truth-level range-energy validation")
    ap.add_argument("--config", default="configs/mc_validation/mv2.yaml")
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

    split = None
    split_name = config.get("split")
    if split_name and split_name != "legacy_parity":
        split = SplitRegistry.load(config.get("splits_config", "configs/mc_validation/splits.yaml"), split_name)

    result = run_mv2(records, config, split=split, fixture=args.fixture)
    result.provenance["mc_file"] = str(Path(mc_path).resolve())
    write_study_result(result, out_dir)

    keys = ("proton_ekin_recon_res68", "deuteron_ekin_recon_res68")
    summary = {k: result.metrics.get(k) for k in keys if k in result.metrics}
    print(json.dumps(summary, indent=2))
    print(f"[ok] wrote {out_dir}/study_result.json")


if __name__ == "__main__":
    main()
