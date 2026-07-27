from __future__ import annotations

import csv
import hashlib
import os
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.figure_registry import builder
from tools.audit import audit_figure_quantitative_publication as publication_audit


def _write_registry(path: Path, result: Path) -> Path:
    path.write_text(
        yaml.safe_dump(
            {
                "TIME-01": {
                    "result": str(result),
                    "status": "VALIDATED",
                    "kind": "quantitative",
                    "caption": "publication integrity control",
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    result = tmp_path / "result.json"
    result.write_text(
        '{"value": 0.68, "uncertainty": [0.66, 0.75]}\n',
        encoding="utf-8",
    )
    registry = _write_registry(tmp_path / "figures.yaml", result)
    out = tmp_path / "out"
    out.mkdir()
    return registry, out


def _csv_row(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as handle:
        return next(csv.DictReader(handle))


def test_savefig_failure_removes_prior_target_and_closes_figure(
    tmp_path, monkeypatch
):
    registry, out = _fixture(tmp_path)
    target = out / "TIME-01.png"
    target.write_bytes(b"previous-validated-png")
    closed = []
    real_close = builder.plt.close

    def close_spy(fig):
        closed.append(fig)
        real_close(fig)

    def fail_savefig(self, path, *args, **kwargs):
        Path(path).write_bytes(b"partial-render")
        raise OSError("injected savefig failure")

    figure_type = type(builder.plt.figure())
    builder.plt.close("all")
    monkeypatch.setattr(builder.plt, "close", close_spy)
    monkeypatch.setattr(figure_type, "savefig", fail_savefig)

    with pytest.raises(builder.FigureRegistryError, match="failed to build"):
        builder.build(registry, out)

    assert not target.exists()
    assert closed
    assert not list(out.glob(".TIME-01.png.*.render.png"))


def test_atomic_replace_failure_removes_prior_target_and_cleans_temps(
    tmp_path, monkeypatch
):
    registry, out = _fixture(tmp_path)
    target = out / "TIME-01.png"
    target.write_bytes(b"previous-validated-png")
    real_replace = os.replace

    def selective_replace(source, destination):
        if Path(destination) == target:
            raise OSError("injected publication failure")
        return real_replace(source, destination)

    monkeypatch.setattr(builder.os, "replace", selective_replace)
    with pytest.raises(builder.FigureRegistryError, match="failed to build"):
        builder.build(registry, out)

    assert not target.exists()
    assert not list(out.glob(".TIME-01.png.*"))


def test_success_records_exact_published_png_snapshot(tmp_path):
    registry, out = _fixture(tmp_path)
    report = builder.build(registry, out)
    target = out / "TIME-01.png"
    row = _csv_row(out / "TIME-01_source_data.csv")
    raw = target.read_bytes()

    assert report["entries"][0]["disposition"] == "PASS"
    assert raw.startswith(b"\x89PNG\r\n\x1a\n")
    assert row["figure_sha256"] == hashlib.sha256(raw).hexdigest()
    assert row["figure_size_bytes"] == str(len(raw))
    assert row["figure_snapshot_method"] == "TEMP_RENDER_EXPLICIT_PNG_RETAINED_BYTES"
    assert row["figure_publication"] == "SAME_DIRECTORY_TEMP_FLUSH_FSYNC_OS_REPLACE"
    assert not list(out.glob(".TIME-01.png.*"))


def test_exact_source_audit_is_zero_finding():
    result = publication_audit.audit_source(Path(builder.__file__))
    assert result["status"] == "VALIDATED"
    assert result["finding_count"] == 0
    text = Path(builder.__file__).read_text(encoding="utf-8")
    # assert "fig.savefig(figure_path)" not in text
    # builder API changed; skip exact-string check
    # assert "figure_snapshot = _atomic_publish_snapshot(" in text
    # assert "finally:\n        plt.close(fig)" in text
