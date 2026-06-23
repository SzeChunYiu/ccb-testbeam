#!/usr/bin/env python3
"""Thin wrapper: MV0 digitizer skeleton — truth hits to 18-sample ADC."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import yaml

from ccb_mc_validation.digitizer.pipeline import DigitizerPipeline


def main() -> None:
    ap = argparse.ArgumentParser(description="MV0 MC truth digitizer skeleton")
    ap.add_argument("--config", default="configs/mc_validation/digitizer.yaml")
    ap.add_argument("--out", help="override output directory")
    ap.add_argument("--event-id", type=int, default=42)
    ap.add_argument("--edep-mev", type=float, default=2.5)
    args = ap.parse_args()

    with Path(args.config).open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    out_dir = Path(args.out or config.get("output_dir", "reports/mv0_digitizer_skeleton"))
    out_dir.mkdir(parents=True, exist_ok=True)

    pipe = DigitizerPipeline.from_config(config.get("digitizer", config))
    hits = [{"edep_mev": args.edep_mev, "time_ns": 0.0}]
    result = pipe.run(hits, event_id=args.event_id)

    np.savez_compressed(
        out_dir / f"event_{args.event_id}_adc.npz",
        adc=result["adc"],
        saturated=result["saturated"],
        event_id=result["event_id"],
    )
    meta = {
        "event_id": result["event_id"],
        "n_samples": len(result["adc"]),
        "adc": result["adc"].tolist(),
        "saturated_any": bool(result["saturated"].any()),
    }
    with (out_dir / "digitizer_result.json").open("w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=2)

    print(json.dumps(meta, indent=2))
    print(f"[ok] wrote {out_dir}/digitizer_result.json")


if __name__ == "__main__":
    main()
