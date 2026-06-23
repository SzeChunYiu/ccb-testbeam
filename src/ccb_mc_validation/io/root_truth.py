"""ROOT truth-tree inspection via uproot."""

from __future__ import annotations

from pathlib import Path
from typing import Any

DEFAULT_TRUTH_BRANCHES: tuple[str, ...] = (
    "Sci_bar_LayerID",
    "Sci_bar_LayerID1",
    "Sci_bar_PDG",
    "Sci_bar_EDep",
    "Sci_bar_Time",
    "Sci_bar_TrackID",
    "Sci_bar_TrackLength",
    "Sci_bar_Momentum_X",
    "Sci_bar_Momentum_Y",
    "Sci_bar_Momentum_Z",
)


def _require_uproot():
    try:
        import uproot
    except ImportError as exc:
        raise ImportError(
            "uproot is required for ROOT truth I/O; install with "
            "`pip install ccb-mc-validation[root]`"
        ) from exc
    return uproot


def list_root_objects(path: Path | str) -> list[str]:
    """List top-level keys (trees, histograms) in a ROOT file."""
    uproot = _require_uproot()
    with uproot.open(path) as handle:
        return list(handle.keys())


def resolve_truth_branches(
    path: Path | str,
    tree: str = "hibeam",
    *,
    required: tuple[str, ...] = DEFAULT_TRUTH_BRANCHES,
) -> dict[str, Any]:
    """Return branch metadata for the truth tree and verify required fields exist."""
    uproot = _require_uproot()
    with uproot.open(path) as handle:
        if tree not in handle:
            available = sorted(k.split(";")[0] for k in handle.keys())
            raise KeyError(f"tree {tree!r} not found; available: {available}")
        ttree = handle[tree]
        available = set(ttree.keys())
        missing = [b for b in required if b not in available]
        present = {name: str(ttree[name].typename) for name in required if name in available}
        return {
            "path": str(Path(path).resolve()),
            "tree": tree,
            "n_entries": int(ttree.num_entries),
            "present": present,
            "missing": missing,
            "ok": len(missing) == 0,
        }


def audit_truth_tree(
    path: Path | str,
    tree: str = "hibeam",
    *,
    required: tuple[str, ...] = DEFAULT_TRUTH_BRANCHES,
) -> dict[str, Any]:
    """Audit a MC truth ROOT file for schema completeness."""
    report = resolve_truth_branches(path, tree, required=required)
    report["status"] = "ok" if report["ok"] else "missing_branches"
    return report
