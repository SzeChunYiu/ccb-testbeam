"""Software contract tests and bounded exhaustive finite-population verification."""
from __future__ import annotations

import copy
import itertools
import math
import unittest

import numpy as np
from scipy.stats import binomtest

import trigger_joint_reference as ref
import legacy_threshold_excerpt as threshold
import legacy_migration_excerpt as migration


def rows(mask, run="fixture"):
    return [{"run_id": run, "event_id": i, "passed": bool(x)} for i, x in enumerate(mask)]


def surface_rows():
    return [{"threshold_mev": t, "coinc_ns": w, "n_total": 10,
             "n_pass": n, "population_id": "fixture"}
            for t, w, n in [(1, 5, 2), (1, 15, 8), (2, 5, 1), (2, 15, 6)]]


def surface(data):
    return ref.scan_surface(data, thresholds=[1, 2], windows=[5, 15], population_id="fixture")


class JointTests(unittest.TestCase):
    def test_disjoint_selections_not_laundered(self):
        r = ref.joint_counts(rows([1, 1, 0, 0]), rows([0, 0, 1, 1]), population_id="fixture")
        self.assertEqual(r["counts"], {"both": 0, "neither": 0, "proxy_only": 2, "hardware_only": 2})
        self.assertEqual(r["rates"]["proxy_loss"]["estimate"], 1.0)
        old = migration.compute_migration_quadrant({"n_enter": 4, "n_pass": 2}, {"n_enter": 4, "n_pass": 2})
        self.assertEqual(old.both, 2)  # retained historical failing witness

    def test_alignment_is_by_composite_identity(self):
        p, h = rows([1, 1, 0]), rows([0, 1, 1])
        self.assertEqual(ref.joint_counts(p, h, population_id="f"), ref.joint_counts(p[::-1], h[1:]+h[:1], population_id="f"))

    def test_same_event_number_different_runs_remains_distinct(self):
        p = rows([1], "a") + rows([0], "b")
        h = rows([0], "a") + rows([1], "b")
        self.assertEqual(ref.joint_counts(p, h, population_id="f")["counts"]["both"], 0)

    def test_duplicate_identity_rejected(self):
        with self.assertRaises(ValueError): ref.joint_counts(rows([1])+rows([1]), rows([1]), population_id="f")

    def test_missing_event_rejected(self):
        with self.assertRaises(ValueError): ref.joint_counts(rows([1, 0]), rows([1]), population_id="f")

    def test_equal_cardinality_different_keys_rejected(self):
        with self.assertRaises(ValueError): ref.joint_counts(rows([1], "a"), rows([1], "b"), population_id="f")

    def test_unknown_or_coerced_flags_rejected(self):
        for x in [0, 1, None, "true", float("nan"), np.bool_(True)]:
            p = rows([1]); p[0]["passed"] = x
            with self.subTest(x=str(x)), self.assertRaises(ValueError): ref.joint_counts(p, rows([1]), population_id="f")

    def test_weights_not_silently_ignored(self):
        p = rows([1]); p[0]["weight"] = 0.25
        with self.assertRaises(ValueError): ref.joint_counts(p, rows([1]), population_id="f")

    def test_noninteger_event_identity_rejected(self):
        for x in [True, 0.1, "1", -1]:
            p = rows([1]); p[0]["event_id"] = x
            with self.subTest(x=x), self.assertRaises(ValueError): ref.joint_counts(p, rows([1]), population_id="f")

    def test_empty_sample_not_zero_efficiency(self):
        r = ref.joint_counts([], [], population_id="f")
        self.assertIsNone(r["rates"]["hardware_acceptance"]["estimate"])
        self.assertEqual(r["rates"]["proxy_loss"]["status"], "NOT_ESTIMABLE")

    def test_conditional_denominators_distinct(self):
        r = ref.joint_counts(rows([1, 1, 1, 0]), rows([1, 0, 0, 1]), population_id="f")["rates"]
        self.assertEqual(r["hardware_given_proxy"]["estimate"], 1/3)
        self.assertEqual(r["proxy_given_hardware"]["estimate"], 1/2)

    def test_no_scientific_release(self):
        self.assertEqual(ref.joint_counts(rows([1]), rows([1]), population_id="f")["scientific_release"], "NOT_AUTHORIZED")

    def test_missing_population_identity_rejected(self):
        with self.assertRaises(ValueError): ref.joint_counts([], [], population_id="")

    def test_inputs_not_modified(self):
        p, h = rows([1, 0]), rows([0, 1]); before = copy.deepcopy((p, h))
        ref.joint_counts(p, h, population_id="f")
        self.assertEqual((p, h), before)


