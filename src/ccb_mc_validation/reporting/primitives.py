"""Low-level figure persistence with metadata sidecars."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from matplotlib.figure import Figure


def save_figure(
    fig: Figure,
    path: str | Path,
    *,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Save *fig* to disk and write a JSON metadata sidecar alongside it."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)

    sidecar = out_path.with_suffix(out_path.suffix + ".meta.json")
    payload = {
        "figure_path": out_path.name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "format": out_path.suffix.lstrip(".") or "png",
        "metadata": metadata or {},
    }
    sidecar.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out_path
