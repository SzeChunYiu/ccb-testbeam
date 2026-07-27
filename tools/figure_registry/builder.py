"""Fail-closed paper-figure builder with explicit scientific dispositions."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .registry import (  # noqa: E402
    Entry,
    RegistryFormatError,
    RegistrySnapshot,
    load_registry_snapshot,
    validate_registry,
)

MANAGED_ARTIFACT_POLICY = (
    "PREVIOUS_REPORT_RECONCILIATION_NONPASS_REMOVAL_REPORT_ROLLBACK"
)


class FigureRegistryError(RuntimeError):
    """Raised when a build-authorized registry entry cannot be built safely."""


@dataclass(frozen=True)
class ByteSnapshot:
    """One immutable byte snapshot and its content-addressed identity."""

    raw: bytes
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class ResultSnapshot:
    """A parsed result object bound to the exact bytes used for parsing."""

    payload: dict[str, Any]
    source: ByteSnapshot


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _same_file(left: Path, right: Path) -> bool:
    try:
        if left.resolve() == right.resolve():
            return True
    except OSError:
        pass
    try:
        return left.exists() and right.exists() and os.path.samefile(left, right)
    except OSError:
        return False


def _read_file_snapshot(path: Path, *, entry_id: str, label: str) -> ByteSnapshot:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise FigureRegistryError(
            f"{entry_id}: could not read {label} {path}: {exc}"
        ) from exc
    return ByteSnapshot(raw=raw, sha256=_sha256_bytes(raw), size_bytes=len(raw))


def _atomic_publish_snapshot(
    path: Path,
    snapshot: ByteSnapshot,
    *,
    entry_id: str = "publication",
    label: str = "artifact",
) -> ByteSnapshot:
    """Publish retained bytes atomically and verify the final target independently."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(snapshot.raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        if isinstance(exc, FigureRegistryError):
            raise
        raise FigureRegistryError(
            f"{entry_id}: could not publish {label} {path}: {exc}"
        ) from exc

    published = _read_file_snapshot(
        path, entry_id=entry_id, label=f"published {label}"
    )
    if published.sha256 != snapshot.sha256 or published.size_bytes != snapshot.size_bytes:
        raise FigureRegistryError(
            f"published target {path} does not match retained source snapshot"
        )
    return published


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


def _load_result(path: Path, entry: Entry) -> ResultSnapshot:
    snapshot = _read_file_snapshot(path, entry_id=entry.id, label="result JSON")
    try:
        text = snapshot.raw.decode("utf-8", errors="strict")
        payload = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FigureRegistryError(
            f"{entry.id}: could not decode result JSON {entry.result}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise FigureRegistryError(f"{entry.id}: result JSON must be an object")
    return ResultSnapshot(payload=payload, source=snapshot)


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
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(row))
    writer.writeheader()
    writer.writerow(row)
    raw = stream.getvalue().encode("utf-8")
    snapshot = ByteSnapshot(raw=raw, sha256=_sha256_bytes(raw), size_bytes=len(raw))
    _atomic_publish_snapshot(path, snapshot, entry_id="source-data", label="CSV")


