"""Atomic artifact writers for reproducible study outputs."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np


def atomic_write(path: Path, writer: Callable[[Path], None]) -> None:
    """Write via a temp file in the same directory, then rename into place."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{id(path)}.tmp")
    try:
        writer(tmp)
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def atomic_write_json(path: Path, payload: Any, *, indent: int = 2) -> None:
    """Atomically write JSON (mapping or JSON-serializable object)."""

    def _write(tmp: Path) -> None:
        if isinstance(payload, dict):
            text = json.dumps(payload, indent=indent, allow_nan=False, sort_keys=True)
        else:
            text = json.dumps(payload, indent=indent, allow_nan=False, default=str)
        tmp.write_text(text + "\n", encoding="utf-8")

    atomic_write(path, _write)


def write_json(path: Path, payload: dict[str, Any], *, indent: int = 2) -> None:
    """Atomically write a JSON document."""

    def _write(tmp: Path) -> None:
        tmp.write_text(json.dumps(payload, indent=indent, allow_nan=False) + "\n", encoding="utf-8")

    atomic_write(path, _write)


def write_npz(path: Path, **arrays: np.ndarray) -> None:
    """Atomically write a compressed NumPy archive."""

    def _write(tmp: Path) -> None:
        np.savez_compressed(tmp, **arrays)

    atomic_write(path, _write)
