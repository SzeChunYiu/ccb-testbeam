#!/usr/bin/env python3
# ruff: noqa: F403, F405
"""Beginner-facing raw-waveform timing study CLI.

Implementation is split into reviewable modules in this directory.  Use
``demo`` for fixed-seed known-answer demonstrations, ``raw`` for source-bound
ROOT data, and ``self-test`` for bounded regression checks.
"""
from student_timing_workflows import *  # noqa: F403


def self_test() -> None:
    physical = generate_physical_demo(3_000, 1729)
    physical_config = make_lane_config(
        physical,
        name="selftest_physical",
        description="self-test",
        polarity=PHYSICAL_MAP,
        authorising=False,
        watermark_text=None,
        polarity_status="SYNTHETIC",
        amplitude_cut_adc=600.0,
        analysis_fraction=0.50,
        component_identity_authorized=True,
        resolution_model_authorized=True,
    )
    physical_result = analyze_lane(physical, physical_config)
    rows = physical_result.pair_metrics[
        (physical_result.pair_metrics["stave_a"] == "B4")
        & (physical_result.pair_metrics["stave_b"] == "B6")
        & (physical_result.pair_metrics["fraction"] == 0.50)
    ]
    assert len(rows) == 1
    assert int(rows.iloc[0]["n"]) > 500
    assert 0.05 < float(rows.iloc[0]["sigma68_ns"]) < 0.20
    assert physical_result.inference.get("authorized") is True

    correct, legacy = generate_artifact_demo(3_000, 1730)
    legacy_config = make_lane_config(
        legacy,
        name="selftest_legacy",
        description="self-test",
        polarity=RETRACTED_ARTIFACT_MAP,
        authorising=False,
        watermark_text="NON_PHYSICAL",
        polarity_status="RETRACTED_TEST",
        amplitude_cut_adc=600.0,
        analysis_fraction=0.60,
        source_frame_authorized=False,
        component_identity_authorized=False,
    )
    legacy_result = analyze_lane(legacy, legacy_config)
    rows = legacy_result.pair_metrics[
        (legacy_result.pair_metrics["stave_a"] == "B4")
        & (legacy_result.pair_metrics["stave_b"] == "B6")
        & (legacy_result.pair_metrics["fraction"] == 0.60)
    ]
    assert len(rows) == 1
    assert int(rows.iloc[0]["n"]) > 500
    assert 0.05 < float(rows.iloc[0]["sigma68_ns"]) < 0.20
    assert float(rows.iloc[0]["rms_ns"]) > float(rows.iloc[0]["sigma68_ns"])
    assert correct.waveforms.shape[2] == 18
    assert legacy.waveforms.shape[2] == 16
    print("self-test: PASS")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo_parser = subparsers.add_parser("demo", help="run both synthetic teaching lanes")
    demo_parser.add_argument("--out", type=Path, required=True)
    demo_parser.add_argument("--events", type=int, default=30_000)
    demo_parser.add_argument("--seed", type=int, default=20260901)

    raw_parser = subparsers.add_parser("raw", help="run from source-bound ROOT waveforms")
    raw_parser.add_argument("--config", type=Path, required=True)
    raw_parser.add_argument("--out", type=Path, required=True)

    subparsers.add_parser("self-test", help="run bounded synthetic known-answer checks")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "self-test":
        self_test()
        return 0
    if args.command == "demo":
        summary = run_demo(args.out, args.events, args.seed)
    elif args.command == "raw":
        summary = run_raw(args.config, args.out)
    else:  # pragma: no cover - argparse enforces the command set.
        raise AssertionError(args.command)
    print(
        json.dumps(
            json_safe(summary), indent=2, sort_keys=True, allow_nan=False
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
