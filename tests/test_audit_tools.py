#!/usr/bin/env python3
"""Tests for the CCB test-beam repository-wide audit harness (tools/audit)."""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# tools/audit is imported by bare module name (repo has no tools/__init__.py).
REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = REPO_ROOT / 'tools' / 'audit'
if str(AUDIT_DIR) not in sys.path:
    sys.path.insert(0, str(AUDIT_DIR))

import audit_repository  # noqa: E402
import validate_event_keys  # noqa: E402
import validate_pulse_schema  # noqa: E402
import audit_mc_weight_usage  # noqa: E402


# --------------------------------------------------------------------------- #
# validate_event_keys
# --------------------------------------------------------------------------- #
def test_event_keys_one_to_one_pass(tmp_path):
    left = pd.DataFrame({'run': [1, 1, 2], 'evt': [10, 11, 20], 'a': [0.1, 0.2, 0.3]})
    right = pd.DataFrame({'run': [1, 1, 2], 'evt': [10, 11, 20], 'b': [1, 2, 3]})
    # CSV (not parquet) so the test runs without a parquet engine in CI.
    lp, rp = tmp_path / 'left.csv', tmp_path / 'right.csv'
    left.to_csv(lp, index=False); right.to_csv(rp, index=False)
    res = validate_event_keys.validate(lp, rp, ['run', 'evt'])
    assert res['one_to_one'] is True
    assert res['joined_rows'] == 3

    out = tmp_path / 'keys.json'
    with pytest.raises(SystemExit) as exc:
        validate_event_keys.main([str(lp), str(rp), '--keys', 'run', 'evt', '--out', str(out)])
    assert exc.value.code == 0
    assert json.loads(out.read_text())['one_to_one'] is True


def test_event_keys_duplicate_fails(tmp_path):
    left = pd.DataFrame({'run': [1, 1, 2], 'evt': [10, 11, 20], 'a': [0.1, 0.2, 0.3]})
    # Inject a duplicate composite key on the right side -> not one_to_one.
    right = pd.DataFrame({'run': [1, 1, 1, 2], 'evt': [10, 10, 11, 20], 'b': [1, 9, 2, 3]})
    lp, rp = tmp_path / 'left.csv', tmp_path / 'right.csv'
    left.to_csv(lp, index=False); right.to_csv(rp, index=False)
    res = validate_event_keys.validate(lp, rp, ['run', 'evt'])
    assert res['one_to_one'] is False
    assert res['right_duplicate_rows'] == 2

    out = tmp_path / 'keys.json'
    with pytest.raises(SystemExit) as exc:
        validate_event_keys.main([str(lp), str(rp), '--out', str(out)])
    assert exc.value.code == 1


def test_event_keys_left_only_key_fails_key_set_equality(tmp_path):
    """Left-only key should fail with --require-key-set-equality."""
    left = pd.DataFrame({'run': [1, 1, 3], 'evt': [10, 11, 30], 'a': [0.1, 0.2, 0.3]})
    right = pd.DataFrame({'run': [1, 1], 'evt': [10, 11], 'b': [1, 2]})
    lp, rp = tmp_path / 'left.csv', tmp_path / 'right.csv'
    left.to_csv(lp, index=False); right.to_csv(rp, index=False)
    # Default mode (no key-set equality) passes because inner merge is one-to-one.
    res = validate_event_keys.validate(lp, rp, ['run', 'evt'])
    assert res['one_to_one'] is True
    assert res['key_set_analysis']['left_only_count'] == 1
    assert res['key_set_analysis']['shared_key_count'] == 2

    # Strict mode fails.
    res_strict = validate_event_keys.validate(
        lp, rp, ['run', 'evt'], require_key_set_equality=True)
    assert res_strict['one_to_one'] is False
    assert res_strict['key_set_analysis']['left_only_count'] == 1


