#!/usr/bin/env python3
"""Fail-closed audit for the MV3 selection-matched stopping-depth claim.

This tool checks whether a claimed selection-matched data/MC comparison:

* uses the source-specific ``PrimaryWeight`` vector for the physical MC result;
* treats the unweighted result only as a labelled sensitivity;
* uses the canonical signed-charge predicate rather than a positive-charge mask;
* binds the verdict to the canonical CL-021 ledger state;
* records content-addressed inputs and a controlled same-target comparison;
* avoids declaring shape agreement while the reported goodness-of-fit remains rejected.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

POLICY = "MV3_SELECTION_CLAIM_REQUIRES_WEIGHTED_SIGNED_CHARGE_AND_SAME_TARGET_VALIDATION"
STAVES = ("B2", "B4", "B6", "B8")


class AuditInputError(RuntimeError):
    """Controlled malformed-input error."""


@dataclass(frozen=True)
class Snapshot:
    path: str
    size_bytes: int
    sha256: str
    text: str


def _snapshot(path: Path) -> Snapshot:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise AuditInputError(
            f"INVALID_UTF8:{path}:{exc.start}:{exc.reason}"
        ) from exc
    return Snapshot(
        path=str(path),
        size_bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        text=text,
    )


def _require_no_alias(out: Path | None, inputs: list[Path]) -> None:
    if out is None:
        return
    out_resolved = out.resolve(strict=False)
    for path in inputs:
        if out_resolved == path.resolve(strict=False):
            raise AuditInputError(f"OUTPUT_ALIASES_INPUT:{out}:{path}")


def _read_json(snapshot: Snapshot) -> dict[str, Any]:
    try:
        data = json.loads(snapshot.text)
    except json.JSONDecodeError as exc:
        raise AuditInputError(f"INVALID_JSON:{snapshot.path}:{exc}") from exc
    if not isinstance(data, dict):
        raise AuditInputError(f"JSON_ROOT_NOT_OBJECT:{snapshot.path}")
    return data


def _read_cl021(snapshot: Snapshot) -> tuple[dict[str, str], int]:
    rows = list(csv.DictReader(snapshot.text.splitlines()))
    if not rows or not rows[0]:
        raise AuditInputError("LEDGER_EMPTY_OR_HEADER_MISSING")
    header = snapshot.text.splitlines()[0].split(",")
    width = len(header)
    matches = [row for row in rows if row.get("claim_id") == "CL-021"]
    if len(matches) != 1:
        raise AuditInputError(f"CL021_CARDINALITY:{len(matches)}")
    row = matches[0]
    if None in row:
        raise AuditInputError("CL021_ROW_WIDER_THAN_HEADER")
    if len(row) != width:
        raise AuditInputError(f"CL021_WIDTH:{len(row)}:{width}")
    return row, width


def _float(value: Any, label: str) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise AuditInputError(f"NONNUMERIC:{label}:{value!r}") from exc
    if not math.isfinite(out):
        raise AuditInputError(f"NONFINITE:{label}:{value!r}")
    return out


def _fractions(block: dict[str, Any], label: str) -> list[float]:
    frac = block.get("stop_depth_frac")
    counts = block.get("stop_depth_counts")
    if not isinstance(frac, dict) or not isinstance(counts, dict):
        raise AuditInputError(f"MISSING_STOPPING_PROFILE:{label}")
    values = [_float(frac.get(stave), f"{label}.{stave}.frac") for stave in STAVES]
    count_values = [_float(counts.get(stave), f"{label}.{stave}.count") for stave in STAVES]
    total = math.fsum(count_values)
    if total <= 0:
        raise AuditInputError(f"NONPOSITIVE_PROFILE_TOTAL:{label}")
    for stave, observed, count in zip(STAVES, values, count_values):
        expected = count / total
        if not math.isclose(observed, expected, rel_tol=0.0, abs_tol=5e-15):
            raise AuditInputError(
                f"COUNT_FRACTION_MISMATCH:{label}.{stave}:{observed}:{expected}"
            )
    if not math.isclose(math.fsum(values), 1.0, rel_tol=0.0, abs_tol=5e-15):
        raise AuditInputError(f"FRACTIONS_DO_NOT_SUM_TO_ONE:{label}")
    return values


def _counts(block: dict[str, Any], label: str) -> list[float]:
    counts = block.get("stop_depth_counts")
    if not isinstance(counts, dict):
        raise AuditInputError(f"MISSING_STOPPING_COUNTS:{label}")
    return [_float(counts.get(stave), f"{label}.{stave}.count") for stave in STAVES]


def _pearson_chi2_per_ndf(mc_frac: list[float], data_counts: list[float]) -> float:
    total = math.fsum(data_counts)
    terms: list[float] = []
    positive = 0
    for frac, observed in zip(mc_frac, data_counts):
        expected = frac * total
        if expected > 0:
            positive += 1
            terms.append((observed - expected) ** 2 / expected)
    ndf = positive - 1
    if ndf <= 0:
        raise AuditInputError("NONPOSITIVE_NDF")
    return math.fsum(terms) / ndf


def _has_full_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def audit(
    *,
    script: Snapshot,
    report: Snapshot,
    summary: Snapshot,
    ledger: Snapshot,
    weight_contract: Snapshot,
    pdg_helper: Snapshot,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    summary_obj = _read_json(summary)
    cl021, ledger_width = _read_cl021(ledger)

    mc = summary_obj.get("mc")
    data = summary_obj.get("data")
    if not isinstance(mc, dict) or not isinstance(data, dict):
        raise AuditInputError("SUMMARY_MISSING_MC_OR_DATA")
    mc_unselected = _fractions(mc.get("unselected", {}), "mc.unselected")
    mc_sample_i = _fractions(mc.get("sample_i", {}), "mc.sample_i")
    data_all_counts = _counts(data.get("all", {}), "data.all")
    data_sample_i_counts = _counts(data.get("sample_i", {}), "data.sample_i")
    data_sample_i_frac = _fractions(data.get("sample_i", {}), "data.sample_i")

    reported_improvement = _float(summary_obj.get("chi2_improvement_factor"), "improvement")
    chi_unselected_all = _pearson_chi2_per_ndf(mc_unselected, data_all_counts)
    chi_unselected_sample_i = _pearson_chi2_per_ndf(mc_unselected, data_sample_i_counts)
    chi_sample_i = _pearson_chi2_per_ndf(mc_sample_i, data_sample_i_counts)
    same_target_improvement = chi_unselected_sample_i / chi_sample_i
    b2_residual_pp = 100.0 * (data_sample_i_frac[0] - mc_sample_i[0])
    total_variation = 0.5 * math.fsum(
        abs(data_value - mc_value)
        for data_value, mc_value in zip(data_sample_i_frac, mc_sample_i)
    )

    source = script.text
    report_text = report.text
    weight_text = weight_contract.text
    helper_text = pdg_helper.text

    if "PrimaryWeight" in source and "w_evt" in source:
        weighted_fields = (
            "weighted_stop_depth_counts",
            "stop_depth_weight_sum",
            "primaryweight_applied",
        )
        if not any(token in source for token in weighted_fields):
            findings.append({
                "code": "PRIMARY_WEIGHT_READ_BUT_NOT_APPLIED",
                "message": (
                    "PrimaryWeight is read but no weighted stopping-profile "
                    "accumulator is emitted."
                ),
            })
    if "else 1.0" in source and "w_evt" in source:
        findings.append({
            "code": "PRIMARY_WEIGHT_FAIL_OPEN_DEFAULT",
            "message": "Missing or nonfinite PrimaryWeight is silently replaced with 1.0.",
        })
    if "pdg_charge(int(p)) >= 1" in source:
        findings.append({
            "code": "POSITIVE_CHARGE_ONLY_MASK",
            "message": "The charged-hit mask excludes negatively charged particles.",
        })
    if "abs(pdg_charge(int(pdg))) > 0.5" in helper_text and "is_charged" not in source:
        findings.append({
            "code": "CANONICAL_CHARGE_HELPER_DIVERGENCE",
            "message": "The study bypasses the canonical signed-charge predicate is_charged().",
        })
    if "must NOT be used" in report_text and "unweighted truth" in weight_text:
        findings.append({
            "code": "UNWEIGHTED_PHYSICAL_CLAIM_CONTRADICTS_WEIGHT_CONTRACT",
            "message": (
                "The report rejects PrimaryWeight even though the repository contract says "
                "it carries the cross-section factor and unweighted truth is not physical."
            ),
        })
    if (
        "NO physical differential cross-section weighting" in report_text
        and "PrimaryWeight" in source
    ):
        findings.append({
            "code": "RESIDUAL_ATTRIBUTION_IGNORES_AVAILABLE_WEIGHT",
            "message": (
                "The report attributes the residual to missing angular weighting while the "
                "available cross-section weight is loaded and discarded."
            ),
        })

    weighting = summary_obj.get("weighting")
    if not isinstance(weighting, dict) or weighting.get("primaryweight_applied") is not True:
        findings.append({
            "code": "SUMMARY_WEIGHT_CONTRACT_MISSING",
            "message": "Summary lacks an accepting PrimaryWeight policy and weighted-result flag.",
        })
    if not isinstance(weighting, dict) or not all(
        key in weighting for key in ("sum_w", "sum_w2", "effective_sample_size")
    ):
        findings.append({
            "code": "SUMMARY_WEIGHT_SUFFICIENT_STATISTICS_MISSING",
            "message": "Summary omits sum_w, sum_w2, and effective sample size.",
        })

    provenance = summary_obj.get("provenance")
    provenance_ok = isinstance(provenance, dict)
    if provenance_ok:
        provenance_ok = (
            _has_full_digest(provenance.get("mc_sha256"))
            and _has_full_digest(provenance.get("data_pulse_sha256"))
            and _has_full_digest(provenance.get("script_sha256"))
            and isinstance(provenance.get("source_commit"), str)
            and len(provenance["source_commit"]) == 40
            and bool(provenance.get("command"))
        )
    if not provenance_ok:
        findings.append({
            "code": "CONTENT_ADDRESSED_PROVENANCE_MISSING",
            "message": "Summary does not bind MC, data, script, commit, and command provenance.",
        })

    if summary_obj.get("comparison_policy") != "SAME_DATA_TARGET_FOR_SELECTION_ABLATION":
        findings.append({
            "code": "IMPROVEMENT_CHANGES_DATA_TARGET",
            "message": (
                "Reported improvement divides unselected-vs-all by selected-vs-Sample-I; "
                "a controlled selection ablation must hold the data target fixed."
            ),
        })
    if not math.isclose(
        reported_improvement, same_target_improvement, rel_tol=0.0, abs_tol=1e-9
    ):
        findings.append({
            "code": "REPORTED_IMPROVEMENT_NOT_SAME_TARGET",
            "message": (
                f"reported={reported_improvement:.12g}, same-target={same_target_improvement:.12g}"
            ),
        })

    verdict = str(summary_obj.get("verdict", ""))
    ledger_status = cl021.get("status", "")
    if "RESOLVED" in verdict and ledger_status == "FLAWED":
        findings.append({
            "code": "VERDICT_OUTRUNS_CANONICAL_LEDGER",
            "message": "Summary/report upgrade conflicts with canonical CL-021 status FLAWED.",
        })
    if ("shape matches" in report_text or "gap is gone" in report_text) and chi_sample_i > 10.0:
        findings.append({
            "code": "SHAPE_MATCH_CLAIM_WITH_REJECTED_CHI2",
            "message": f"Sample-I Pearson chi2/ndf remains {chi_sample_i:.6g}.",
        })
    if total_variation > 0.05 and "shape matches" in report_text:
        findings.append({
            "code": "SHAPE_MATCH_CLAIM_WITH_MATERIAL_TVD",
            "message": f"Sample-I total-variation distance is {total_variation:.6g}.",
        })

    sensitivity = summary_obj.get("sensitivity")
    required_sensitivity = {"gain", "threshold_adc", "coinc_ns", "weighting"}
    if not isinstance(sensitivity, dict) or not required_sensitivity.issubset(sensitivity):
        findings.append({
            "code": "PREREGISTERED_SENSITIVITY_SCAN_MISSING",
            "message": "No gain/threshold/coincidence/weighting sensitivity result is recorded.",
        })
    uncertainty = summary_obj.get("uncertainty")
    if (
        not isinstance(uncertainty, dict)
        or not uncertainty.get("mc_data_covariance_evaluated")
    ):
        findings.append({
            "code": "MC_DATA_UNCERTAINTY_NOT_EVALUATED",
            "message": "Finite weighted-MC and data uncertainty/covariance are not evaluated.",
        })

    status = "VALIDATED" if not findings else "FLAWED"
    return {
        "schema": "ccb-mv3-selection-claim-audit/1",
        "policy": POLICY,
        "status": status,
        "n_findings": len(findings),
        "findings": findings,
        "inputs": {
            name: {
                "path": snap.path,
                "size_bytes": snap.size_bytes,
                "sha256": snap.sha256,
            }
            for name, snap in (
                ("script", script),
                ("report", report),
                ("summary", summary),
                ("ledger", ledger),
                ("weight_contract", weight_contract),
                ("pdg_helper", pdg_helper),
            )
        },
        "ledger": {
            "header_width": ledger_width,
            "cl021_status": ledger_status,
            "cl021_truth_type": cl021.get("truth_type"),
            "cl021_blocked_by": cl021.get("blocked_by"),
        },
        "independent_calculations": {
            "reported_improvement_factor": reported_improvement,
            "same_target_unselected_vs_selected_improvement": same_target_improvement,
            "chi2_per_ndf_unselected_vs_all": chi_unselected_all,
            "chi2_per_ndf_unselected_vs_sample_i": chi_unselected_sample_i,
            "chi2_per_ndf_selected_vs_sample_i": chi_sample_i,
            "sample_i_b2_residual_percentage_points": b2_residual_pp,
            "sample_i_total_variation_distance": total_variation,
        },
        "scientific_boundary": (
            "This audit validates claim semantics and software/provenance contracts. "
            "It does not regenerate weighted production MC or establish detector closure."
        ),
    }


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--weight-contract", type=Path, required=True)
    parser.add_argument("--pdg-helper", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    inputs = [
        args.script,
        args.report,
        args.summary,
        args.ledger,
        args.weight_contract,
        args.pdg_helper,
    ]
    try:
        _require_no_alias(args.out, inputs)
        payload = audit(
            script=_snapshot(args.script),
            report=_snapshot(args.report),
            summary=_snapshot(args.summary),
            ledger=_snapshot(args.ledger),
            weight_contract=_snapshot(args.weight_contract),
            pdg_helper=_snapshot(args.pdg_helper),
        )
        if args.out is not None:
            _atomic_json(args.out, payload)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload["status"] == "VALIDATED" else 1
    except (AuditInputError, OSError) as exc:
        payload = {
            "schema": "ccb-mv3-selection-claim-audit/1",
            "policy": POLICY,
            "status": "INPUT_ERROR",
            "error": str(exc),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
