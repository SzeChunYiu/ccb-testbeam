"""Validated paper-figure builder.

For each registry entry the builder does one of three things and records it in
``build_report.json``:

* **BUILD (PASS)** -- a paper-permitted quantitative status (VALIDATED, TENSION,
  or PRELIMINARY when ``--allow-preliminary``).  The builder verifies the result
  file exists, loads it, asserts the uncertainty key is present and non-null,
  optionally verifies the source table's sha256, then emits a small matplotlib
  (Agg) figure whose every number is *read from the result JSON / source table*
  -- never a literal -- plus a per-figure ``<id>_source_data.csv``.
* **ILLUSTRATIVE (PASS)** -- a schematic (``kind: illustrative``).  Rendered into
  a separate ``illustrative/`` sub-directory and clearly labelled; it is never
  counted among the quantitative figures.
* **BLOCKED** -- an ``EXTERNAL_BLOCKER`` (result compute-blocked / not yet
  present), or a PRELIMINARY entry when ``--allow-preliminary`` is not set.  A
  blocked entry is *not* a hard failure.

On ANY hard failure (missing result for a build entry, missing/null uncertainty,
sha256 mismatch, a status outside the allowed set / malformed registry) the
builder writes what report it can and raises :class:`FigureRegistryError`, which
the CLI turns into a nonzero exit.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless / reproducible
import matplotlib.pyplot as plt  # noqa: E402

from .registry import (  # noqa: E402
    _PAPER_QUANTITATIVE_STATUSES,
    Entry,
    load_registry,
    validate_registry,
)


class FigureRegistryError(RuntimeError):
    """Raised on any hard failure while building paper figures."""


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def sha256_file(path: str | Path) -> str:
    """Return the hex sha256 of a file's bytes (streamed)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_key(obj: Any, key: str) -> tuple[bool, Any]:
    """Find ``key`` at the top level or one level down (metrics-style nesting).

    Returns ``(found, value)``.  Result JSONs in this repo nest headline numbers
    under blocks like ``winner_metrics`` / ``metrics`` / ``primary``, so we look
    top-level first, then inside nested dicts.
    """
    if not isinstance(obj, dict):
        return (False, None)
    if key in obj:
        return (True, obj[key])
    for v in obj.values():
        if isinstance(v, dict) and key in v:
            return (True, v[key])
    return (False, None)


