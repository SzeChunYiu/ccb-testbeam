from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
from PIL import Image

from ccb_plotting.wiki_figures import build_all
from tools.figure_registry.builder import _emit_quantitative, _load_result
from tools.figure_registry.registry import Entry

REPO_ROOT = Path(__file__).resolve().parents[1]


def _manifest_by_id(manifest: dict[str, object]) -> dict[str, dict[str, object]]:
    figures = manifest["figures"]
    assert isinstance(figures, list)
    return {str(item["figure_id"]): item for item in figures}


def test_builds_all_evidence_bound_figures(tmp_path: Path) -> None:
    manifest = build_all(REPO_ROOT, tmp_path / "paper")
    assert manifest["schema"] == "ccb-paper-grade-wiki-figures/1"
    assert manifest["figure_count"] == 11
    by_id = _manifest_by_id(manifest)
    assert set(by_id) == {f"FIG-WIKI-{index:03d}" for index in range(1, 12)}

    for item in by_id.values():
        assert item["source_paths"]
        assert item["source_table_sha256"] == item["plotted_data_sha256"]
        assert all(check["ok"] for check in item["file_checks"])
        for kind in ("pdf", "svg", "png"):
            assert Path(item["outputs"][kind]["path"]).is_file()


def test_pid_and_pileup_source_values_are_preserved(tmp_path: Path) -> None:
    manifest = build_all(REPO_ROOT, tmp_path / "paper")
    by_id = _manifest_by_id(manifest)

    pid = pd.read_csv(by_id["FIG-WIKI-004"]["source_table"])
    assert pid["fold"].tolist() == [1, 2, 3, 4, 5]
    assert pid["auc"].round(12).tolist() == [
        0.964493359846,
        0.933923521677,
        0.961883408072,
        float("nan"),
        float("nan"),
    ]
    assert pid["full_auc"].nunique() == 1
    assert pid["full_auc"].iloc[0] == 0.8976036882035276

    pileup = pd.read_csv(by_id["FIG-WIKI-007"]["source_table"])
    nearest = pileup.iloc[:2]
    assert nearest["rate_MHz"].round(6).tolist() == [0.288703, 0.604551]
    assert (nearest["poisson_overlap"] * 100).round(4).tolist() == [5.0639, 10.3107]
    assert "not exactly 10%" in str(by_id["FIG-WIKI-007"]["caption"])


def test_metadata_does_not_overwrite_claim_status(tmp_path: Path) -> None:
    manifest = build_all(REPO_ROOT, tmp_path / "paper")
    by_id = _manifest_by_id(manifest)
    claims = pd.read_csv(by_id["FIG-WIKI-002"]["source_table"])
    assert "status" in claims.columns
    assert "figure_status" in claims.columns
    assert set(claims["figure_status"]) == {"REVIEW"}
    # CL-001 was reclassified from VALIDATED to GATED (issue #955); the ledger
    # must still contain at least one GATED row and the historical VALIDATED
    # status must not reappear while the data-contract gates are open.
    assert "GATED" in set(claims["status"])
    assert "VALIDATED" not in set(claims["status"])

    gain = pd.read_csv(by_id["FIG-WIKI-005"]["source_table"])
    mv0 = gain.loc[gain["estimate"] == "MV0 data/MC proxy"].iloc[0]
    assert mv0["slope_adc_per_MeV"] == 92
    assert mv0["uncertainty_adc_per_MeV"] == 28
    assert mv0["evidence"] == "GATED"


def test_generic_registry_renderer_is_compact_and_keeps_caption_external(
    tmp_path: Path,
) -> None:
    result_path = tmp_path / "result.json"
    result_path.write_text('{"value": 2.0, "uncertainty": 0.2}\n', encoding="utf-8")
    entry = Entry(
        id="TEST-INTERVAL",
        result=str(result_path),
        status="VALIDATED",
        kind="quantitative",
        caption="External scientific caption; it must not be drawn in the axes.",
    )
    snapshot = _load_result(result_path, entry)
    figure_path, source_path = _emit_quantitative(entry, snapshot, tmp_path / "out")

    with Image.open(figure_path) as image:
        assert image.size == (round(89 / 25.4 * 600), round(50 / 25.4 * 600))

    with source_path.open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))
    assert row["figure_status"] == "VALIDATED"
    assert row["caption"] == entry.caption
    assert row["figure_width_mm"] == "89.0"
    assert row["figure_height_mm"] == "50.0"
    assert row["figure_dpi"] == "600"
    assert "status" not in row


def test_committed_manifest_uses_portable_paths() -> None:
    payload = json.loads(
        (REPO_ROOT / "docs/figures/paper/manifest.json").read_text(encoding="utf-8")
    )
    for item in payload["figures"]:
        assert not Path(item["source_table"]).is_absolute()
        for output in item["outputs"].values():
            assert not Path(output["path"]).is_absolute()