def test_event_keys_right_only_key_fails_key_set_equality(tmp_path):
    """Right-only key should fail with --require-key-set-equality."""
    left = pd.DataFrame({'run': [1, 1], 'evt': [10, 11], 'a': [0.1, 0.2]})
    right = pd.DataFrame({'run': [1, 1, 2], 'evt': [10, 11, 20], 'b': [1, 2, 3]})
    lp, rp = tmp_path / 'left.csv', tmp_path / 'right.csv'
    left.to_csv(lp, index=False); right.to_csv(rp, index=False)
    res = validate_event_keys.validate(
        lp, rp, ['run', 'evt'], require_key_set_equality=True)
    assert res['one_to_one'] is False
    assert res['key_set_analysis']['right_only_count'] == 1


def test_event_keys_disjoint_sets_fail_key_set_equality(tmp_path):
    """Disjoint unique key sets should fail."""
    left = pd.DataFrame({'run': [1, 2], 'evt': [10, 20], 'a': [0.1, 0.2]})
    right = pd.DataFrame({'run': [3, 4], 'evt': [30, 40], 'b': [1, 2]})
    lp, rp = tmp_path / 'left.csv', tmp_path / 'right.csv'
    left.to_csv(lp, index=False); right.to_csv(rp, index=False)
    res = validate_event_keys.validate(
        lp, rp, ['run', 'evt'], require_key_set_equality=True)
    assert res['one_to_one'] is False
    assert res['key_set_analysis']['shared_key_count'] == 0
    assert res['key_set_analysis']['left_only_count'] == 2
    assert res['key_set_analysis']['right_only_count'] == 2


def test_event_keys_key_set_equality_sha256(tmp_path):
    """Key-set equality mode should record input hashes."""
    left = pd.DataFrame({'run': [1, 1], 'evt': [10, 11], 'a': [0.1, 0.2]})
    right = pd.DataFrame({'run': [1, 1], 'evt': [10, 11], 'b': [1, 2]})
    lp, rp = tmp_path / 'left.csv', tmp_path / 'right.csv'
    left.to_csv(lp, index=False); right.to_csv(rp, index=False)
    res = validate_event_keys.validate(
        lp, rp, ['run', 'evt'], require_key_set_equality=True)
    assert res['one_to_one'] is True
    assert len(res['left_sha256']) == 64
    assert len(res['right_sha256']) == 64
    assert res['left_sha256'] != res['right_sha256']


# --------------------------------------------------------------------------- #
# validate_pulse_schema
# --------------------------------------------------------------------------- #
def test_pulse_schema_missing_required(tmp_path):
    # Missing 'baseline_adc'.
    df = pd.DataFrame({'run': [1], 'evt': [10], 'stave': [0]})
    stats = validate_pulse_schema.validate(df, 'v1')
    codes = {f['code'] for f in stats['findings']}
    assert 'MISSING_REQUIRED_COLUMNS' in codes
    assert any(f['code'] == 'MISSING_REQUIRED_COLUMNS' and f['severity'] == 'P0' for f in stats['findings'])

    p = tmp_path / 't.csv'; df.to_csv(p, index=False)
    with pytest.raises(SystemExit) as exc:
        validate_pulse_schema.main([str(p), '--out', str(tmp_path / 'o.json'), '--schema-version', 'v1'])
    assert exc.value.code == 1


def test_pulse_schema_ambiguous_amplitude(tmp_path):
    df = pd.DataFrame({'run': [1], 'evt': [10], 'stave': [0],
                       'baseline_adc': [500.0], 'amplitude_adc': [1200.0]})
    stats = validate_pulse_schema.validate(df, 'v1')
    codes = {f['code'] for f in stats['findings']}
    assert 'AMBIGUOUS_AMPLITUDE_ADC' in codes
    assert 'MISSING_REQUIRED_COLUMNS' not in codes


def test_pulse_schema_clean_passes(tmp_path):
    df = pd.DataFrame({'run': [1, 1], 'evt': [10, 11], 'stave': [0, 0],
                       'baseline_adc': [500.0, 501.0], 'peak_height_adc': [1200.0, 1300.0]})
    stats = validate_pulse_schema.validate(df, 'v1')
    assert stats['findings'] == []

    p = tmp_path / 't.csv'; df.to_csv(p, index=False)
    with pytest.raises(SystemExit) as exc:
        validate_pulse_schema.main([str(p), '--out', str(tmp_path / 'o.json'), '--schema-version', 'v1'])
    assert exc.value.code == 0


