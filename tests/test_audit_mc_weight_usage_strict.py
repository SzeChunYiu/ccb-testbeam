from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = REPO_ROOT / "tools" / "audit"
if str(AUDIT_DIR) not in sys.path:
    sys.path.insert(0, str(AUDIT_DIR))

import audit_mc_weight_usage  # noqa: E402


class FakeBranch:
    def __init__(self, values):
        self.values = values

    def array(self, library):
        assert library == "np"
        return self.values


class FakeTree:
    def __init__(self, branches, n_entries=None):
        self.branches = branches
        first = next(iter(branches.values()), np.array([], dtype=float))
        self.num_entries = len(first) if n_entries is None else n_entries

    def keys(self):
        return list(self.branches)

    def __getitem__(self, name):
        return FakeBranch(self.branches[name])


class FakeRootFile:
    def __init__(self, tree):
        self.tree = tree

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def __getitem__(self, name):
        assert name == "hibeam"
        return self.tree


def install_fake_uproot(monkeypatch, tree):
    monkeypatch.setitem(
        sys.modules,
        "uproot",
        SimpleNamespace(open=lambda path: FakeRootFile(tree)),
    )


def write_root_bytes(tmp_path):
    root = tmp_path / "sample.root"
    root.write_bytes(b"synthetic-root-bytes\x00\x01")
    return root


def test_valid_weights_record_exact_provenance_and_stable_ess(tmp_path, monkeypatch):
    root = write_root_bytes(tmp_path)
    weights = np.array([0.5, 1.5, 2.0], dtype=np.float64)
    install_fake_uproot(monkeypatch, FakeTree({"PrimaryWeight": weights}))

    result = audit_mc_weight_usage.audit(root, "hibeam")

    assert result["status"] == "OK"
    assert result["validator_version"] == "3.0.0"
    assert result["population_policy_id"] == "nonnegative_event_measure_v2"
    assert result["n_entries"] == result["n_weights"] == result["n"] == 3
    assert result["sum_w"] == pytest.approx(4.0)
    assert result["sum_w2"] == pytest.approx(6.5)
    assert result["ess"] == pytest.approx(16.0 / 6.5)
    assert result["max_weight_fraction"] == pytest.approx(0.5)
    assert result["input_size_bytes"] == len(root.read_bytes())
    assert result["input_sha256"] == hashlib.sha256(root.read_bytes()).hexdigest()
    assert result["summation_method"] == "python_math_fsum_max_scaled_binary64_v2"


@pytest.mark.parametrize("scale", [1.0, 1e300, 1e-300])
def test_audit_diagnostics_are_invariant_to_positive_common_scale(
    tmp_path,
    monkeypatch,
    scale,
):
    root = write_root_bytes(tmp_path)
    weights = scale * np.array([1.0, 2.0, 7.0], dtype=np.float64)
    install_fake_uproot(monkeypatch, FakeTree({"PrimaryWeight": weights}))

    result = audit_mc_weight_usage.audit(root, "hibeam")

    assert result["status"] == "OK"
    assert result["ess"] == pytest.approx(100.0 / 54.0)
    assert result["ess_fraction"] == pytest.approx((100.0 / 54.0) / 3.0)
    assert result["max_weight_fraction"] == pytest.approx(0.7)
    assert result["max_over_mean"] == pytest.approx(2.1)
    assert result["sum_w_over_scale"] == pytest.approx(10.0 / 7.0)
    assert result["sum_w2_over_scale2"] == pytest.approx(54.0 / 49.0)