class BoundsTests(unittest.TestCase):
    def test_marginals_return_set_not_invented_overlap(self):
        r = ref.marginal_bounds(4, 2, 2, population_id="f")
        self.assertEqual(r["both_bounds"], [0, 2])
        self.assertEqual(r["proxy_loss_bounds"], [0, 1])
        self.assertFalse(r["joint_counts_identified"])

    def test_zero_hardware_special_case_is_identified(self):
        r = ref.marginal_bounds(4, 2, 0, population_id="f")
        self.assertEqual(r["both_bounds"], [0, 0]); self.assertTrue(r["joint_counts_identified"])
        self.assertEqual(r["proxy_loss_bounds"], [1, 1])

    def test_no_proxy_is_not_zero_loss(self):
        self.assertIsNone(ref.marginal_bounds(4, 0, 2, population_id="f")["proxy_loss_bounds"])

    def test_impossible_or_invalid_counts_rejected(self):
        for args in [(4, 5, 2), (4, 2, 5), (True, 0, 0), (4, 0.0, 1), (-1, 0, 0), (2**53+1, 0, 0)]:
            with self.subTest(args=args), self.assertRaises(ValueError): ref.marginal_bounds(*args, population_id="f")

    def test_empty_counts_mathematically_identified_but_no_loss(self):
        r = ref.marginal_bounds(0, 0, 0, population_id="f")
        self.assertEqual(r["both_bounds"], [0, 0]); self.assertIsNone(r["proxy_loss_bounds"])


class ScanTests(unittest.TestCase):
    def test_preserves_two_coordinates(self):
        r = surface(surface_rows())
        self.assertEqual(len(r["rows"]), 4)
        self.assertEqual([x["estimate"] for x in r["rows"]], [0.2, 0.8, 0.1, 0.6])

    def test_all_24_row_orders_equal(self):
        expected = surface(surface_rows())
        for perm in itertools.permutations(surface_rows()): self.assertEqual(surface(list(perm)), expected)

    def test_missing_cell_rejected(self):
        with self.assertRaises(ValueError): surface(surface_rows()[:-1])

    def test_duplicate_cell_rejected_even_if_identical(self):
        with self.assertRaises(ValueError): surface(surface_rows()+[surface_rows()[0]])

    def test_unexpected_cell_rejected(self):
        r = surface_rows(); r[0]["threshold_mev"] = 3
        with self.assertRaises(ValueError): surface(r)

    def test_population_identity_mismatch_rejected(self):
        r = surface_rows(); r[0]["population_id"] = "other"
        with self.assertRaises(ValueError): surface(r)

    def test_population_size_mismatch_rejected(self):
        r = surface_rows(); r[0]["n_total"] = 11
        with self.assertRaises(ValueError): surface(r)

    def test_nonfinite_axes_rejected(self):
        for x in [float("nan"), float("inf"), 0, -1, True, "1"]:
            r = surface_rows(); r[0]["coinc_ns"] = x
            with self.subTest(x=str(x)), self.assertRaises(ValueError): surface(r)

    def test_duplicate_or_empty_axis_rejected(self):
        for ts in [[], [1, 1], [1, 1.0]]:
            with self.subTest(ts=ts), self.assertRaises(ValueError): ref.scan_surface(surface_rows(), thresholds=ts, windows=[5, 15], population_id="fixture")

    def test_zero_population_is_explicit_null(self):
        r = surface_rows()
        for row in r: row["n_total"] = row["n_pass"] = 0
        self.assertTrue(all(row["estimate"] is None for row in surface(r)["rows"]))

    def test_threshold_monotonicity_is_not_universally_assumed(self):
        # Earliest-above-threshold times can move after a threshold change.
        es, ts = np.array([1.5, 3.0]), np.array([0.0, 20.0])
        h = lambda cut: bool(threshold.classify_event_hardware_response(es, ts, np.array([3.0]), np.array([20.0]), cut, 5)["coincidence"])
        self.assertFalse(h(1)); self.assertTrue(h(2))
        r = [{"threshold_mev": cut, "coinc_ns": 5, "n_total": 1, "n_pass": int(h(cut)), "population_id": "f"} for cut in [1, 2]]
        self.assertEqual(len(ref.scan_surface(r, thresholds=[1, 2], windows=[5], population_id="f")["rows"]), 2)


class IntervalTests(unittest.TestCase):
    def test_zero_success_matches_scipy_independently(self):
        for n in [1, 4, 40, 554, 1000000]:
            for level in [0.68, 0.95, 0.99]:
                for sided, alt in [("one-sided", "less"), ("two-sided-equal-tail", "two-sided")]:
                    actual = ref.zero_success_upper(n, confidence=level, sided=sided, sampling_model="independent_identical_bernoulli")
                    expected = binomtest(0, n, alternative=alt).proportion_ci(level, method="exact").high
                    self.assertAlmostEqual(actual, expected, delta=2e-12)

    def test_zero_trials_rejected(self):
        with self.assertRaises(ValueError): ref.zero_success_upper(0, confidence=.95, sided="one-sided", sampling_model="independent_identical_bernoulli")

    def test_sampling_model_must_be_explicit(self):
        for model in ["weighted", "correlated", "", None]:
            with self.subTest(model=model), self.assertRaises(ValueError): ref.zero_success_upper(4, confidence=.95, sided="one-sided", sampling_model=model)

    def test_confidence_and_sidedness_validated(self):
        for lev, sid in [(0, "one-sided"), (1, "one-sided"), (.95, "unspecified"), (float("nan"), "one-sided")]:
            with self.subTest(lev=lev, sid=sid), self.assertRaises(ValueError): ref.zero_success_upper(4, confidence=lev, sided=sid, sampling_model="independent_identical_bernoulli")

    def test_two_sided_upper_is_larger(self):
        f = lambda s: ref.zero_success_upper(554, confidence=.95, sided=s, sampling_model="independent_identical_bernoulli")
        self.assertGreater(f("two-sided-equal-tail"), f("one-sided"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
