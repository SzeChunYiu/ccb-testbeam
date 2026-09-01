#!/usr/bin/env python3
# ruff: noqa: F403, F405
"""Fail-closed diagnostics for the historical CCB timing result."""
from timing_result_audit_core import *  # noqa: F403
from timing_result_audit_outputs import *  # noqa: F403


def run_self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        result_path = root / "result.json"
        map_path = root / "map.json"
        result_path.write_text(
            json.dumps(
                {
                    "n_complete_pair_events": 100,
                    "evaluation": [
                        {
                            "fraction": row["fraction"],
                            "sigma68_ns": row["sigma68_ns"],
                            "core_sigma_ns": row["core_sigma_ns"],
                            "full_rms_ns": row["rms_ns"],
                            "core_chi2_ndf": row["chi2_ndf"],
                        }
                        for row in FROZEN_FRACTION_ROWS
                    ],
                    "cfd_status": {"t_cfd20": {"n_finite": 200}},
                }
            ),
            encoding="utf-8",
        )
        map_path.write_text(json.dumps({"status": "RETRACTED_TEST"}), encoding="utf-8")
        result = read_json(result_path)
        rows, source = extract_fraction_rows(result)
        status, _ = polarity_status(map_path)
        outcome = audit_result(result, rows, status)
        assert source == "parsed_from_result_json"
        assert outcome.single_stave_resolution_authorized is False
        codes = {finding.code for finding in outcome.findings}
        assert "RETRACTED_POLARITY_MAP" in codes
        assert "WAVEFORM_ROWS_LABELLED_AS_EVENTS" in codes
        assert "PAIR_ONLY_UNDERDETERMINED" in codes
    print("self-test: PASS")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, help="Issue/result JSON to audit")
    parser.add_argument("--polarity-map", type=Path, help="Channel polarity JSON")
    parser.add_argument("--out", type=Path, default=Path("timing_diagnostic_output"))
    parser.add_argument(
        "--allow-gated-exit-zero",
        action="store_true",
        help="Return zero even when no physical resolution is authorized",
    )
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument(
        "--allow-frozen-fallback",
        action="store_true",
        help=(
            "Use the checked-in Issue #1320 table only when live JSON rows cannot "
            "be parsed; disabled by default to prevent stale-result substitution"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        run_self_test()
        return 0
    if args.result is None:
        raise SystemExit("--result is required unless --self-test is used")

    args.out.mkdir(parents=True, exist_ok=True)
    result = read_json(args.result)
    rows, rows_source = extract_fraction_rows(
        result, allow_frozen_fallback=args.allow_frozen_fallback
    )
    map_status, _ = polarity_status(args.polarity_map)
    outcome = audit_result(result, rows, map_status)

    write_fraction_table(rows, args.out / "fraction_metrics.csv")
    plot_width_scan(rows, args.out)
    plot_non_gaussianity(rows, args.out)
    plot_fit_quality(rows, args.out)
    counterexamples = plot_deconvolution_counterexamples(args.out)
    plot_inference_gate(args.out)

    payload = asdict(outcome)
    payload["fraction_table_source"] = rows_source
    payload["polarity_map_status"] = map_status
    payload["sqrt2_counterexamples"] = counterexamples
    (args.out / "audit_summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    write_markdown_summary(args.out, rows_source, map_status, outcome, counterexamples)

    print(json.dumps(payload, indent=2, sort_keys=True))
    if outcome.single_stave_resolution_authorized or args.allow_gated_exit_zero:
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