def _emit_quantitative(
    entry: Entry,
    result_snapshot: ResultSnapshot,
    out_dir: Path,
) -> tuple[Path, Path]:
    """Render one compact interval figure; keep all prose in the source table."""
    result = result_snapshot.payload
    value_name, value = _central_value(result, entry)
    found, uncertainty_value = _find_key(result, entry.uncertainty_key)
    uncertainty = _first_scalar(uncertainty_value) if found else None
    if uncertainty is None:
        raise FigureRegistryError(
            f"{entry.id}: uncertainty key {entry.uncertainty_key!r} missing, null, "
            f"nonfinite, or nonnumeric in {entry.result}"
        )

    figure_path = out_dir / f"{entry.id}.png"
    render_path: Path | None = None
    width_mm, height_mm, dpi = 89.0, 50.0, 600
    rc = {
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans", "Arial", "Liberation Sans"],
        "font.size": 7.0,
        "axes.titlesize": 7.5,
        "axes.labelsize": 7.0,
        "axes.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.labelsize": 6.0,
        "ytick.labelsize": 6.0,
        "xtick.major.width": 0.5,
        "ytick.major.width": 0.5,
        "lines.linewidth": 0.9,
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
    }
    with plt.rc_context(rc):
        fig, axis = plt.subplots(
            figsize=(width_mm / 25.4, height_mm / 25.4),
            dpi=dpi,
            constrained_layout=True,
        )
        try:
            span = max(abs(uncertainty), abs(value) * 0.04, 1e-12)
            axis.errorbar(
                [value],
                [0.0],
                xerr=[uncertainty],
                fmt="o",
                color="#0072B2",
                ecolor="#4D4D4D",
                capsize=2.0,
            )
            axis.set_xlim(value - 2.4 * span, value + 2.4 * span)
            axis.set_ylim(-0.8, 0.8)
            axis.set_yticks([])
            axis.set_xlabel(value_name.replace("/", " / "))
            axis.set_title(entry.id, loc="left", pad=5)
            axis.xaxis.grid(True, color="#D8D8D8", linewidth=0.45, alpha=0.7)
            axis.set_axisbelow(True)

            figure_path.parent.mkdir(parents=True, exist_ok=True)
            fd, render_name = tempfile.mkstemp(
                prefix=f".{figure_path.name}.", suffix=".render.png", dir=figure_path.parent
            )
            os.close(fd)
            render_path = Path(render_name)
            fig.savefig(render_path, format="png", dpi=dpi, metadata={"Software": "ccb figure registry"})
            rendered = _read_file_snapshot(
                render_path, entry_id=entry.id, label="temporary rendered figure"
            )
            figure_snapshot = _atomic_publish_snapshot(
                figure_path,
                rendered,
                entry_id=entry.id,
                label="quantitative figure",
            )
        except FigureRegistryError:
            raise
        except Exception as exc:
            raise FigureRegistryError(
                f"{entry.id}: could not render quantitative figure {figure_path}: {exc}"
            ) from exc
        finally:
            plt.close(fig)
            if render_path is not None:
                render_path.unlink(missing_ok=True)

    source_path = out_dir / f"{entry.id}_source_data.csv"
    _write_source_csv(
        source_path,
        {
            "figure_id": entry.id,
            "figure_status": entry.status,
            "figure_kind": entry.kind,
            "caption": entry.caption,
            "value_name": value_name,
            "central_value": repr(value),
            "uncertainty_key": entry.uncertainty_key,
            "uncertainty": repr(uncertainty),
            "result_path": entry.result,
            "result_sha256": result_snapshot.source.sha256,
            "result_size_bytes": result_snapshot.source.size_bytes,
            "result_snapshot_method": "SINGLE_READ_STRICT_UTF8_EXACT_BYTES",
            "figure_sha256": figure_snapshot.sha256,
            "figure_size_bytes": figure_snapshot.size_bytes,
            "figure_width_mm": width_mm,
            "figure_height_mm": height_mm,
            "figure_dpi": dpi,
            "figure_snapshot_method": "TEMP_RENDER_EXPLICIT_PNG_RETAINED_BYTES",
            "figure_publication": "SAME_DIRECTORY_TEMP_FLUSH_FSYNC_OS_REPLACE",
            "table_path": entry.table or "",
            "input_sha256": entry.input_sha256 or "",
        },
    )
    return figure_path, source_path


