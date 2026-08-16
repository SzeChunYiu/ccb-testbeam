#!/usr/bin/env python3
"""Freeze-check MV0 executable digitizer identity (#1078)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

VERSION = "1.0.0"


def validate(repo: Path) -> list[str]:
    errors: list[str] = []
    ident_path = repo / "docs/contracts/MV0_DIGITIZER_MODEL_IDENTITY.json"
    ident = json.loads(ident_path.read_text(encoding="utf-8"))
    src = repo / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from ccb_mc_validation.digitizer.pipeline import DigitizerPipeline
    from ccb_mc_validation.digitizer.electronics import ElectronicsConfig

    pipe = DigitizerPipeline()
    elec = ElectronicsConfig()
    frozen = ident["frozen_defaults"]
    checks = [
        ("n_samples", pipe.n_samples, frozen["n_samples"]),
        ("sample_spacing_ns", pipe.sample_spacing_ns, frozen["sample_spacing_ns"]),
        ("tau_rise_ns", pipe.tau_rise_ns, frozen["tau_rise_ns"]),
        ("tau_decay_ns", pipe.tau_decay_ns, frozen["tau_decay_ns"]),
        ("transport_sigma_ns", pipe.transport_sigma_ns, frozen["transport"]["sigma_ns"]),
        ("gain_adc_per_mev", elec.gain_adc_per_mev, frozen["electronics"]["gain_adc_per_mev"]),
        ("noise_adc_rms", elec.noise_adc_rms, frozen["electronics"]["noise_adc_rms"]),
        ("adc_bits", elec.adc_bits, frozen["electronics"]["adc_bits"]),
        ("adc_ceiling", elec.adc_ceiling, frozen["electronics"]["adc_ceiling"]),
        ("apply_birks", pipe.apply_birks, frozen["apply_birks_default"]),
    ]
    for name, got, exp in checks:
        if got != exp:
            errors.append(f"IDENTITY_DRIFT:{name}:got={got}:expected={exp}")
    # Chapter must not silently claim ACCEPTED while divergent
    ch10 = (repo / "docs/academic_chapters/10_mc_validation.md").read_text(encoding="utf-8")
    head = "\n".join(ch10.splitlines()[:20])
    if "DIVERGENT_FROM_EXECUTABLE" not in head and "245.6" in ch10:
        errors.append("CHAPTER10_MISSING_DIVERGENCE_BANNER")
    mid = getattr(pipe, "model_identity", None)
    if callable(mid):
        live = mid()
        if live.get("model_id") != ident.get("model_id"):
            errors.append(f"MODEL_ID_MISMATCH:{live.get('model_id')}")
    else:
        errors.append("MISSING_PIPELINE_MODEL_IDENTITY_METHOD")
    return errors


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = p.parse_args(argv)
    errs = validate(args.repo_root)
    if errs:
        print("FAIL")
        for e in errs:
            print(e)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
