#!/usr/bin/env python3
"""Scoped source/claim consistency checks; never a scientific release certificate.

Default input is a disclosed field projection of connector-read repository data.
--repo reads the actual full files and verifies their Git blob identities against
that projection. Exit 0 = scoped metadata checks clear, 1 = known inconsistencies,
2 = malformed input or execution failure. No source or ledger is modified.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

STATES = frozenset({"NOT_REVIEWED", "BLOCKED", "GATED", "FLAWED", "RETRACTED",
                    "SUPERSEDED", "SUPPORTED", "VALIDATED", "DONE_DATA_ONLY",
                    "DIAGNOSTIC", "MC_METHOD_CLOSURE", "TRUTH_LEVEL_MC_ONLY"})
INVALID = frozenset({"FLAWED", "RETRACTED"})
PENDING = frozenset({"NOT_REVIEWED", "BLOCKED", "GATED", "SUPERSEDED"})
HERE = Path(__file__).resolve().parent


def parse_json(text: str) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in items:
            if key in out:
                raise ValueError(f"duplicate JSON key: {key}")
            out[key] = value
        return out

    def invalid(value: str) -> None:
        raise ValueError(f"nonfinite JSON constant: {value}")

    obj = json.loads(text, object_pairs_hook=pairs,
                     parse_constant=invalid)
    if not isinstance(obj, dict):
        raise ValueError("top-level JSON must be an object")
    return obj


def strict_json(path: Path) -> dict[str, Any]:
    return parse_json(path.read_text(encoding="utf-8"))


def graph_check(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    """Propagate known invalid/pending/stale ancestors; retain every root cause."""
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("nonempty atomic graph required; empty is not complete")
    index: dict[str, dict[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("node must be an object")
        ident = node.get("id")
        if not isinstance(ident, str) or not ident.strip() or ident in index:
            raise ValueError("missing/duplicate atomic ID")
        if node.get("state") not in STATES:
            raise ValueError(f"{ident}: unknown state")
        revision = node.get("revision")
        if not isinstance(revision, str) or not revision.strip():
            raise ValueError(f"{ident}: missing revision")
        if not isinstance(node.get("requires"), list):
            raise ValueError(f"{ident}: explicit requires list required")
        index[ident] = node
    for ident, node in index.items():
        seen: set[str] = set()
        for dep in node["requires"]:
            if not isinstance(dep, dict) or dep.get("id") not in index:
                raise ValueError(f"{ident}: unresolved dependency")
            if dep["id"] in seen:
                raise ValueError(f"{ident}: duplicate dependency")
            seen.add(dep["id"])
            if not isinstance(dep.get("revision"), str) or not dep["revision"].strip():
                raise ValueError(f"{ident}: dependency revision missing")
    visiting: set[str] = set()
    complete: set[str] = set()
    order: list[str] = []
    causes: dict[str, dict[str, set[str]]] = {}

    def visit(ident: str) -> None:
        if ident in visiting:
            raise ValueError(f"cycle at {ident}; coordination refs are not a DAG")
        if ident in complete:
            return
        visiting.add(ident)
        node = index[ident]
        current = {"invalid": set(), "pending": set(), "stale": set()}
        if node["state"] in INVALID:
            current["invalid"].add(ident)
        if node["state"] in PENDING:
            current["pending"].add(ident)
        for dep in node["requires"]:
            parent = dep["id"]
            visit(parent)
            for kind in current:
                current[kind].update(causes[parent][kind])
            if dep["revision"] != index[parent]["revision"]:
                current["stale"].add(f"{ident}->{parent}")
        causes[ident] = current
        visiting.remove(ident)
        complete.add(ident)
        order.append(ident)

    for ident in sorted(index):
        visit(ident)
    effective: dict[str, str] = {}
    for ident in order:
        c = causes[ident]
        effective[ident] = ("INVALIDATED" if c["invalid"] else
                            "STALE_RECOMPUTE_REQUIRED" if c["stale"] else
                            "BLOCKED_PENDING_EVIDENCE" if c["pending"] else
                            "NO_KNOWN_GRAPH_BLOCKER")
    return {"topological_order": order, "effective_states": effective,
            "root_causes": {k: {t: sorted(v) for t, v in c.items()}
                            for k, c in causes.items()},
            "scope_clear": all(v == "NO_KNOWN_GRAPH_BLOCKER" for v in effective.values()),
            "global_release_authorized": False,
            "scope_notice": "Only declared edges checked. Identity, physics validity and exhaustive coverage are not certified."}


def finite_number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("quantitative value must be numeric, not bool/string")
    if not math.isfinite(value):
        raise ValueError("quantitative value must be finite")
    return float(value)


def count(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("counts must be nonnegative integer counts")
    return value


def audit(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema") != "ccb-publication-assurance-projection/1":
        raise ValueError("unsupported schema")
    graph = graph_check(payload.get("nodes"))
    findings: list[dict[str, Any]] = []
    for ident, node_state in graph["effective_states"].items():
        roots = graph["root_causes"][ident]
        # Root retraction itself is evidence; dependent live claims are the inconsistency.
        original = next(x for x in payload["nodes"] if x["id"] == ident)
        if roots["invalid"] and original["state"] not in INVALID | {"SUPERSEDED"}:
            findings.append({"code": "RETRACTED_OR_FLAWED_ANCESTOR", "claim_id": ident,
                             "ledger_state": original["state"], "effective_state": node_state,
                             "invalid_roots": roots["invalid"]})
    checks = payload.get("quantitative_checks")
    if not isinstance(checks, list):
        raise ValueError("quantitative_checks must be explicit")
    for item in checks:
        n_ledger = count(item["ledger_n_events"])
        n_artifact = count(item["artifact_n_heldout"])
        observed = finite_number(item["artifact_value"])
        stated = finite_number(item["ledger_value"])
        if n_ledger != n_artifact:
            findings.append({"code": "SAMPLE_COUNT_MISMATCH", "claim_id": item["claim_id"],
                             "ledger_n_events": n_ledger, "artifact_n_heldout": n_artifact})
        if stated != observed:
            findings.append({"code": "NUMERICAL_VALUE_MISMATCH", "claim_id": item["claim_id"],
                             "ledger_value": stated, "artifact_value": observed})
    return {"status": "SCOPED_INCONSISTENCIES_FOUND" if findings else "SCOPED_CHECK_CLEAR",
            "scientific_release": "NOT_AUTHORIZED", "complete_repository_inventory": False,
            "input_scope": payload.get("scope"), "graph": graph, "findings": findings,
            "finding_count": len(findings),
            "boundary": "Checks metadata/provenance consistency only; no raw-data reprocessing or physics revalidation."}


def repository_payload(repo: Path, projection: dict[str, Any]) -> dict[str, Any]:
    """Read pinned whole-file bytes; refuse drift instead of reusing old conclusions."""
    data: dict[str, bytes] = {}
    base = repo.resolve()
    for entry in projection["source_bindings"]:
        path = (base / entry["path"]).resolve()
        if not path.is_relative_to(base):
            raise ValueError("source outside repository")
        raw = path.read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if blob != entry["git_blob"]:
            raise ValueError(f"source changed; re-audit required: {entry['path']}")
        data[entry["path"]] = raw
    import io
    text = data["docs/claim_ledger.csv"].decode("utf-8")
    reader = csv.reader(io.StringIO(text), strict=True)
    header = next(reader)
    if len(header) != len(set(header)):
        raise ValueError("duplicate ledger header")
    rows: dict[str, dict[str, str]] = {}
    for line, values in enumerate(reader, 2):
        if len(values) != len(header):
            raise ValueError(f"ledger row {line} width mismatch; do not shift evidence fields")
        row = dict(zip(header, values))
        ident = row["claim_id"]
        if not ident or ident in rows:
            raise ValueError("missing/duplicate canonical claim ID")
        rows[ident] = row
    cfg = parse_json(data["configs/channel_polarity_v2.json"].decode("utf-8"))
    source = projection["nodes"][0].copy()
    if not str(cfg.get("status", "")).startswith("RETRACTED_"):
        raise ValueError("source retraction changed; fresh scope review required")
    source["state"] = "RETRACTED"
    nodes = [source]
    for ident in ["CL-954-001", "CL-1318-002", "CL-1320-002"]:
        row = rows[ident]
        if row["source_config"] != "configs/channel_polarity_v2.json":
            raise ValueError(f"{ident}: dependency changed; review graph")
        nodes.append({"id": ident, "revision": projection["source_bindings"][1]["git_blob"],
                      "state": row["status"],
                      "requires": [{"id": source["id"], "revision": source["revision"]}]})
    result_path = projection["source_bindings"][2]["path"]
    result = parse_json(data[result_path].decode("utf-8"))
    nominal = [s for s in result["summaries"]
               if s["energy_target"] == "E_vis" and s["is_negative_control"] is False]
    if len(nominal) != 1:
        raise ValueError("expected exactly one nominal E_vis summary")
    row = rows["CL-029"]
    item = {"claim_id": "CL-029", "ledger_n_events": int(row["n_events"]),
            "artifact_n_heldout": nominal[0]["n_heldout"],
            "ledger_value": float(row["current_value"]),
            "artifact_value": nominal[0]["heldout_sigma68_fraction"]}
    return {**projection, "nodes": nodes, "quantitative_checks": [item],
            "scope": "PINNED_WHOLE_FILE_READ_SCOPED_CLAIM_COMPARISON"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projection", type=Path, default=HERE / "observed_projection.json")
    parser.add_argument("--repo", type=Path)
    args = parser.parse_args()
    try:
        payload = strict_json(args.projection)
        if args.repo:
            payload = repository_payload(args.repo, payload)
        report = audit(payload)
        print(json.dumps(report, indent=2, allow_nan=False))
        return 1 if report["findings"] or not report["graph"]["scope_clear"] else 0
    except (OSError, ValueError, KeyError, TypeError, RecursionError, csv.Error) as error:
        print(json.dumps({"status": "INPUT_OR_EXECUTION_FAILURE", "error": str(error),
                          "scientific_release": "NOT_AUTHORIZED"}, allow_nan=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