def _first_scalar(value: Any) -> float | None:
    """Coerce a scalar / [lo, hi] CI / [.., x] to a single float, or None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, (list, tuple)) and value:
        # e.g. a ci95 pair -> use half-width as an uncertainty magnitude
        nums = [x for x in value if isinstance(x, (int, float))]
        if len(nums) >= 2:
            return abs(float(nums[-1]) - float(nums[0])) / 2.0
        if nums:
            return float(nums[0])
    return None


def _central_value(result: dict[str, Any], entry: Entry) -> tuple[str, float]:
    """Pick the figure's central value, driven only by the result JSON.

    Preference order: explicit ``value_key`` -> the key named by
    ``primary_metric`` -> common names.  Never a literal.
    """
    candidates: list[str] = []
    if entry.value_key:
        candidates.append(entry.value_key)
    pm_found, pm = _find_key(result, "primary_metric")
    if pm_found and isinstance(pm, str):
        candidates.append(pm)
    candidates += ["value", "central", "primary_value", "point_estimate", "estimate"]

    for name in candidates:
        found, val = _find_key(result, name)
        scalar = _first_scalar(val) if found else None
        if scalar is not None:
            return (name, scalar)

    raise FigureRegistryError(
        f"{entry.id}: could not locate a central value in result "
        f"{entry.result!r}; set 'value_key' in the registry entry "
        f"(tried {candidates})"
    )


def _load_table(path: Path):
    """Load a source table (.csv or .parquet) into a DataFrame, or None."""
    import pandas as pd

    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in (".parquet", ".pq"):
        return pd.read_parquet(path)
    return None


# ---------------------------------------------------------------------------
# figure emitters (numbers ONLY from result JSON / source table)
# ---------------------------------------------------------------------------


def _emit_quantitative_figure(
    entry: Entry,
    result: dict[str, Any],
    unc: float,
    out_dir: Path,
) -> tuple[Path, Path]:
    import pandas as pd

    value_name, value = _central_value(result, entry)

    # If a source table is present with plottable columns, drive the figure from
    # it; otherwise render the single point estimate +/- uncertainty.
    table_df = None
    if entry.table:
        tpath = Path(entry.table)
        if tpath.exists():
            table_df = _load_table(tpath)

    fig, ax = plt.subplots(figsize=(6.0, 4.0), dpi=150)

    source_rows: list[dict[str, Any]] = []
    plotted_from_table = False
    if table_df is not None:
        # look for x / y (+ optional yerr) style columns
        def _col(*names):
            for n in names:
                for c in table_df.columns:
                    if c.lower() == n:
                        return c
            return None

        ycol = _col("y", "value", "sigma68_ns", "residual", "mean")
        xcol = _col("x", "stave", "label", "bin", "index")
        yerr = _col("yerr", "uncertainty", "sigma", "err", "ci95_halfwidth")
        if ycol is not None:
            y = pd.to_numeric(table_df[ycol], errors="coerce")
            if xcol is not None:
                x_labels = table_df[xcol].astype(str).tolist()
                x = range(len(y))
                ax.errorbar(
                    list(x),
                    y.tolist(),
                    yerr=(pd.to_numeric(table_df[yerr], errors="coerce").tolist()
                          if yerr else None),
                    fmt="o",
                    color="#2a78d6",
                    ecolor="#595959",
                    capsize=3,
                )
                ax.set_xticks(list(x))
                ax.set_xticklabels(x_labels, rotation=0)
            else:
                x = range(len(y))
                ax.errorbar(
                    list(x),
                    y.tolist(),
                    yerr=(pd.to_numeric(table_df[yerr], errors="coerce").tolist()
                          if yerr else None),
                    fmt="o",
                    color="#2a78d6",
                    ecolor="#595959",
                    capsize=3,
                )
            for i in range(len(y)):
                source_rows.append(
                    {
                        "series": "table",
                        "x": (table_df[xcol].iloc[i] if xcol else i),
                        "y": float(y.iloc[i]) if pd.notna(y.iloc[i]) else None,
                    }
                )
            plotted_from_table = True

    if not plotted_from_table:
        ax.errorbar(
            [0],
            [value],
            yerr=[unc],
            fmt="o",
            color="#2a78d6",
            ecolor="#595959",
            capsize=4,
            markersize=8,
        )
        ax.set_xlim(-0.5, 0.5)
        ax.set_xticks([0])
        ax.set_xticklabels([entry.id])
        ax.annotate(
            f"{value:.4g} ± {unc:.4g}",
            xy=(0, value),
            xytext=(6, 6),
            textcoords="offset points",
            fontsize=9,
            color="#1a1a1a",
        )

    status_tag = f"[{entry.status}]"
    ax.set_title(f"{entry.id} {status_tag}", fontsize=11, fontweight="bold")
    ax.set_ylabel(value_name)
    ax.grid(True, color="#e8e8e8", linewidth=0.5)
    fig.text(
        0.5,
        0.005,
        entry.caption,
        ha="center",
        va="bottom",
        fontsize=7,
        color="#595959",
        wrap=True,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))

    fig_path = out_dir / f"{entry.id}.png"
    fig.savefig(fig_path)
    plt.close(fig)

    # per-figure source data (records the exact numbers used, + provenance)
    src_path = out_dir / f"{entry.id}_source_data.csv"
    prov = {
        "figure_id": entry.id,
        "status": entry.status,
        "kind": entry.kind,
        "value_name": value_name,
        "central_value": value,
        "uncertainty_key": entry.uncertainty_key,
        "uncertainty": unc,
        "result_path": entry.result,
        "table_path": entry.table or "",
        "input_sha256": entry.input_sha256 or "",
    }
    if source_rows:
        df = pd.DataFrame(source_rows)
        for k, v in prov.items():
            df[k] = v
    else:
        df = pd.DataFrame([prov])
    df.to_csv(src_path, index=False)

    return fig_path, src_path


def _emit_illustrative_figure(entry: Entry, out_dir: Path) -> tuple[Path, Path]:
    """Emit a clearly-labelled schematic into a SEPARATE directory.

    Illustrative figures carry no measured numbers and are never mixed with the
    quantitative set.
    """
    ill_dir = out_dir / "illustrative"
    ill_dir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(6.0, 4.0), dpi=150)
    ax.axis("off")
    ax.add_patch(
        plt.Rectangle((0.05, 0.05), 0.9, 0.9, fill=False, edgecolor="#a0a0a0",
                      linewidth=1.2, linestyle="--")
    )
    ax.text(
        0.5,
        0.6,
        "SCHEMATIC",
        ha="center",
        va="center",
        fontsize=22,
        fontweight="bold",
        color="#a0a0a0",
    )
    ax.text(
        0.5,
        0.42,
        "Illustrative only — not quantitative evidence",
        ha="center",
        va="center",
        fontsize=9,
        color="#595959",
    )
    ax.set_title(f"{entry.id} [ILLUSTRATIVE]", fontsize=11, fontweight="bold")
    fig.text(0.5, 0.02, entry.caption, ha="center", fontsize=7, color="#595959",
             wrap=True)
    fig_path = ill_dir / f"{entry.id}.png"
    fig.savefig(fig_path)
    plt.close(fig)

    import pandas as pd

    src_path = ill_dir / f"{entry.id}_source_data.csv"
    pd.DataFrame(
        [
            {
                "figure_id": entry.id,
                "kind": "illustrative",
                "status": entry.status,
                "note": "schematic; no measured data",
                "caption": entry.caption,
            }
        ]
    ).to_csv(src_path, index=False)
    return fig_path, src_path


# ---------------------------------------------------------------------------
# per-entry disposition
# ---------------------------------------------------------------------------


def _process_entry(
    entry: Entry, out_dir: Path, paper_only: bool, allow_preliminary: bool
) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "id": entry.id,
        "status": entry.status,
        "kind": entry.kind,
        "disposition": None,
        "reason": "",
        "figure": None,
        "source_data": None,
        "quantitative": entry.is_quantitative,
    }

    # Blocked: legitimately absent upstream result.
    if entry.status == "EXTERNAL_BLOCKER":
        present = Path(entry.result).exists() if entry.result else False
        rec["disposition"] = "BLOCKED"
        rec["reason"] = (
            "EXTERNAL_BLOCKER: upstream result not yet available"
            + ("" if not present else " (result file present but entry marked blocked)")
        )
        return rec

    # Illustrative schematic -> separate directory, always allowed, never quantitative.
    if entry.status == "ILLUSTRATIVE":
        fig_path, src_path = _emit_illustrative_figure(entry, out_dir)
        rec["disposition"] = "PASS"
        rec["reason"] = "illustrative schematic (kept separate)"
        rec["figure"] = str(fig_path)
        rec["source_data"] = str(src_path)
        return rec

    # PRELIMINARY excluded from a paper build unless explicitly allowed.
    if entry.status == "PRELIMINARY" and paper_only and not allow_preliminary:
        rec["disposition"] = "BLOCKED"
        rec["reason"] = (
            "PRELIMINARY excluded from paper build (pass --allow-preliminary "
            "to include)"
        )
        return rec

    # Paper-permitted quantitative build (VALIDATED / TENSION / allowed PRELIMINARY).
    if entry.status in _PAPER_QUANTITATIVE_STATUSES:
        result_path = Path(entry.result)
        if not result_path.exists():
            raise FigureRegistryError(
                f"{entry.id}: result file not found: {entry.result}"
            )
        try:
            with open(result_path, encoding="utf-8") as fh:
                result = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            raise FigureRegistryError(
                f"{entry.id}: could not read result JSON {entry.result}: {exc}"
            ) from exc

        # Uncertainty must be present and non-null for quantitative entries.
        if entry.is_quantitative:
            found, unc_val = _find_key(result, entry.uncertainty_key)
            if not found or unc_val is None:
                raise FigureRegistryError(
                    f"{entry.id}: uncertainty key {entry.uncertainty_key!r} "
                    f"missing or null in result {entry.result}"
                )
            unc = _first_scalar(unc_val)
            if unc is None:
                raise FigureRegistryError(
                    f"{entry.id}: uncertainty {entry.uncertainty_key!r}="
                    f"{unc_val!r} is not numeric in result {entry.result}"
                )
        else:
            unc = 0.0

        # sha256 gate on the source table.
        if entry.input_sha256:
            if not entry.table:
                raise FigureRegistryError(
                    f"{entry.id}: input_sha256 recorded but no table to hash"
                )
            tpath = Path(entry.table)
            if not tpath.exists():
                raise FigureRegistryError(
                    f"{entry.id}: table not found for sha256 check: {entry.table}"
                )
            actual = sha256_file(tpath)
            if actual != entry.input_sha256:
                raise FigureRegistryError(
                    f"{entry.id}: source-table sha256 mismatch for {entry.table}\n"
                    f"  recorded: {entry.input_sha256}\n"
                    f"  actual:   {actual}"
                )

        fig_path, src_path = _emit_quantitative_figure(entry, result, unc, out_dir)
        rec["disposition"] = "PASS"
        rec["reason"] = f"built from {entry.result}"
        if entry.status == "TENSION":
            rec["reason"] += " (status=TENSION; see caption)"
        rec["figure"] = str(fig_path)
        rec["source_data"] = str(src_path)
        return rec

    # Should be unreachable: validate_registry rejects unknown statuses first.
    raise FigureRegistryError(
        f"{entry.id}: status {entry.status!r} is not buildable for the paper"
    )


# ---------------------------------------------------------------------------
# public build
# ---------------------------------------------------------------------------


def build(
    registry_path: str | Path,
    out_dir: str | Path,
    paper_only: bool = True,
    allow_preliminary: bool = False,
) -> dict[str, Any]:
    """Build all figures in ``registry_path`` into ``out_dir``.

    Returns the build report dict (also written to
    ``out_dir/build_report.json``).  Raises :class:`FigureRegistryError` on any
    hard failure -- after writing whatever report is available.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    entries = load_registry(registry_path)
    problems = validate_registry(entries)

    report: dict[str, Any] = {
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "registry": str(registry_path),
        "paper_only": paper_only,
        "allow_preliminary": allow_preliminary,
        "validation_problems": problems,
        "entries": [],
        "summary": {},
    }

    if problems:
        report["summary"] = {"status": "INVALID_REGISTRY", "n_problems": len(problems)}
        _write_report(out_dir, report)
        raise FigureRegistryError(
            "registry failed validation:\n  - " + "\n  - ".join(problems)
        )

    failures: list[str] = []
    for entry in entries:
        try:
            rec = _process_entry(entry, out_dir, paper_only, allow_preliminary)
        except FigureRegistryError as exc:
            rec = {
                "id": entry.id,
                "status": entry.status,
                "kind": entry.kind,
                "disposition": "FAIL",
                "reason": str(exc),
                "figure": None,
                "source_data": None,
                "quantitative": entry.is_quantitative,
            }
            failures.append(str(exc))
        report["entries"].append(rec)

    counts: dict[str, int] = {"PASS": 0, "FAIL": 0, "BLOCKED": 0}
    quant_pass = 0
    illus_pass = 0
    for rec in report["entries"]:
        counts[rec["disposition"]] = counts.get(rec["disposition"], 0) + 1
        if rec["disposition"] == "PASS":
            if rec["kind"] == "illustrative":
                illus_pass += 1
            elif rec["quantitative"]:
                quant_pass += 1
    report["summary"] = {
        "n_entries": len(entries),
        "pass": counts.get("PASS", 0),
        "fail": counts.get("FAIL", 0),
        "blocked": counts.get("BLOCKED", 0),
        "quantitative_figures": quant_pass,
        "illustrative_figures": illus_pass,
    }

    _write_report(out_dir, report)

    if failures:
        raise FigureRegistryError(
            f"{len(failures)} figure(s) failed to build:\n  - "
            + "\n  - ".join(failures)
        )
    return report


def _write_report(out_dir: Path, report: dict[str, Any]) -> None:
    with open(out_dir / "build_report.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m tools.figure_registry.builder",
        description=(
            "Build validated CCB test-beam paper figures from a result "
            "registry. Every quantitative figure is driven only by values "
            "read from a result JSON / source table -- never a hand-entered "
            "constant. Fails (nonzero exit) on a missing result, a missing "
            "uncertainty, a source-table sha256 mismatch, or a status outside "
            "the allowed set."
        ),
    )
    p.add_argument("--registry", required=True, help="path to the YAML registry")
    p.add_argument("--out", required=True, help="output directory for figures")
    p.add_argument(
        "--allow-preliminary",
        action="store_true",
        help="include PRELIMINARY figures in the paper build (default: blocked)",
    )
    return p


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
    s = report["summary"]
    print(
        f"OK: {s['pass']} built "
        f"({s['quantitative_figures']} quantitative, "
        f"{s['illustrative_figures']} illustrative), "
        f"{s['blocked']} blocked, {s['fail']} failed. "
        f"Report: {Path(args.out) / 'build_report.json'}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
