"""Tests the scoped auditor, not experimental physics. Run with unittest."""
from __future__ import annotations
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import audit_claim_dependencies as mod

HERE = Path(__file__).resolve().parent


def node(ident, state="SUPPORTED", parents=(), revision="revision-1"):
    return {"id": ident, "state": state, "revision": revision,
            "requires": [{"id": p, "revision": "revision-1"} for p in parents]}


class GraphTests(unittest.TestCase):
    def test_scoped_valid_is_not_global_certificate(self):
        r = mod.graph_check([node("source"), node("claim", parents=("source",))])
        self.assertTrue(r["scope_clear"])
        self.assertFalse(r["global_release_authorized"])

    def test_retraction_reaches_grandchild(self):
        r = mod.graph_check([node("a", "RETRACTED"), node("b", parents=("a",)), node("c", parents=("b",))])
        self.assertEqual(r["root_causes"]["c"]["invalid"], ["a"])
        self.assertEqual(r["effective_states"]["c"], "INVALIDATED")

    def test_diamond_deduplicates_root_cause(self):
        r = mod.graph_check([node("a", "FLAWED"), node("b", parents=("a",)), node("c", parents=("a",)), node("d", parents=("b", "c"))])
        self.assertEqual(r["root_causes"]["d"]["invalid"], ["a"])

    def test_multiple_roots_not_lost(self):
        r = mod.graph_check([node("a", "RETRACTED"), node("b", "FLAWED"), node("c", parents=("a", "b"))])
        self.assertEqual(r["root_causes"]["c"]["invalid"], ["a", "b"])

    def test_blocked_is_not_claimed_flawed(self):
        r = mod.graph_check([node("a", "BLOCKED"), node("b", parents=("a",))])
        self.assertEqual(r["effective_states"]["b"], "BLOCKED_PENDING_EVIDENCE")
        self.assertEqual(r["root_causes"]["b"]["invalid"], [])

    def test_changed_revision_propagates(self):
        r = mod.graph_check([node("a", revision="revision-2"), node("b", parents=("a",)), node("c", parents=("b",))])
        self.assertEqual(r["effective_states"]["c"], "STALE_RECOMPUTE_REQUIRED")
        self.assertEqual(r["root_causes"]["c"]["stale"], ["b->a"])

    def test_order_invariance(self):
        nodes = [node("a", "RETRACTED"), node("b", parents=("a",)), node("c", parents=("b",))]
        self.assertEqual(mod.graph_check(nodes), mod.graph_check(nodes[::-1]))

    def test_empty_graph_rejected(self):
        with self.assertRaises(ValueError): mod.graph_check([])

    def test_duplicate_node_rejected(self):
        with self.assertRaises(ValueError): mod.graph_check([node("a"), node("a")])

    def test_unknown_status_rejected(self):
        with self.assertRaises(ValueError): mod.graph_check([node("a", "SUPORTED")])

    def test_unresolved_dependency_rejected(self):
        with self.assertRaises(ValueError): mod.graph_check([node("a", parents=("missing",))])

    def test_duplicate_edge_rejected(self):
        with self.assertRaises(ValueError): mod.graph_check([node("a"), node("b", parents=("a", "a"))])

    def test_cycle_rejected(self):
        with self.assertRaises(ValueError): mod.graph_check([node("a", parents=("b",)), node("b", parents=("a",))])

    def test_self_loop_rejected(self):
        with self.assertRaises(ValueError): mod.graph_check([node("a", parents=("a",))])

    def test_missing_node_revision_rejected(self):
        n = node("a"); n.pop("revision")
        with self.assertRaises(ValueError): mod.graph_check([n])

    def test_missing_edge_revision_rejected(self):
        n = node("b", parents=("a",)); n["requires"][0].pop("revision")
        with self.assertRaises(ValueError): mod.graph_check([node("a"), n])

    def test_missing_requires_is_not_assumed_empty(self):
        n = node("a"); n.pop("requires")
        with self.assertRaises(ValueError): mod.graph_check([n])

    def test_atomic_order_is_upstream_first(self):
        r = mod.graph_check([node("c", parents=("b",)), node("a"), node("b", parents=("a",))])
        self.assertEqual(r["topological_order"], ["a", "b", "c"])


class InputTests(unittest.TestCase):
    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(ValueError): mod.parse_json('{"id":1,"id":2}')

    def test_nonfinite_json_rejected(self):
        for val in ["NaN", "Infinity", "-Infinity"]:
            with self.subTest(val=val), self.assertRaises(ValueError): mod.parse_json('{"x":'+val+'}')

    def test_array_document_rejected(self):
        with self.assertRaises(ValueError): mod.parse_json('[]')

    def test_bad_counts_rejected(self):
        for val in [True, -1, 1.5, "400", float("nan")]:
            with self.subTest(val=val), self.assertRaises(ValueError): mod.count(val)

    def test_exact_zero_count_allowed(self):
        self.assertEqual(mod.count(0), 0)

    def test_nonfinite_metrics_rejected(self):
        for val in [True, "1", float("nan"), float("inf")]:
            with self.subTest(val=val), self.assertRaises(ValueError): mod.finite_number(val)

    def test_observed_projection_finds_three_descendants_and_count(self):
        p = mod.strict_json(HERE / "observed_projection.json")
        r = mod.audit(p)
        invalid = {x["claim_id"] for x in r["findings"] if x["code"] == "RETRACTED_OR_FLAWED_ANCESTOR"}
        self.assertEqual(invalid, {"CL-954-001", "CL-1318-002", "CL-1320-002"})
        self.assertEqual(r["finding_count"], 4)
        self.assertFalse(any(x["code"] == "NUMERICAL_VALUE_MISMATCH" for x in r["findings"]))

    def test_count_correction_does_not_clear_retracted_inputs(self):
        p = mod.strict_json(HERE / "observed_projection.json")
        p["quantitative_checks"][0]["ledger_n_events"] = 4000
        r = mod.audit(p)
        self.assertEqual(r["finding_count"], 3)
        self.assertEqual(r["scientific_release"], "NOT_AUTHORIZED")

    def test_numerical_mismatch_detected(self):
        p = mod.strict_json(HERE / "observed_projection.json")
        p["quantitative_checks"][0]["ledger_value"] = 0.1
        self.assertTrue(any(x["code"] == "NUMERICAL_VALUE_MISMATCH" for x in mod.audit(p)["findings"]))

    def test_historical_node_not_promoted(self):
        p = mod.strict_json(HERE / "observed_projection.json")
        for n in p["nodes"][1:]: n["state"] = "SUPERSEDED"
        r = mod.audit(p)
        self.assertFalse(any(x["code"] == "RETRACTED_OR_FLAWED_ANCESTOR" for x in r["findings"]))
        self.assertFalse(r["graph"]["scope_clear"])

    def test_cli_returns_one_for_current_inconsistencies(self):
        r = subprocess.run([sys.executable, str(HERE / "audit_claim_dependencies.py")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(json.loads(r.stdout)["finding_count"], 4)

    def test_cli_returns_two_for_missing_source(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, str(HERE / "audit_claim_dependencies.py"), "--repo", d], capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertEqual(json.loads(r.stdout)["scientific_release"], "NOT_AUTHORIZED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
