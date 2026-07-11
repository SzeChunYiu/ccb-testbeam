#!/usr/bin/env python3
"""P04n3 runner for B-stack trigger-code semantics."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import p04n_1781101446_892_139c702a_forced_random_pedestal_validation as p04n


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/p04n3_1783714082_13505_551221eb_bstack_trigger_code_semantics.json"


EXTERNAL_METADATA = {
    "context_source": "reports/1781110796.1578.28f051c2__s16i_external_daq_runlog_checksum_join",
    "visible_hrd_root_files_in_checksum_manifest": 110,
    "bstack_root_files_in_manifest": 53,
    "independent_external_daq_records_joined": 0,
    "external_daq_candidate_records_joined_to_bstack_runs": 0,
    "scaler_metadata_files_joined_to_bstack_runs": 0,
    "nonbeam_trigger_entries_in_visible_root": 0,
    "trigger_code_1_exhausts_visible_mirror": True,
    "distinguishes_true_nonacquisition_from_mirror_omission": False,
    "interpretation": (
        "No mounted external DAQ run log or scaler metadata joins to B-stack ROOT runs; "
        "trigger code 1 is exhaustive for visible data/root/root entries but cannot prove "
        "whether forced/random pedestal acquisitions were never taken or omitted from the mirror."
    ),
}


def _metadata_table() -> str:
    rows = [
        ("visible HRD ROOT files in checksum manifest", EXTERNAL_METADATA["visible_hrd_root_files_in_checksum_manifest"]),
        ("B-stack ROOT files in manifest", EXTERNAL_METADATA["bstack_root_files_in_manifest"]),
        ("independent external DAQ records joined", EXTERNAL_METADATA["independent_external_daq_records_joined"]),
        (
            "external DAQ candidate records joined to B-stack runs",
            EXTERNAL_METADATA["external_daq_candidate_records_joined_to_bstack_runs"],
        ),
        ("scaler metadata files joined to B-stack runs", EXTERNAL_METADATA["scaler_metadata_files_joined_to_bstack_runs"]),
        ("non-beam trigger entries in visible ROOT", EXTERNAL_METADATA["nonbeam_trigger_entries_in_visible_root"]),
    ]
    lines = ["| metadata audit item | value |", "|---|---:|"]
    lines.extend(f"| {name} | {value} |" for name, value in rows)
    return "\n".join(lines)


def _write_external_metadata_summary(out_dir: Path) -> None:
    rows = [
        {"item": key, "value": value}
        for key, value in EXTERNAL_METADATA.items()
        if key != "interpretation"
    ]
    rows.append({"item": "interpretation", "value": EXTERNAL_METADATA["interpretation"]})
    pd.DataFrame(rows).to_csv(out_dir / "external_metadata_summary.csv", index=False)


def _replace_between(text: str, start: str, end: str, replacement: str) -> str:
    start_idx = text.index(start) + len(start)
    end_idx = text.index(end, start_idx)
    return text[:start_idx] + "\n\n" + replacement.strip() + "\n\n" + text[end_idx:]


def _patch_result(out_dir: Path) -> dict:
    path = out_dir / "result.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    winner = result["winner"]
    best_trad = result["best_traditional"]
    source = result["forced_random_pedestal_source"]
    result["external_daq_scaler_metadata"] = EXTERNAL_METADATA
    result["finding"] = (
        f"Raw ROOT reproduction passes exactly "
        f"({result['raw_reproduction']['reproduced_selected_pulses']:,} selected B-stave pulses; "
        f"delta {result['raw_reproduction']['delta']:+,}). No accessible forced/random pedestal "
        f"B-stack ROOT source was found: {source['n_bstack_raw_root_files']} B-stack files carry only "
        f"trigger code(s) {source['unique_trigger_codes']} and keyword search found "
        f"{source['n_keyword_root_files']} candidate ROOT files. The external DAQ run-log/checksum-join "
        "context likewise joins 0 independent run-log or scaler records to the ROOT manifest, so the "
        "mounted trigger code 1 should be interpreted as exhaustive only for the visible data/root/root "
        "mirror, not as proof that forced/random pedestal acquisitions never existed. On the external "
        f"downstream charge proxy, {winner['method']} wins with res68 {winner['res68_abs_frac']:.4f} "
        f"[{winner['res68_ci95'][0]:.4f}, {winner['res68_ci95'][1]:.4f}], versus the traditional "
        f"comparator {best_trad['method']} at {best_trad['res68_abs_frac']:.4f}. This validates P04m "
        "only as a physics-event pretrigger support diagnostic, not as a true forced/random pedestal veto."
    )
    result["hypothesis"] = (
        "The high-pretrigger P04m cells are likely electronics-support boundary markers that expose "
        "charge-transfer fragility, but without true forced/random pedestal rows or joinable external "
        "DAQ/scaler metadata they cannot be interpreted as independently measured pedestal disturbances. "
        "Trigger code 1 exhausts the mounted B-stack ROOT mirror; the current evidence cannot prove whether "
        "this is true non-acquisition or omission from the mirror. The external proxy still favors tree-based "
        "waveform/context models over the traditional Huber comparator, while the same-event duplicate closure "
        "remains much sharper than downstream transfer."
    )
    path.write_text(json.dumps(p04n.json_ready(result), indent=2) + "\n", encoding="utf-8")
    return result


def _patch_report(out_dir: Path, result: dict) -> None:
    path = out_dir / "REPORT.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "# P04n3: Forced-random pedestal validation of P04m pretrigger abstention",
        "# P04n3: B-stack trigger-code semantics from DAQ run-log and scaler metadata",
    )
    text = text.replace(
        "- **Inputs:** raw B-stack ROOT under `data/root/root`, P04m predecessor artifacts, and S16f forced/random inventory context.",
        "- **Inputs:** raw B-stack ROOT under `data/root/root`, P04m predecessor artifacts, S16f forced/random inventory context, and the S16i external DAQ run-log/checksum-join audit.",
    )
    text = _replace_between(text, "## Abstract", "## 1. Pre-registered question", result["finding"])
    text = text.replace(
        "The ticket asks whether P04m high-pretrigger abstention regions correspond to independently measured forced/random pedestal disturbances and whether those regions predict external charge-proxy failure after amplitude, saturation, run, and topology matching. The primary decision rule is: first establish whether a dedicated forced/random B-stack pedestal ROOT source exists; if absent, do not promote the pretrigger map to a true pedestal validation and instead quantify its external charge-proxy behavior as a physics-event pretrigger support diagnostic.",
        "The ticket asks whether external DAQ run logs or scaler metadata can explain whether the mounted B-stack ROOT trigger code 1 exhausts all acquisition modes, or whether forced/random pedestal triggers were recorded outside `data/root/root`. The primary decision rule is: first establish whether a dedicated forced/random B-stack pedestal ROOT source or independent run-log/scaler join exists; if absent, do not promote the pretrigger map to a true pedestal validation and instead quantify its external charge-proxy behavior as a physics-event pretrigger support diagnostic.",
    )
    external_section = "\n".join(
        [
            "## 4. External DAQ run-log and scaler metadata audit",
            "",
            "The P04n3-specific evidence comes from the S16i external DAQ run-log/checksum join, reranked here as metadata context rather than as a new waveform label. That audit searched the configured data mirror and known external roots for DAQ/logbook/trigger/beam/pedestal/forced/random/scaler-like records, then attempted a join to the ROOT checksum manifest. It found no independent acquisition record that joins to HRD ROOT rows.",
            "",
            _metadata_table(),
            "",
            "Operational interpretation:",
            "",
            "- Within the mounted `data/root/root` mirror, trigger code 1 is exhaustive for populated B-stack ROOT entries.",
            "- The same evidence does not distinguish true non-acquisition from mirror omission, because no independent DAQ run log or scaler table is mounted and joinable.",
            "- Therefore a direct P04m pedestal-veto validation remains blocked; the only defensible quantitative endpoint here is the downstream physics-event charge-proxy transfer benchmark.",
            "",
        ]
    )
    text = text.replace("## 4. Estimands and equations", external_section + "## 5. Estimands and equations")
    for old, new in [
        ("## 10. Reproducibility", "## 11. Reproducibility"),
        ("## 9. Verdict and hypothesis", "## 10. Verdict and hypothesis"),
        ("## 8. Systematics and caveats", "## 9. Systematics and caveats"),
        ("## 7. Required method-family context", "## 8. Required method-family context"),
        ("## 6. Pretrigger risk stratification", "## 7. Pretrigger risk stratification"),
        ("## 5. External charge-proxy benchmark", "## 6. External charge-proxy benchmark"),
    ]:
        text = text.replace(old, new)
    text = text.replace(
        "- The external endpoint is a downstream charge proxy, not deposited-energy truth.",
        "- The external DAQ/scaler audit joins 0 independent acquisition records, so trigger-code semantics are closed only for the visible mirror.\n- The external endpoint is a downstream charge proxy, not deposited-energy truth.",
    )
    text = _replace_between(text, "## 10. Verdict and hypothesis", "## 11. Reproducibility", result["hypothesis"])
    old_local_command = (
        str(Path.home() / "anaconda3/bin/python")
        + " scripts/p04n3_1783714082_13505_551221eb_bstack_trigger_code_semantics.py"
    )
    text = text.replace(old_local_command, "python scripts/p04n3_1783714082_13505_551221eb_bstack_trigger_code_semantics.py")
    path.write_text(text, encoding="utf-8")


def _refresh_manifest(out_dir: Path, config: dict) -> None:
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["command"] = config["runner_command"]
    manifest["outputs"] = p04n.output_hashes(out_dir)
    manifest_path.write_text(json.dumps(p04n.json_ready(manifest), indent=2) + "\n", encoding="utf-8")


def postprocess() -> None:
    config = p04n.load_config(CONFIG)
    out_dir = ROOT / config["output_dir"]
    _write_external_metadata_summary(out_dir)
    result = _patch_result(out_dir)
    _patch_report(out_dir, result)
    _refresh_manifest(out_dir, config)


def main() -> int:
    import sys

    sys.argv = [sys.argv[0], "--config", str(CONFIG)]
    status = p04n.main()
    if status == 0:
        postprocess()
    return status


if __name__ == "__main__":
    raise SystemExit(main())