def test_audit_accepts_valid_measure_when_raw_moments_are_unrepresentable(
    tmp_path,
    monkeypatch,
):
    root = write_root_bytes(tmp_path)
    cases = (
        np.array([1e154, 1e154]),
        np.array([1e308, 1e308]),
        np.array([np.nextafter(0.0, 1.0), np.nextafter(0.0, 1.0)]),
    )
    for weights in cases:
        install_fake_uproot(monkeypatch, FakeTree({"PrimaryWeight": weights}))
        result = audit_mc_weight_usage.audit(root, "hibeam")
        assert result["status"] == "OK"
        assert result["ess"] == pytest.approx(2.0)
        assert result["max_weight_fraction"] == pytest.approx(0.5)
        assert result["sum_w_over_scale"] == pytest.approx(2.0)
        assert result["sum_w2_over_scale2"] == pytest.approx(2.0)
        assert result["sum_w2"] is None

    install_fake_uproot(
        monkeypatch,
        FakeTree({"PrimaryWeight": np.array([1e308, 1e308])}),
    )
    overflow = audit_mc_weight_usage.audit(root, "hibeam")
    assert overflow["sum_w"] is None
    assert overflow["mean"] is None
    json.dumps(overflow, allow_nan=False)


@pytest.mark.parametrize(
    ("weights", "status", "detail"),
    [
        (np.array([1.0, np.nan, 2.0]), "P0_NONFINITE_WEIGHT", "n_nonfinite"),
        (np.array([1.0, -0.1, 2.0]), "P0_NEGATIVE_WEIGHT", "n_negative"),
        (np.array([0.0, 0.0, 0.0]), "P0_ZERO_TOTAL_WEIGHT", "sum_w"),
    ],
)
def test_invalid_values_fail_without_silent_filtering(
    tmp_path,
    monkeypatch,
    weights,
    status,
    detail,
):
    root = write_root_bytes(tmp_path)
    install_fake_uproot(monkeypatch, FakeTree({"PrimaryWeight": weights}))

    result = audit_mc_weight_usage.audit(root, "hibeam")

    assert result["status"] == status
    assert detail in result
    assert "ess" not in result


def test_ambiguous_weight_branches_fail_closed(tmp_path, monkeypatch):
    root = write_root_bytes(tmp_path)
    values = np.ones(3)
    install_fake_uproot(
        monkeypatch,
        FakeTree({"PrimaryWeight": values, "EventWeight": values.copy()}),
    )

    result = audit_mc_weight_usage.audit(root, "hibeam")

    assert result["status"] == "P0_AMBIGUOUS_WEIGHT_BRANCHES"
    assert result["weight_branch_candidates"] == ["PrimaryWeight", "EventWeight"]


def test_shape_and_entry_alignment_fail_closed(tmp_path, monkeypatch):
    root = write_root_bytes(tmp_path)
    install_fake_uproot(
        monkeypatch,
        FakeTree({"PrimaryWeight": np.ones((2, 2))}, n_entries=2),
    )
    shape_result = audit_mc_weight_usage.audit(root, "hibeam")
    assert shape_result["status"] == "P0_WEIGHT_SHAPE_INVALID"

    install_fake_uproot(
        monkeypatch,
        FakeTree({"PrimaryWeight": np.ones(2)}, n_entries=3),
    )
    length_result = audit_mc_weight_usage.audit(root, "hibeam")
    assert length_result["status"] == "P0_WEIGHT_LENGTH_MISMATCH"
    assert length_result["n_entries"] == 3
    assert length_result["n_weights"] == 2


def test_main_publishes_json_atomically_and_preserves_compatibility(
    tmp_path,
    monkeypatch,
):
    root = write_root_bytes(tmp_path)
    install_fake_uproot(
        monkeypatch,
        FakeTree({"PrimaryWeight": np.ones(4, dtype=np.float64)}),
    )
    out = tmp_path / "reports" / "weights.json"

    with pytest.raises(SystemExit) as exc:
        audit_mc_weight_usage.main([str(root), "--out", str(out)])

    assert exc.value.code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "OK"
    assert payload["branch"] == "PrimaryWeight"
    assert payload["n"] == 4
    assert payload["ess"] == pytest.approx(4.0)
    assert payload["population_policy_id"] == "nonnegative_event_measure_v2"
    assert list(out.parent.glob(f".{out.name}.*.tmp")) == []


def test_main_rejects_input_output_alias_without_destroying_root(tmp_path):
    root = write_root_bytes(tmp_path)
    before = root.read_bytes()

    with pytest.raises(SystemExit) as exc:
        audit_mc_weight_usage.main([str(root), "--out", str(root)])

    assert exc.value.code == 2
    assert root.read_bytes() == before