def _emit_existing_artifact(
    entry: Entry,
    out_dir: Path,
    subdirectory: str,
) -> tuple[Path, Path]:
    if not entry.source_figure:
        raise FigureRegistryError(f"{entry.id}: source_figure is required")
    source = Path(entry.source_figure)
    target_dir = out_dir / subdirectory
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix or ".artifact"
    target = target_dir / f"{entry.id}{suffix}"
    if _same_file(source, target):
        raise FigureRegistryError(f"{entry.id}: output aliases source artifact")
    source_snapshot = _read_file_snapshot(source, entry_id=entry.id, label="source artifact")
    published_snapshot = _atomic_publish_snapshot(
        target, source_snapshot, entry_id=entry.id, label="source artifact"
    )
    metadata = target_dir / f"{entry.id}_source_data.csv"
    _write_source_csv(
        metadata,
        {
            "figure_id": entry.id,
            "status": entry.status,
            "kind": entry.kind,
            "source_artifact": entry.source_figure,
            "source_sha256": source_snapshot.sha256,
            "source_size_bytes": source_snapshot.size_bytes,
            "source_snapshot_method": "SINGLE_READ_EXACT_BYTES",
            "published_target_sha256": published_snapshot.sha256,
            "published_target_size_bytes": published_snapshot.size_bytes,
            "publication": "SAME_DIRECTORY_TEMP_FLUSH_FSYNC_OS_REPLACE",
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
        "managed_artifacts": [],
        "quantitative": entry.is_quantitative,
    }


def _valid_managed_relative(path: Path, entry_id: str) -> bool:
    parts = path.parts
    if len(parts) == 1:
        return parts[0] in {f"{entry_id}.png", f"{entry_id}_source_data.csv"}
    if len(parts) != 2 or parts[0] not in {"source", "illustrative"}:
        return False
    name = parts[1]
    return name == f"{entry_id}_source_data.csv" or name.startswith(f"{entry_id}.")


def _managed_path_from_text(output: Path, value: str, entry_id: str) -> Path:
    raw = Path(value)
    root = output.resolve()
    candidates = [raw.resolve()]
    if not raw.is_absolute():
        candidates.append((output / raw).resolve())
    resolved: Path | None = None
    for candidate in candidates:
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        resolved = candidate
        break
    if resolved is None:
        raise FigureRegistryError(
            f"{entry_id}: prior managed artifact escapes output directory: {value}"
        )
    relative = resolved.relative_to(root)
    if not _valid_managed_relative(relative, entry_id):
        raise FigureRegistryError(
            f"{entry_id}: prior report path is not a canonical managed artifact: {value}"
        )
    return output / relative


def _relative_managed_path(output: Path, path: Path, entry_id: str) -> str:
    root = output.resolve()
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise FigureRegistryError(
            f"{entry_id}: managed artifact escapes output directory: {path}"
        ) from exc
    if not _valid_managed_relative(relative, entry_id):
        raise FigureRegistryError(
            f"{entry_id}: noncanonical managed artifact path: {path}"
        )
    return relative.as_posix()


def _expected_entry_output_paths(entry: Entry, out_dir: Path) -> set[Path]:
    if entry.is_quantitative:
        return {
            out_dir / f"{entry.id}.png",
            out_dir / f"{entry.id}_source_data.csv",
        }
    if entry.kind in {"illustrative", "figure_sourced"}:
        subdirectory = "illustrative" if entry.is_illustrative else "source"
        source = Path(entry.source_figure or "")
        suffix = source.suffix or ".artifact"
        target_dir = out_dir / subdirectory
        return {
            target_dir / f"{entry.id}{suffix}",
            target_dir / f"{entry.id}_source_data.csv",
        }
    return set()


def _protected_input_paths(entry: Entry) -> tuple[Path, ...]:
    values = [entry.result, entry.source_figure, entry.table]
    return tuple(Path(value) for value in values if value)


def _remove_paths(
    paths: Iterable[Path],
    *,
    entry: Entry | None,
    output: Path,
    entry_id: str | None = None,
) -> list[str]:
    removed: list[str] = []
    protected = _protected_input_paths(entry) if entry is not None else ()
    entry_id = entry.id if entry is not None else (entry_id or "removed-entry")
    for path in sorted(set(paths), key=lambda item: str(item)):
        if path.is_symlink():
            raise FigureRegistryError(
                f"{entry_id}: refusing to manage symbolic-link output {path}"
            )
        if any(_same_file(path, source) for source in protected):
            continue
        if path.exists():
            if not path.is_file():
                raise FigureRegistryError(
                    f"{entry_id}: managed output is not a regular file: {path}"
                )
            path.unlink()
            removed.append(_relative_managed_path(output, path, entry_id))
    return removed


def _remove_managed_entry_outputs(
    entry: Entry,
    out_dir: Path,
    prior_paths: Iterable[Path] = (),
    keep_paths: Iterable[Path] = (),
) -> list[str]:
    """Remove canonical current/prior outputs without touching declared inputs."""
    keep = set(keep_paths)
    candidates = set(prior_paths) | _expected_entry_output_paths(entry, out_dir)
    return _remove_paths(candidates - keep, entry=entry, output=out_dir)


def _load_previous_build_report(output: Path) -> dict[str, Any] | None:
    path = output / "build_report.json"
    if not path.exists():
        return None
    snapshot = _read_file_snapshot(path, entry_id="build-report", label="prior report")
    try:
        text = snapshot.raw.decode("utf-8", errors="strict")
        payload = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FigureRegistryError(f"could not decode prior build report {path}: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("entries"), list):
        raise FigureRegistryError(f"prior build report {path} has no entries list")
    return payload


def _bootstrap_previous_outputs(
    output: Path,
    entries: list[Entry],
) -> dict[str, set[Path]]:
    """Adopt only exact current canonical paths when no prior report exists."""
    expected = {
        entry.id: _expected_entry_output_paths(entry, output) for entry in entries
    }
    candidates = list(output.glob("*.png")) + list(
        output.glob("*_source_data.csv")
    )
    candidates += [
        path for path in (output / "source").glob("*") if not path.name.startswith(".")
    ]
    candidates += [
        path
        for path in (output / "illustrative").glob("*")
        if not path.name.startswith(".")
    ]
    adopted: dict[str, set[Path]] = {entry.id: set() for entry in entries}
    for candidate in candidates:
        owners = [entry_id for entry_id, paths in expected.items() if candidate in paths]
        if len(owners) != 1:
            raise FigureRegistryError(
                "existing canonical figure artifact cannot be attributed without "
                f"build_report.json: {candidate}"
            )
        adopted[owners[0]].add(candidate)
    return {entry_id: paths for entry_id, paths in adopted.items() if paths}


def _paths_from_previous_record(output: Path, record: dict[str, Any]) -> set[Path]:
    entry_id = record.get("id")
    if not isinstance(entry_id, str) or not entry_id:
        raise FigureRegistryError("prior build report contains an entry without a valid id")
    raw_paths: list[str] = []
    managed = record.get("managed_artifacts")
    if managed is not None:
        if not isinstance(managed, list) or not all(isinstance(item, str) for item in managed):
            raise FigureRegistryError(
                f"{entry_id}: prior managed_artifacts must be a list of strings"
            )
        raw_paths.extend(managed)
    else:
        for key in ("figure", "source_data"):
            value = record.get(key)
            if isinstance(value, str) and value:
                raw_paths.append(value)
    return {
        _managed_path_from_text(output, value, entry_id)
        for value in raw_paths
    }


def _previous_managed_outputs(
    output: Path,
    report: dict[str, Any] | None,
) -> dict[str, set[Path]]:
    if report is None:
        return {}
    previous: dict[str, set[Path]] = {}
    for item in report["entries"]:
        if not isinstance(item, dict):
            raise FigureRegistryError("prior build report entries must be objects")
        entry_id = item.get("id")
        if not isinstance(entry_id, str) or not entry_id:
            raise FigureRegistryError("prior build report contains an entry without a valid id")
        if entry_id in previous:
            raise FigureRegistryError(f"prior build report duplicates entry id {entry_id}")
        previous[entry_id] = _paths_from_previous_record(output, item)
    return previous


def _snapshot_managed_state(paths: Iterable[Path]) -> dict[Path, ByteSnapshot | None]:
    state: dict[Path, ByteSnapshot | None] = {}
    for path in set(paths):
        if path.is_symlink():
            raise FigureRegistryError(f"refusing to snapshot symbolic-link output {path}")
        if path.exists():
            if not path.is_file():
                raise FigureRegistryError(f"managed output is not a regular file: {path}")
            state[path] = _read_file_snapshot(
                path, entry_id="build-transaction", label="managed artifact"
            )
        else:
            state[path] = None
    return state


def _restore_managed_state(state: dict[Path, ByteSnapshot | None]) -> None:
    errors: list[str] = []
    for path, snapshot in state.items():
        try:
            if snapshot is None:
                if path.is_symlink():
                    raise FigureRegistryError(
                        f"refusing to remove symbolic-link output during rollback: {path}"
                    )
                path.unlink(missing_ok=True)
            else:
                _atomic_publish_snapshot(
                    path,
                    snapshot,
                    entry_id="build-rollback",
                    label="managed artifact",
                )
        except Exception as exc:  # pragma: no cover - catastrophic filesystem failure
            errors.append(f"{path}: {exc}")
    if errors:
        raise FigureRegistryError(
            "could not restore managed artifact state:\n  - " + "\n  - ".join(errors)
        )


def _reconcile_registry_outputs(
    entries: list[Entry],
    out_dir: Path,
    previous: dict[str, set[Path]],
) -> list[str]:
    """Remove outputs for IDs no longer present in the current registry."""
    current_ids = {entry.id for entry in entries}
    removed: list[str] = []
    for entry_id, paths in previous.items():
        if entry_id in current_ids:
            continue
        removed.extend(
            _remove_paths(
                paths, entry=None, output=out_dir, entry_id=entry_id
            )
        )
    return removed


def _process_entry(
    entry: Entry,
    out_dir: Path,
    paper_only: bool,
    allow_preliminary: bool,
    prior_paths: Iterable[Path] = (),
) -> tuple[dict[str, Any], list[str]]:
    record = _base_record(entry)
    disposition = entry.disposition
    if disposition == "BLOCKED":
        removed = _remove_managed_entry_outputs(entry, out_dir, prior_paths)
        record["disposition"] = "BLOCKED"
        record["reason"] = "scientific status EXTERNAL_BLOCKER is non-buildable"
        return record, removed
    if disposition == "QUARANTINED":
        removed = _remove_managed_entry_outputs(entry, out_dir, prior_paths)
        record["disposition"] = "QUARANTINED"
        record["reason"] = (
            f"scientific status {entry.status} is retained but not paper-authorizing"
        )
        return record, removed
    if disposition == "CONDITIONAL" and paper_only and not allow_preliminary:
        removed = _remove_managed_entry_outputs(entry, out_dir, prior_paths)
        record["disposition"] = "BLOCKED"
        record["reason"] = "PRELIMINARY excluded unless --allow-preliminary is set"
        return record, removed

    if disposition == "ILLUSTRATIVE":
        figure, source_data = _emit_existing_artifact(entry, out_dir, "illustrative")
        record["disposition"] = "PASS"
        record["reason"] = "illustrative source artifact copied without numeric extraction"
    elif entry.is_figure_sourced:
        figure, source_data = _emit_existing_artifact(entry, out_dir, "source")
        record["disposition"] = "PASS"
        record["reason"] = "existing source artifact copied without scalar extraction"
    elif entry.is_quantitative:
        result_snapshot = _load_result(Path(entry.result), entry)
        _validate_table_hash(entry)
        figure, source_data = _emit_quantitative(entry, result_snapshot, out_dir)
        record["disposition"] = "PASS"
        record["reason"] = f"built from {entry.result}"
    else:
        raise FigureRegistryError(f"{entry.id}: unsupported kind {entry.kind!r}")

    current = {figure, source_data}
    removed = _remove_managed_entry_outputs(
        entry, out_dir, prior_paths, keep_paths=current
    )
    record["figure"] = str(figure)
    record["source_data"] = str(source_data)
    record["managed_artifacts"] = sorted(
        _relative_managed_path(out_dir, path, entry.id) for path in current
    )
    return record, removed


def _registry_provenance(snapshot: RegistrySnapshot) -> dict[str, Any]:
    """Return report metadata bound to the exact registry bytes used for parsing."""

    return {
        "path": snapshot.path,
        "sha256": snapshot.sha256,
        "size_bytes": snapshot.size_bytes,
        "snapshot_method": snapshot.snapshot_method,
        "entry_count": len(snapshot.entries),
    }


def build(
    registry_path: str | Path,
    out_dir: str | Path,
    paper_only: bool = True,
    allow_preliminary: bool = False,
) -> dict[str, Any]:
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    try:
        snapshot = load_registry_snapshot(registry_path)
    except RegistryFormatError as exc:
        raise FigureRegistryError(f"registry format error: {exc}") from exc
    entries = list(snapshot.entries)
    problems = validate_registry(entries)
    previous_report = _load_previous_build_report(output)
    if previous_report is None:
        previous = _bootstrap_previous_outputs(output, entries)
    else:
        previous = _previous_managed_outputs(output, previous_report)
    transaction_paths = set().union(*previous.values()) if previous else set()
    for entry in entries:
        transaction_paths.update(_expected_entry_output_paths(entry, output))
    before = _snapshot_managed_state(transaction_paths)

    report: dict[str, Any] = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "registry": snapshot.path,
        "registry_provenance": _registry_provenance(snapshot),
        "paper_only": paper_only,
        "allow_preliminary": allow_preliminary,
        "managed_artifact_policy": MANAGED_ARTIFACT_POLICY,
        "previous_report_present": previous_report is not None,
        "validation_problems": problems,
        "entries": [],
        "cleanup": {"removed": [], "removed_count": 0},
        "summary": {},
    }
    removed: list[str] = []
    report_published = False
    try:
        if problems:
            for entry_id, paths in previous.items():
                removed.extend(
                    _remove_paths(
                        paths, entry=None, output=output, entry_id=entry_id
                    )
                )
            report["cleanup"] = {
                "removed": sorted(set(removed)),
                "removed_count": len(set(removed)),
            }
            report["summary"] = {
                "status": "INVALID_REGISTRY",
                "n_problems": len(problems),
            }
            _atomic_write_json(output / "build_report.json", report)
            report_published = True
            raise FigureRegistryError(
                "registry failed validation:\n  - " + "\n  - ".join(problems)
            )

        removed.extend(_reconcile_registry_outputs(entries, output, previous))
        failures: list[str] = []
        for entry in entries:
            prior_paths = previous.get(entry.id, set())
            try:
                record, entry_removed = _process_entry(
                    entry,
                    output,
                    paper_only,
                    allow_preliminary,
                    prior_paths,
                )
                removed.extend(entry_removed)
            except FigureRegistryError as exc:
                removed.extend(
                    _remove_managed_entry_outputs(entry, output, prior_paths)
                )
                record = _base_record(entry)
                record["disposition"] = "FAIL"
                record["reason"] = str(exc)
                failures.append(str(exc))
            report["entries"].append(record)

        counts = {name: 0 for name in ("PASS", "FAIL", "BLOCKED", "QUARANTINED")}
        quantitative = illustrative = source_only = 0
        for record in report["entries"]:
            counts[record["disposition"]] = counts.get(record["disposition"], 0) + 1
            if record["disposition"] == "PASS":
                if record["kind"] == "quantitative":
                    quantitative += 1
                elif record["kind"] == "illustrative":
                    illustrative += 1
                elif record["kind"] == "figure_sourced":
                    source_only += 1
        report["cleanup"] = {
            "removed": sorted(set(removed)),
            "removed_count": len(set(removed)),
        }
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
        report_published = True
        if failures:
            raise FigureRegistryError(
                f"{len(failures)} figure(s) failed to build:\n  - "
                + "\n  - ".join(failures)
            )
        return report
    except FigureRegistryError:
        if not report_published:
            _restore_managed_state(before)
        raise
    except Exception as exc:
        try:
            _restore_managed_state(before)
        except FigureRegistryError as rollback_exc:
            raise FigureRegistryError(
                f"build failed and managed-artifact rollback failed: {rollback_exc}"
            ) from exc
        raise FigureRegistryError(f"could not publish coherent build state: {exc}") from exc


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
