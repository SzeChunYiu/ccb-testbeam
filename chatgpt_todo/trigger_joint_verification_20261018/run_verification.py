"""Bounded trigger-accounting proof checks and source-component counterexamples.

Exit 1 intentionally retains unresolved historical defects; not global clearance.
"""
from __future__ import annotations

from dataclasses import asdict
from itertools import permutations
import json
import sys

import numpy as np
import trigger_joint_reference as ref
import legacy_migration_excerpt as legacy
import legacy_threshold_excerpt as threshold
from test_trigger_joint_reference import rows, surface, surface_rows


def exhaustive(max_n=8):
    cases = 0
    legacy_wrong = 0
    support = {}
    for n in range(max_n+1):
        masks = [rows([(m >> k) & 1 for k in range(n)]) for m in range(1 << n)]
        for p in range(1 << n):
            for h in range(1 << n):
                actual = ref.joint_counts(masks[p], masks[h], population_id="synthetic-finite-universe")
                # Independent integer bitset oracle, not key-join implementation.
                both = (p & h).bit_count()
                pc, hc = p.bit_count(), h.bit_count()
                oracle = {"both": both, "neither": n-(p | h).bit_count(),
                          "proxy_only": (p & ~h).bit_count(), "hardware_only": (h & ~p).bit_count()}
                if actual["counts"] != oracle:
                    raise RuntimeError(f"joint mismatch n={n},p={p},h={h}")
                bounds = ref.marginal_bounds(n, pc, hc, population_id="synthetic-finite-universe")
                if not bounds["both_bounds"][0] <= both <= bounds["both_bounds"][1]:
                    raise RuntimeError("marginal bounds exclude a realizable joint table")
                support.setdefault((n, pc, hc), set()).add(both)
                if min(pc, hc) != both:
                    legacy_wrong += 1
                cases += 1
    for (n, p, h), attained in support.items():
        b = ref.marginal_bounds(n, p, h, population_id="synthetic-finite-universe")["both_bounds"]
        if attained != set(range(b[0], b[1]+1)):
            raise RuntimeError("bounds not sharp over enumerated finite universe")
    return {"max_n": max_n, "all_mask_pairs": cases,
            "joint_bitset_oracle_mismatches": 0,
            "marginal_population_triples": len(support),
            "bounds_attainability_mismatches": 0,
            "old_min_marginals_wrong_pairs": legacy_wrong,
            "meaning": "finite software/accounting conformance; not independent detector observations"}


def hardware(e1, t1, e2, t2, cut=1.0, window=5.0):
    r = threshold.classify_event_hardware_response(
        np.array(e1, float), np.array(t1, float),
        np.array(e2, float), np.array(t2, float), cut, window)
    return {key: bool(value) for key, value in r.items()}


def main():
    disjoint = ref.joint_counts(rows([1, 1, 0, 0]), rows([0, 0, 1, 1]), population_id="disjoint-four")
    old = legacy.compute_migration_quadrant({"n_enter": 4, "n_pass": 2}, {"n_enter": 4, "n_pass": 2})
    # The same physical hit rows are permuted as records, not particle identities changed.
    original_hits = [(2212, 1, 0, 20.0), (1000010020, 2, 0, 20.0), (11, 1, 1, 20.0)]
    labels = []
    for perm in permutations(original_hits):
        labels.append({"hit_order_pdg": [row[0] for row in perm],
                       "legacy_primary_species_pdg": threshold.get_primary_species(np.array([row[0] for row in perm]))})
    unique = sorted(set(row["legacy_primary_species_pdg"] for row in labels))
    if unique != [11, 2212, 1000010020]:
        raise RuntimeError("source species witness changed")
    low = hardware([1.5, 3], [0, 20], [3], [20], 1)
    high = hardware([1.5, 3], [0, 20], [3], [20], 2)
    merged = hardware([1.2], [20], [1.2], [20])
    split = hardware([.6, .6], [20, 20], [.6, .6], [20, 20])
    early = hardware([3, 3], [0, 20], [3], [20])
    bad = hardware([float("nan")], [20], [3], [20])
    scan = [{"threshold_mev": 1, "coinc_ns": w,
             "species_breakdown": {"proton": {"n_enter": 10, "n_pass": n}}}
            for w, n in [(5, 2), (15, 8)]]
    result = {
        "status": "REFERENCE_CONFORMANCE_PASS_LEGACY_DEFECTS_REMAIN",
        "scientific_release": "NOT_AUTHORIZED",
        "full_repository_verified": False,
        "exhaustive": exhaustive(),
        "disjoint_fixture": {"legacy": asdict(old), "correct_reference": disjoint,
                             "marginals_only": ref.marginal_bounds(4, 2, 2, population_id="disjoint-four")},
        "source_species_counterexample": {"permutations": labels,
            "distinct_labels_same_hits": len(unique),
            "classification": "CONFIRMED_ORDER_DEPENDENT_FIRST_HIT_LABEL_NOT_PRIMARY_TRUTH",
            "boundary": "No production species fractions recomputed; real writer ordering and track ancestry unverified."},
        "energy_partition_counterexample": {"merged_deposit_MeV_each_counter": 1.2,
            "split_deposits_MeV_each_counter": [.6, .6], "threshold_MeV": 1,
            "all_times_ns": 20, "merged": merged, "split": split,
            "classification": "CONDITIONAL_RESPONSE_MODEL_GAP",
            "boundary": "Invariance required only if entries partition one unresolved counter signal. Actual T1/T2 writer/response semantics unbound. Not a measured efficiency bias."},
        "coincidence_policy_counterexample": {"earliest_only_result": early,
            "any_pair_within_window_exists": True,
            "boundary": "Earliest-only and any-pair policies differ. Neither is asserted to be real electronics without discriminator/deadtime evidence."},
        "threshold_monotonicity_counterexample": {"cut_1_MeV": low, "cut_2_MeV": high,
            "boundary": "An unconditional nonincreasing coincidence-vs-threshold test would be invalid; selected timestamps can change."},
        "nan_energy_counterexample": {"result": bad, "exception_raised": False,
            "classification": "INVALID_HIT_DATA_SILENTLY_COUNTS_AS_TRIGGER_FAILURE"},
        "scan_order_control": {"legacy_forward": legacy.extract_curve_data(scan, "threshold_mev"),
            "legacy_reverse": legacy.extract_curve_data(scan[::-1], "threshold_mev"),
            "reference_surface": surface(surface_rows())},
        "zero_success_control": {str(n): {s: ref.zero_success_upper(n, confidence=.95, sided=s,
            sampling_model="independent_identical_bernoulli") for s in ["one-sided", "two-sided-equal-tail"]}
            for n in [554, 1000000]},
        "code_scope": "reference code plus named Python function bodies; no full ROOT CLI, native hit writer or Geant4 transport",
        "four_review_roles": "single-assistant perspectives, not independent human sign-off"
    }
    print(json.dumps(result, indent=2, allow_nan=False))
    return 1


if __name__ == "__main__":
    sys.exit(main())
