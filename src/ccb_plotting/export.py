"""Atomic, multi-format export with dimensions, hashes and QA metadata."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import platform
import sys
import tempfile
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.figure

from .quality import audit_figure, check_pdf, check_png, check_svg, checks_to_dict
from .style import DOUBLE_COLUMN_MM, SINGLE_COLUMN_MM


def _module_version(module_name: str) -> str:
    """Version of a plotting dependency; "unknown" if it cannot be imported."""
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        return "unknown"
    version = getattr(module, "__version__", None)
    return str(version) if version else "unknown"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_savefig(fig: matplotlib.figure.Figure, path: Path, **kwargs: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.stem}.", suffix=path.suffix, dir=path.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        fig.savefig(temporary, **kwargs)
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def export_figure(
    fig: matplotlib.figure.Figure,
    *,
    output_dir: Path,
    stem: str,
    column: str,
    height_mm: float,
    title: str,
) -> dict[str, Any]:
    """Validate and export PDF, SVG and 600-dpi PNG from one figure object."""
    width_mm = {"single": SINGLE_COLUMN_MM, "double": DOUBLE_COLUMN_MM}[column]
    issues = audit_figure(fig)
    errors = [issue for issue in issues if issue.severity == "error"]
    if errors:
        message = "\n".join(f"{item.code}: {item.message}" for item in errors)
        raise RuntimeError(f"figure {stem} failed pre-export QA:\n{message}")

    outputs = {
        "pdf": output_dir / f"{stem}.pdf",
        "svg": output_dir / f"{stem}.svg",
        "png": output_dir / f"{stem}.png",
    }
    common_metadata = {"Title": title, "Creator": "ccb_plotting"}
    _atomic_savefig(
        fig,
        outputs["pdf"],
        format="pdf",
        dpi=600,
        metadata={**common_metadata, "CreationDate": None, "ModDate": None},
    )
    _atomic_savefig(
        fig,
        outputs["svg"],
        format="svg",
        dpi=600,
        metadata={**common_metadata, "Date": None},
    )
    _atomic_savefig(
        fig, outputs["png"], format="png", dpi=600, metadata={"Software": "ccb_plotting"}
    )

    checks = [
        check_pdf(outputs["pdf"], width_mm=width_mm, height_mm=height_mm),
        check_svg(outputs["svg"], width_mm=width_mm, height_mm=height_mm),
        check_png(outputs["png"], width_mm=width_mm, height_mm=height_mm, dpi=600),
    ]
    failed = [item for item in checks if not item.ok]
    if failed:
        raise RuntimeError(f"figure {stem} failed file QA: {checks_to_dict(failed)}")

    return {
        "column": column,
        "width_mm": width_mm,
        "height_mm": height_mm,
        "qa_issues": [item.__dict__ for item in issues],
        "file_checks": checks_to_dict(checks),
        "outputs": {
            key: {
                "path": path.as_posix(),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for key, path in outputs.items()
        },
        "environment": {
            # Byte-stability contract: the audit gate
            # (tools/figure_registry/audit_regenerated.py) compares committed
            # vs regenerated artifacts. Byte identity is only required when
            # the full toolchain stamp matches; any differing component
            # (matplotlib, numpy, pandas, pillow, platform) downgrades binary
            # diffs to a warning. Platform is stamped because darwin and
            # manylinux Pillow/zlib wheels produce different PNG bytes from
            # identical pixels. Python records the project requires-python
            # floor (pyproject.toml), never the running patch version.
            "python": ">=3.11 (requires-python floor; patch version not stamped)",
            "matplotlib": matplotlib.__version__,
            "numpy": _module_version("numpy"),
            "pandas": _module_version("pandas"),
            "pillow": _module_version("PIL"),
            "platform": f"{sys.platform}-{platform.machine()}",
        },
    }


def atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    except Exception:
        Path(name).unlink(missing_ok=True)
        raise