# --------------------------------------------------------------------------- #
# audit_mc_weight_usage
# --------------------------------------------------------------------------- #
def _write_root(path, arrays):
    uproot = pytest.importorskip("uproot")  # skip cleanly if uproot absent (CI)
    with uproot.recreate(path) as f:
        f['hibeam'] = arrays


def test_mc_weight_missing_branch(tmp_path):
    p = tmp_path / 'no_weight.root'
    _write_root(p, {'PrimaryPDG': np.array([2112, 2112, -2112], dtype=np.int64),
                    'Sci_bar_LayerID1': np.array([1, 2, 1], dtype=np.int64)})
    res = audit_mc_weight_usage.audit(p, 'hibeam')
    assert res['status'] == 'P0_NO_WEIGHT_BRANCH'

    with pytest.raises(SystemExit) as exc:
        audit_mc_weight_usage.main([str(p), '--tree', 'hibeam', '--out', str(tmp_path / 'w.json')])
    assert exc.value.code == 1


def test_mc_weight_present_ok(tmp_path):
    p = tmp_path / 'weighted.root'
    w = np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float64)
    _write_root(p, {'PrimaryWeight': w, 'PrimaryPDG': np.array([2112, 2112, -2112, 2112], dtype=np.int64)})
    res = audit_mc_weight_usage.audit(p, 'hibeam')
    assert res['status'] == 'OK'
    assert res['branch'] == 'PrimaryWeight'
    assert res['n'] == 4
    # Equal weights -> ESS equals n exactly.
    assert res['ess'] == pytest.approx(4.0)
    assert res['ess_fraction'] == pytest.approx(1.0)

    out = tmp_path / 'w.json'
    with pytest.raises(SystemExit) as exc:
        audit_mc_weight_usage.main([str(p), '--out', str(out)])
    assert exc.value.code == 0
    assert json.loads(out.read_text())['status'] == 'OK'


# --------------------------------------------------------------------------- #
# audit_repository (static auditor)
# --------------------------------------------------------------------------- #
def test_audit_python_flags_core_patterns(tmp_path):
    src = (
        "import numpy as np\n"
        "import pandas as pd\n"
        "def go(a, b):\n"
        "    merged = a.merge(b, on='eventno', how='inner')\n"
        "    pick = np.random.choice(merged.index, size=3)\n"
        "    path = '/home/billy/ccb-data/run.root'\n"
        "    return merged, pick, path\n"
    )
    f = tmp_path / 'leaky.py'
    f.write_text(src)
    rows = []
    audit_repository.audit_python(f, rows)
    codes = {r['code'] for r in rows}
    assert 'EVENTNO_ONLY_JOIN' in codes
    assert 'UNSEEDED_RANDOMNESS' in codes
    assert 'ABSOLUTE_PATH' in codes
    # EVENTNO_ONLY_JOIN is publication-blocking.
    assert any(r['code'] == 'EVENTNO_ONLY_JOIN' and r['severity'] == 'P0' for r in rows)


def test_audit_collect_and_exclude(tmp_path):
    (tmp_path / 'good').mkdir()
    (tmp_path / 'good' / 'clean.py').write_text(
        "import numpy as np\n"
        "rng = np.random.default_rng(0)\n"
        "x = rng.integers(0, 5, size=3)\n"
    )
    vendored = tmp_path / 'node_modules'
    vendored.mkdir()
    (vendored / 'bad.py').write_text("m = a.merge(b, on='eventno')\n")
    rows, inventory = audit_repository.collect(tmp_path, ['node_modules'])
    paths = {r['path'] for r in rows}
    # The vendored/excluded file must not appear in findings.
    assert not any('node_modules' in p for p in paths)
    assert all('node_modules' not in inv['path'] for inv in inventory)
