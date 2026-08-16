"""Regression tests for AUD-001 (inventory gate) and AUD-002 (coverage).

Run from the repo root::

    python -m pytest tests/test_audit_gate_and_coverage.py -q
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = REPO_ROOT / 'tools' / 'audit'
if str(AUDIT_DIR) not in sys.path:
    sys.path.insert(0, str(AUDIT_DIR))

import audit_repository  # noqa: E402
import run_repo_audit  # noqa: E402


# --------------------------------------------------------------------------- #
# AUD-002: explicit language coverage
# --------------------------------------------------------------------------- #
def test_unaudited_languages_are_recorded_not_silent(tmp_path):
    """C++/CMake/YAML/notebook/shell files must be inventoried + flagged unaudited."""
    (tmp_path / 'src.cc').write_text("int main(){ return 0; }\n")
    (tmp_path / 'CMakeLists.txt').write_text("cmake_minimum_required(VERSION 3.16)\n")
    (tmp_path / 'cfg.yaml').write_text("seed: 1\n")
    (tmp_path / 'nb.ipynb').write_text("{}\n")
    (tmp_path / 'run.sh').write_text("echo hi\n")
    (tmp_path / 'clean.py').write_text("x = 1\n")
    rows, inventory = audit_repository.collect(tmp_path, [])
    inv_by_path = {r['path']: r for r in inventory}
    # audited flags
    assert inv_by_path['src.cc']['audited'] is False
    assert inv_by_path['src.cc']['language'] == 'cpp'
    assert inv_by_path['CMakeLists.txt']['audited'] is False
    assert inv_by_path['CMakeLists.txt']['language'] == 'cmake'
    assert inv_by_path['cfg.yaml']['audited'] is False
    assert inv_by_path['cfg.yaml']['language'] == 'yaml'
    assert inv_by_path['nb.ipynb']['audited'] is False
    assert inv_by_path['nb.ipynb']['language'] == 'notebook'
    assert inv_by_path['run.sh']['audited'] is False
    assert inv_by_path['run.sh']['language'] == 'shell'
    assert inv_by_path['clean.py']['audited'] is True
    assert inv_by_path['clean.py']['language'] == 'python'
    # coverage report surfaces every unaudited language with a suppression rationale
    cov = audit_repository.summarize_coverage(inventory)
    uncovered = cov['uncovered_by_language']
    for lang in ('cpp', 'cmake', 'yaml', 'notebook', 'shell'):
        assert lang in uncovered, f"{lang} missing from coverage report"
        assert lang in cov['uncovered_suppressions'], f"no suppression record for {lang}"
    assert cov['covered_by_language'].get('python') == 1


def test_python_ast_check_still_runs(tmp_path):
    """AUD-002 keeps Python AST coverage; a known P0 pattern is still caught."""
    f = tmp_path / 'leak.py'
    f.write_text("df = a.merge(b, on='eventno')\n")
    rows = []
    audit_repository.audit_python(f, rows)
    assert any(r['code'] == 'EVENTNO_ONLY_JOIN' and r['severity'] == 'P0' for r in rows)


# --------------------------------------------------------------------------- #
# AUD-001: triaged baseline + fail-closed regression gate + waiver mechanism
# --------------------------------------------------------------------------- #
def _repo_with_findings(repo: Path) -> None:
    """Write a tiny repo with one P0 + one P1 finding. Outputs must live OUTSIDE
    ``repo`` so the audit never re-ingests its own baseline/output artifacts
    (which would otherwise self-flag and break the gate)."""
    (repo / 'bad.py').write_text(
        "import numpy as np\n"
        "m = a.merge(b, on='eventno')\n"          # P0 EVENTNO_ONLY_JOIN
        "p = '/home/billy/x.root'\n"               # P1 ABSOLUTE_PATH
    )
    (repo / 'ok.py').write_text("x = 1\n")


def test_gate_passes_when_baseline_covers_all(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    _repo_with_findings(repo)
    out = tmp_path / 'out'          # outside the audited root
    baseline = tmp_path / 'base.json'
    assert run_repo_audit.main(['--root', str(repo), '--out', str(out),
                                '--update-baseline', str(baseline)]) == 0
    data = json.loads(baseline.read_text())
    assert data['version'] == 1
    assert len(data['signatures']) >= 2
    rc = run_repo_audit.main(['--root', str(repo), '--out', str(out),
                              '--baseline', str(baseline)])
    assert rc == 0


def test_gate_fail_closed_on_new_p0_regression(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    _repo_with_findings(repo)
    out = tmp_path / 'out'
    baseline = tmp_path / 'base.json'
    run_repo_audit.main(['--root', str(repo), '--out', str(out),
                         '--update-baseline', str(baseline)])
    (repo / 'regression.py').write_text(
        "df2 = x.join(y, on=['eventno'])\n"  # P0 EVENTNO_ONLY_JOIN in a new file
    )
    rc = run_repo_audit.main(['--root', str(repo), '--out', str(out),
                              '--baseline', str(baseline)])
    assert rc == 1, "gate must fail-closed on a NEW P0 finding"
    assert (out / 'new_blocking_findings.json').is_file()
    blockers = json.loads((out / 'new_blocking_findings.json').read_text())
    assert any(b['path'].endswith('regression.py') for b in blockers)


def test_gate_does_not_block_new_p2(tmp_path):
    """P2/informational findings must never fail the gate (only P0/P1 do)."""
    repo = tmp_path / 'repo'
    repo.mkdir()
    _repo_with_findings(repo)
    out = tmp_path / 'out'
    baseline = tmp_path / 'base.json'
    run_repo_audit.main(['--root', str(repo), '--out', str(out),
                         '--update-baseline', str(baseline)])
    rc = run_repo_audit.main(['--root', str(repo), '--out', str(out),
                              '--baseline', str(baseline)])
    assert rc == 0


def test_inventory_mode_exits_zero_without_baseline(tmp_path):
    """Default (no --baseline) is inventory-only and never a gate (backward compat)."""
    repo = tmp_path / 'repo'
    repo.mkdir()
    _repo_with_findings(repo)
    out = tmp_path / 'out'
    rc = run_repo_audit.main(['--root', str(repo), '--out', str(out)])
    assert rc == 0


def test_committed_baseline_is_wellformed():
    """The repo's committed triaged baseline must load and be internally consistent."""
    baseline = REPO_ROOT / 'tools' / 'audit' / 'audit_baseline.json'
    if not baseline.is_file():
        pytest.skip("audit_baseline.json not committed yet")
    sigs, data = run_repo_audit.load_baseline(baseline)
    assert isinstance(sigs, set) and len(sigs) > 0
    assert data['version'] == run_repo_audit.BASELINE_VERSION
    # Every signature is a 3-part severity|code|path string.
    for sig in list(sigs)[:5]:
        assert sig.count('|') == 2
