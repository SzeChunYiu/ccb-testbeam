#!/usr/bin/env python3
"""Build a content-addressed, fail-closed ledger from pytest CI diagnostics.

A single candidate log can classify failure families and direct test ownership, but
cannot establish that failures pre-date the candidate. Causal attribution requires
an exact same-environment baseline log and is reported explicitly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

TOOL_VERSION = "1.0.0"
POLICY = "REPOSITORY_CI_BLOCKER_MUST_HAVE_CONTENT_ADDRESSED_FAILURE_LEDGER"
ATTRIBUTION_SINGLE = "UNRESOLVED_SINGLE_RUN"
ATTRIBUTION_PAIRED = "PAIRED_BASELINE_COMPARISON"
SUMMARY_RE = re.compile(
    r"^(?P<failed>\d+) failed, (?P<passed>\d+) passed, "
    r"(?P<skipped>\d+) skipped, (?P<warnings>\d+) warnings in (?P<duration>.+)$"
)


class FailureLogError(ValueError):
    """Raised when CI diagnostics cannot support a traceable failure ledger."""


def _read_utf8(path: Path) -> tuple[bytes, str]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise FailureLogError(f"cannot read diagnostics {path}: {exc}") from exc
    try:
        return data, data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FailureLogError(f"diagnostics {path} are not valid UTF-8: {exc}") from exc


def _source_record(path: Path, data: bytes) -> dict[str, Any]:
    return {
        "path": str(path),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "snapshot_method": "SINGLE_READ_EXACT_BYTES",
    }


def _family(nodeid: str) -> str:
    path = nodeid.split("::", 1)[0]
    if path.startswith("tests/test_compare_stopping_power_"):
        return "stopping_power_compare"
    if path.startswith("tests/test_wiki_"):
        return "wiki_claim_binding"
    if path == "tests/test_validate_mv6_pca_claim_rows.py":
        return "mv6_pca_claim_rows"
    if path in {"tests/test_figure_registry.py", "tests/test_pubfig_migration.py"}:
        return "figure_registry"
    if path == "tests/test_audit_mv4_legacy_claim_rows.py":
        return "mv4_legacy_claim_rows"
    if path == "tests/test_validate_clusterd_claim_governance.py":
        return "clusterd_claim_governance"
    if path == "tests/test_deltae_data_bridge_strict.py":
        return "deltae_data_bridge"
    if path == "tests/test_validate_chapter8_mv1_claims.py":
        return "chapter8_claim_validator"
    if path == "tests/test_validate_mv3_legacy_claim_rows.py":
        return "mv3_legacy_claim_rows"
    return "other"


def _signature(message: str) -> str:
    if "KeyError: 'energy_deposit_basis'" in message:
        return "MISSING_SIMULATION_SUMMARY_BASIS"
    if "KeyError: 'input_sha256'" in message:
        return "MISSING_REFERENCE_SUMMARY_PROVENANCE"
    if "DID NOT RAISE" in message:
        return "EXPECTED_FAIL_CLOSED_EXCEPTION_ABSENT"
    if "canonical results table was not found" in message or "Canonical Results Table" in message:
        return "WIKI_CANONICAL_SECTION_MISSING"
    if "pca_cumulative_at_8 disagrees" in message:
        return "PCA_SUMMARY_COMPONENT_MISMATCH"
    if "OUTPUT_ALIAS_INPUT" in message and "OUTPUT_ALIASES_INPUT" in message:
        return "VALIDATOR_FINDING_CODE_DRIFT"
    if "assert [] ==" in message:
        return "VALIDATOR_RETURNED_EMPTY_ROWS"
    if "assert 'FLAWED' == 'VALIDATED'" in message:
        return "CURRENT_ARTIFACT_FAILS_OWN_ACCEPTANCE_TEST"
    if "non-strict build should exit 0" in message:
        return "NONSTRICT_REGISTRY_EXIT_CONTRACT_MISMATCH"
    if "assert 1 == 0" in message or "assert 2 == 0" in message:
        return "CLI_EXIT_STATUS_MISMATCH"
    if "Regex pattern did not match" in message:
        return "EXPECTED_DIAGNOSTIC_TEXT_MISMATCH"
    return "OTHER_ASSERTION_OR_INPUT_MISMATCH"


def _parse(text: str, path: Path) -> tuple[list[dict[str, str]], dict[str, Any]]:
    failures: list[dict[str, str]] = []
    summary: dict[str, Any] | None = None
    for line in text.splitlines():
        if line.startswith("FAILED ") and " - " in line:
            nodeid, message = line[len("FAILED "):].rsplit(" - ", 1)
            failures.append(
                {
                    "nodeid": nodeid,
                    "message": message,
                    "family": _family(nodeid),
                    "signature": _signature(message),
                }
            )
            continue
        summary_match = SUMMARY_RE.match(line)
        if summary_match:
            summary = {
                "failed": int(summary_match.group("failed")),
                "passed": int(summary_match.group("passed")),
                "skipped": int(summary_match.group("skipped")),
                "warnings": int(summary_match.group("warnings")),
                "duration": summary_match.group("duration"),
            }
    if summary is None:
        raise FailureLogError(f"diagnostics {path} have no terminal pytest summary")
    if not failures:
        raise FailureLogError(f"diagnostics {path} have no FAILED summary entries")
    nodeids = [item["nodeid"] for item in failures]
    duplicate_nodeids = sorted(nodeid for nodeid, count in Counter(nodeids).items() if count > 1)
    if duplicate_nodeids:
        raise FailureLogError(
            "diagnostics contain duplicate FAILED node IDs: " + ", ".join(duplicate_nodeids)
        )
    if summary["failed"] != len(failures):
        raise FailureLogError(
            f"terminal failed count {summary['failed']} disagrees with "
            f"{len(failures)} FAILED entries"
        )
    return failures, summary


def _compare_failures(
    candidate: list[dict[str, str]], baseline: list[dict[str, str]] | None
) -> dict[str, Any]:
    candidate_map = {item["nodeid"]: item["signature"] for item in candidate}
    if baseline is None:
        return {
            "mode": ATTRIBUTION_SINGLE,
            "introduced": None,
            "resolved": None,
            "persistent": None,
            "statement": (
                "A single candidate log cannot establish that cross-area failures are "
                "pre-existing; an exact same-environment baseline run is required."
            ),
        }
    baseline_map = {item["nodeid"]: item["signature"] for item in baseline}
    introduced = sorted(set(candidate_map) - set(baseline_map))
    resolved = sorted(set(baseline_map) - set(candidate_map))
    persistent = sorted(set(candidate_map) & set(baseline_map))
    changed_signature = sorted(
        nodeid
        for nodeid in persistent
        if candidate_map[nodeid] != baseline_map[nodeid]
    )
    return {
        "mode": ATTRIBUTION_PAIRED,
        "introduced": introduced,
        "resolved": resolved,
        "persistent": persistent,
        "changed_signature": changed_signature,
        "statement": "Attribution compares exact node IDs from paired logs only.",
    }


def classify(
    candidate_log: Path,
    *,
    baseline_log: Path | None = None,
    candidate_test_prefixes: tuple[str, ...] = (),
) -> dict[str, Any]:
    candidate_bytes, candidate_text = _read_utf8(candidate_log)
    candidate_failures, candidate_summary = _parse(candidate_text, candidate_log)

    baseline_record: dict[str, Any] | None = None
    baseline_failures: list[dict[str, str]] | None = None
    if baseline_log is not None:
        baseline_bytes, baseline_text = _read_utf8(baseline_log)
        baseline_failures, baseline_summary = _parse(baseline_text, baseline_log)
        baseline_record = {
            "source": _source_record(baseline_log, baseline_bytes),
            "summary": baseline_summary,
        }

    family_counts = dict(sorted(Counter(item["family"] for item in candidate_failures).items()))
    signature_counts = dict(
        sorted(Counter(item["signature"] for item in candidate_failures).items())
    )
    direct_candidate_failures = sorted(
        item["nodeid"]
        for item in candidate_failures
        if any(item["nodeid"].startswith(prefix) for prefix in candidate_test_prefixes)
    )
    return {
        "schema_version": 1,
        "tool": "tools/audit/classify_ci_failure_log.py",
        "tool_version": TOOL_VERSION,
        "policy": POLICY,
        "status": "VALIDATED",
        "candidate": {
            "source": _source_record(candidate_log, candidate_bytes),
            "summary": candidate_summary,
            "failure_count": len(candidate_failures),
            "family_counts": family_counts,
            "signature_counts": signature_counts,
            "failures": candidate_failures,
        },
        "baseline": baseline_record,
        "candidate_test_prefixes": list(candidate_test_prefixes),
        "direct_candidate_test_failures": direct_candidate_failures,
        "direct_candidate_test_failure_count": len(direct_candidate_failures),
        "causal_attribution": _compare_failures(candidate_failures, baseline_failures),
        "acceptance_boundary": (
            "This ledger makes the blocker reproducible. It does not authorize merging while "
            "the repository-wide gate is red and does not label failures pre-existing without "
            "a paired baseline run."
        ),
    }


def _paths_alias(left: Path, right: Path) -> bool:
    left = left.expanduser().resolve(strict=False)
    right = right.expanduser().resolve(strict=False)
    if left == right:
        return True
    try:
        return left.exists() and right.exists() and os.path.samefile(left, right)
    except OSError:
        return False


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate_log", type=Path)
    parser.add_argument("--baseline-log", type=Path)
    parser.add_argument("--candidate-test-prefix", action="append", default=[])
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    inputs = [args.candidate_log]
    if args.baseline_log is not None:
        inputs.append(args.baseline_log)
    if args.output is not None and any(_paths_alias(args.output, item) for item in inputs):
        print("INPUT ERROR: output path aliases an input log")
        return 2
    try:
        payload = classify(
            args.candidate_log,
            baseline_log=args.baseline_log,
            candidate_test_prefixes=tuple(args.candidate_test_prefix),
        )
        if args.output is not None:
            _write_json_atomic(args.output, payload)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    except FailureLogError as exc:
        print(f"INPUT ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
