from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_root_wiki_uses_exact_tracked_mv3_arithmetic() -> None:
    wiki = (ROOT / "WIKI.md").read_text(encoding="utf-8")
    summary = json.loads(
        (ROOT / "reports/mv3_stopping_v3_1782679272/mv3_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert "7,051/306,745 = 0.0229865" in wiki
    assert "55,619/249,484 = 0.222936" in wiki
    assert "Pearson χ² = 204,808.217968" in wiki
    assert "χ²/ndf = 68,269.405989" in wiki
    assert "exact source arithmetic is available" in wiki
    assert summary["data"]["all"]["counts"]["B8"] == 7051
    assert summary["mc"]["counts"]["B8"] == 55619
    assert summary["chi2_per_ndf"] == 68269.40598948313


def test_root_wiki_does_not_repeat_absence_narrative() -> None:
    wiki = (ROOT / "WIKI.md").read_text(encoding="utf-8")
    assert "reported χ²/ndf label is not reconstructable" not in wiki
    assert "without the underlying χ², ndf, bin variances, covariance, or exact counts" not in wiki
    assert "Recover exact counts/statistic" not in wiki
    assert "exact statistic/count provenance remain unresolved" not in wiki
