"""PUB-002 guard: fig20_key_results must contain no hard-coded quantitative
headline values and must build from the result registry (or render BLOCKED when
bundles are absent), never from in-source literals.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import matplotlib
import pytest

matplotlib.use("Agg")  # noqa: E402

# ccb_figures.config mutates global rcParams at import time (font.family,
# savefig.bbox='tight', ...). Snapshot the pre-import baseline so the mutation
# can be reverted once this module's tests finish; the leaked savefig.bbox would
# otherwise break figure-QA assertions (exact PNG pixel dimensions) in later
# modules that rely on the matplotlib default (bbox=None).
_RC_PARAMS_BASELINE = dict(matplotlib.rcParams)

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "src" / "ccb_figures" / "figures" / "fig20_key_results.py"
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
from ccb_figures.figures import fig20_key_results as mod  # noqa: E402


@pytest.fixture(autouse=True, scope="module")
def _restore_matplotlib_rcparams_after_module() -> None:
    """Revert ccb_figures.config's import-time rcParams mutation once these
    tests complete, so the side-effect cannot leak into later modules."""
    yield
    matplotlib.rcParams.update(_RC_PARAMS_BASELINE)

# Banned scientific literals (the values previously hard-coded in the cards).
# Layout coordinates (0.55 offsets, figure inches) are intentionally excluded —
# we anchor each pattern to its scientific units / context.
_BANNED = [
    r"σ.?6?8.*0\.55",       # sigma68 = 0.55 ns headline
    r"3\.05\s*MHz",         # R_max headline
    r"0\.986",              # PID AUC headline
    r"68[,.]?269",          # MV3 chi2/ndf headline
    r"0\.32\s*%",           # C12 fraction headline
    r"124\.8\s*ns",         # tau_eff headline
    r"2\.68σ",              # MV4 pull headline
    r"R_max\s*=\s*3",       # any literal R_max assignment in card text
    r"AUC\s*=\s*0\.9",      # any literal AUC assignment in card text
]


def test_source_has_no_quantitative_literals() -> None:
    src = FIG.read_text(encoding="utf-8")
    for pat in _BANNED:
        assert re.search(pat, src) is None, f"banned literal /{pat}/ present in fig20"


def test_source_routes_to_registry_not_literals() -> None:
    src = FIG.read_text(encoding="utf-8")
    assert "paper/figures.yaml" in src
    assert "EXTERNAL_BLOCKER" in src
    # The value path must read a JSON bundle, not return a constant.
    assert "json.loads" in src
    assert "value_key" in src


def test_build_runs_without_result_bundles(tmp_path, monkeypatch) -> None:
    """build() must succeed with NO result bundles on disk (all BLOCKED)."""
    monkeypatch.chdir(tmp_path)  # save_pub writes under cwd/docs/figures
    name = mod.build()
    assert name == "20_key_results"
    # Figure file produced.
    assert (tmp_path / "docs" / "figures" / "20_key_results.png").is_file()
