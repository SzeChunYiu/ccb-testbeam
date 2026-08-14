#!/usr/bin/env python3
"""Fail closed when generated CCB publication figures violate the style contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ccb_plotting.export import atomic_write_json  # noqa: E402
from ccb_plotting.quality import check_pdf, check_png, check_svg  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve(root: Path, recorded: str) -> Path:
    path = Path(recorded)
    return path if path.is_absolute() else root / path


def validate(root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    figures = manifest.get("figures")
    if not isinstance(figures, list) or not figures:
        raise ValueError("manifest contains no figures")

    expected_ids = {f"FIG-WIKI-{index:03d}" for index in range(1, 12)}
    actual_ids = {str(item.get("figure_id")) for item in figures}
    failures: list[str] = []
    if actual_ids != expected_ids:
        failures.append(
            f"figure ID set differs: missing={sorted(expected_ids - actual_ids)}, "
            f"extra={sorted(actual_ids - expected_ids)}"
        )

    records: list[dict[str, Any]] = []
    for item in figures:
        figure_id = str(item["figure_id"])
        width = float(item["width_mm"])
        height = float(item["height_mm"])
        outputs = item["outputs"]
        checks = []
        for kind, checker in (("pdf", check_pdf), ("svg", check_svg), ("png", check_png)):
            output = _resolve(root, str(outputs[kind]["path"]))
            if not output.is_file():
                failures.append(f"{figure_id}: missing {kind} output {output}")
                continue
            if kind == "png":
                check = checker(output, width_mm=width, height_mm=height, dpi=600)
            else:
                check = checker(output, width_mm=width, height_mm=height)
            checks.append({"kind": kind, "path": str(output), "ok": check.ok, **check.details})
            if not check.ok:
                failures.append(f"{figure_id}: {kind} dimension/content check failed")
            expected_hash = str(outputs[kind]["sha256"])
            actual_hash = _sha256(output)
            if actual_hash != expected_hash:
                failures.append(f"{figure_id}: {kind} hash differs from manifest")

        source = _resolve(root, str(item["source_table"]))
        if not source.is_file():
            failures.append(f"{figure_id}: source table is missing")
        else:
            actual_source_hash = _sha256(source)
            if actual_source_hash != str(item["source_table_sha256"]):
                failures.append(f"{figure_id}: source-table hash differs from manifest")
            header = source.read_text(encoding="utf-8").splitlines()[0].split(",")
            for required in ("figure_id", "figure_status", "figure_evidence_class"):
                if required not in header:
                    failures.append(f"{figure_id}: source table lacks {required}")

        records.append(
            {
                "figure_id": figure_id,
                "status": item["status"],
                "evidence_class": item["evidence_class"],
                "checks": checks,
            }
        )

    manifest_record = (
        manifest_path.relative_to(root).as_posix()
        if manifest_path.is_relative_to(root)
        else str(manifest_path)
    )
    report = {
        "schema": "ccb-paper-grade-plot-quality/1",
        "report_scope": "TECHNICAL_RENDERING_QA_ONLY",
        "scientific_authorisation": False,
        "manifest": manifest_record,
        "figure_count": len(figures),
        "passed": not failures,
        "failures": failures,
        "figures": records,
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("docs/figures/paper/manifest.json"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("docs/figures/paper/quality_report.json"),
    )
    args = parser.parse_args(argv)
    root = args.repo_root.resolve()
    manifest = args.manifest if args.manifest.is_absolute() else root / args.manifest
    report_path = args.report if args.report.is_absolute() else root / args.report
    report = validate(root, manifest)
    atomic_write_json(report_path, report)
    if not report["passed"]:
        for failure in report["failures"]:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    print(f"validated {report['figure_count']} paper-grade figures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
