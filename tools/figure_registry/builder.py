"""Fail-closed paper-figure builder with explicit scientific dispositions."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .registry import Entry, load_registry, validate_registry  # noqa: E402


class FigureRegistryError(RuntimeError):
    """Raised when a build-authorized registry entry cannot be built safely."""


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _find_key(obj: Any, key: str) -> tuple[bool, Any]:
    if not isinstance(obj, dict):
        return False, None
    if "/" in key:
        current: Any = obj
        for part in key.split("/"):
            if not isinstance(current, dict) or part not in current:
                return False, None
            current = current[part]
        return True, current
    if key in obj:
        return True, obj[key]
    for value in obj.values():
        if isinstance(value, dict) and key in value:
            return True, value[key]
    return False, None


def _first_scalar(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (list, tuple)) and value:
        numbers = [float(item) for item in value if isinstance(item, (int, float))]
        numbers = [item for item in numbers if math.isfinite(item)]
        if len(numbers) >= 2:
            return abs(numbers[-1] - numbers[0]) / 2.0
        if numbers:
            return numbers[0]
    return None


def _central_value(result: dict[str, Any], entry: Entry) -> tuple[str, float]:
    candidates: list[str] = []
    if entry.value_key:
        candidates.append(entry.value_key)
    found, primary_metric = _find_key(result, "primary_metric")
    if found and isinstance(primary_metric, str):
        candidates.append(primary_metric)
    candidates.extend(["value", "central", "primary_value", "point_estimate", "estimate"])
    for name in candidates:
        found, value = _find_key(result, name)
        scalar = _first_scalar(value) if found else None
        if scalar is not None:
            return name, scalar
    raise FigureRegistryError(
        f"{entry.id}: could not locate a finite central value in {entry.result!r}; "
        f"set 'value_key' (tried {candidates})"
    )


def _load_result(path: Path, entry: Entry) -> dict[str, Any]:
    if not path.exists():
        raise FigureRegistryError(f"{entry.id}: result file not found: {entry.result}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FigureRegistryError(
            f"{entry.id}: could not read result JSON {entry.result}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise FigureRegistryError(f"{entry.id}: result JSON must be an object")
    return payload


def _validate_table_hash(entry: Entry) -> None:
    if not entry.input_sha256:
        return
    if not entry.table:
        raise FigureRegistryError(f"{entry.id}: input_sha256 recorded without table")
    path = Path(entry.table)
    if not path.exists():
        raise FigureRegistryError(f"{entry.id}: table not found: {entry.table}")
    actual = sha256_file(path)
    if actual != entry.input_sha256:
        raise FigureRegistryError(
            f"{entry.id}: source-table sha256 mismatch for {entry.table}; "
            f"recorded={entry.input_sha256} actual={actual}"
        )


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _write_source_csv(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)


def _emit_quantitative(entry: Entry, result: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    value_name, value = _central_value(result, entry)
    found, uncertainty_value = _find_key(result, entry.uncertainty_key)
    uncertainty = _first_scalar(uncertainty_value) if found else None
    if uncertainty is None:
        raise FigureRegistryError(
            f"{entry.id}: uncertainty key {entry.uncertainty_key!r} missing, null, "
            f"nonfinite, or nonnumeric in {entry.result}"
        )

    fig, axis = plt.subplots(figsize=(6.0, 4.0), dpi=150)
    axis.errorbar([0], [value], yerr=[uncertainty], fmt="o", capsize=4)
    axis.set_xlim(-0.5, 0.5)
    axis.set_xticks([0])
    axis.set_xticklabels([entry.id])
    axis.set_ylabel(value_name)
    axis.set_title(f"{entry.id} [{entry.status}]")
    axis.grid(True, linewidth=0.5)
    fig.text(0.5, 0.01, entry.caption, ha="center", fontsize=7, wrap=True)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    figure_path = out_dir / f"{entry.id}.png"
    fig.savefig(figure_path)
    plt.close(fig)

    source_path = out_dir / f"{entry.id}_source_data.csv"
    _write_source_csv(
        source_path,
        {
            "figure_id": entry.id,
            "status": entry.status,
            "kind": entry.kind,
            "value_name": value_name,
            "central_value": repr(value),
            "uncertainty_key": entry.uncertainty_key,
            "uncertainty": repr(uncertainty),
            "result_path": entry.result,
            "result_sha256": sha256_file(entry.result),
            "table_path": entry.table or "",
            "input_sha256": entry.input_sha256 or "",
        },
    )
    return figure_path, source_path


def _emit_existing_artifact(entry: Entry, out_dir: Path, subdirectory: str) -> tuple[Path, Path]:
    if not entry.source_figure:
        raise FigureRegistryError(f"{entry.id}: source_figure is required")
    source = Path(entry.source_figure)
    if not source.exists() or not source.is_file():
        raise FigureRegistryError(
            f"{entry.id}: source artifact not found: {entry.source_figure}"
        )
    target_dir = out_dir / subdirectory
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix or ".artifact"
    target = target_dir / f"{entry.id}{suffix}"
    if source.resolve() == target.resolve():
        raise FigureRegistryError(f"{entry.id}: output aliases source artifact")
    shutil.copy2(source, target)
    metadata = target_dir / f"{entry.id}_source_data.csv"
    _write_source_csv(
        metadata,
        {
            "figure_id": entry.id,
            "status": entry.status,
            "kind": entry.kind,
            "source_artifact": entry.source_figure,
            "source_sha256": sha256_file(source),
            "source_size_bytes": source.stat().st_size,
            "caption": entry.caption,
        },
    )
    return target, metadata


def _base_record(entry: Entry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "status": entry.status,
        "kind": entry.kind,
        "scientific_disposition": entry.disposition,
        "disposition": None,
        "reason": "",
        "figure": None,
        "source_data": None,
        "quantitative": entry.is_quantitative,
    }


def _process_entry(
    entry: Entry,
    out_dir: Path,
    paper_only: bool,
    allow_preliminary: bool,
) -> dict[str, Any]:
    record = _base_record(entry)
    disposition = entry.disposition

    if disposition == "BLOCKED":
        record["disposition"] = "BLOCKED"
        record["reason"] = "scientific status EXTERNAL_BLOCKER is non-buildable"
        return record
    if disposition == "QUARANTINED":
        record["disposition"] = "QUARANTINED"
        record["reason"] = (
            f"scientific status {entry.status} is retained but not paper-authorizing"
        )
        return record
    if disposition == "CONDITIONAL" and paper_only and not allow_preliminary:
        record["disposition"] = "BLOCKED"
        record["reason"] = "PRELIMINARY excluded unless --allow-preliminary is set"
        return record

    if disposition == "ILLUSTRATIVE":
        figure, source_data = _emit_existing_artifact(entry, out_dir, "illustrative")
        record["disposition"] = "PASS"
        record["reason"] = "illustrative source artifact copied without numeric extraction"
    elif entry.is_figure_sourced:
        figure, source_data = _emit_existing_artifact(entry, out_dir, "source")
        record["disposition"] = "PASS"
        record["reason"] = "existing source artifact copied without scalar extraction"
    elif entry.is_quantitative:
        result = _load_result(Path(entry.result), entry)
        _validate_table_hash(entry)
        figure, source_data = _emit_quantitative(entry, result, out_dir)
        record["disposition"] = "PASS"
        record["reason"] = f"built from {entry.result}"
    else:
        raise FigureRegistryError(f"{entry.id}: unsupported kind {entry.kind!r}")

    record["figure"] = str(figure)
    record["source_data"] = str(source_data)
    return record


def build(
    registry_path: str | Path,
    out_dir: str | Path,
    paper_only: bool = True,
    allow_preliminary: bool = False,
) -> dict[str, Any]:
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    entries = load_registry(registry_path)
    problems = validate_registry(entries)
    report: dict[str, Any] = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "registry": str(registry_path),
        "paper_only": paper_only,
        "allow_preliminary": allow_preliminary,
        "validation_problems": problems,
        "entries": [],
        "summary": {},
    }
    if problems:
        report["summary"] = {"status": "INVALID_REGISTRY", "n_problems": len(problems)}
        _atomic_write_json(output / "build_report.json", report)
        raise FigureRegistryError(
            "registry failed validation:\n  - " + "\n  - ".join(problems)
        )

    failures: list[str] = []
    for entry in entries:
        try:
            record = _process_entry(entry, output, paper_only, allow_preliminary)
        except FigureRegistryError as exc:
            record = _base_record(entry)
            record["disposition"] = "FAIL"
            record["reason"] = str(exc)
            failures.append(str(exc))
        report["entries"].append(record)

    counts = {name: 0 for name in ("PASS", "FAIL", "BLOCKED", "QUARANTINED")}
    quantitative = 0
    illustrative = 0
    source_only = 0
    for record in report["entries"]:
        counts[record["disposition"]] = counts.get(record["disposition"], 0) + 1
        if record["disposition"] == "PASS":
            if record["kind"] == "quantitative":
                quantitative += 1
            elif record["kind"] == "illustrative":
                illustrative += 1
            elif record["kind"] == "figure_sourced":
                source_only += 1
    report["summary"] = {
        "n_entries": len(entries),
        "pass": counts["PASS"],
        "fail": counts["FAIL"],
        "blocked": counts["BLOCKED"],
        "quarantined": counts["QUARANTINED"],
        "quantitative_figures": quantitative,
        "illustrative_figures": illustrative,
        "source_artifacts": source_only,
    }
    _atomic_write_json(output / "build_report.json", report)
    if failures:
        raise FigureRegistryError(
            f"{len(failures)} figure(s) failed to build:\n  - "
            + "\n  - ".join(failures)
        )
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--allow-preliminary", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        report = build(
            args.registry,
            args.out,
            paper_only=True,
            allow_preliminary=args.allow_preliminary,
        )
    except FigureRegistryError as exc:
        print(f"FigureRegistryError: {exc}", file=sys.stderr)
        return 1
    summary = report["summary"]
    print(
        f"OK: {summary['pass']} passed, {summary['blocked']} blocked, "
        f"{summary['quarantined']} quarantined, {summary['fail']} failed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
