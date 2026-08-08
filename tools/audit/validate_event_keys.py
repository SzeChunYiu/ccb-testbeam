#!/usr/bin/env python3
"""Prove event-key uniqueness and safe join cardinality before physics merging.

Given two tables (parquet or csv), attempt a strict ``one_to_one`` inner merge on
a composite key (default ``run evt``).  Exits nonzero (P0) if the join is not
one-to-one, i.e. duplicate composite keys exist on either side and rows would fan
out.

v2 changes:
  - ``--require-key-set-equality`` adds an exact key-set equality gate.
  - Key-set mode reports left-only / right-only keys, counts, and examples.
  - Input hashes recorded in the output JSON.
  - ``--key-domain`` reports the shared key count and left/right excess.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(p: Path):
    return pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p)


def _sha_examples(series: pd.Series, n: int = 5) -> list[str]:
    return [str(v) for v in series.head(n).to_list()]


def validate(
    left: Path,
    right: Path,
    keys: list[str],
    require_key_set_equality: bool = False,
) -> dict[str, Any]:
    """Return a result dict."""

    l_df, r_df = load(left), load(right)

    for name, df in [("left", l_df), ("right", r_df)]:
        miss = [k for k in keys if k not in df]
        if miss:
            raise SystemExit(f"{name} missing keys {miss}")

    # ── Duplicate analysis ────────────────────────────────────────────────
    ldup = int(l_df.duplicated(keys, keep=False).sum())
    rdup = int(r_df.duplicated(keys, keep=False).sum())

    # ── Key-set analysis ───────────────────────────────────────────────────
    l_keys = set(l_df[keys].itertuples(index=False, name=None))
    r_keys = set(r_df[keys].itertuples(index=False, name=None))
    left_only = l_keys - r_keys
    right_only = r_keys - l_keys
    shared = l_keys & r_keys
    keys_equal = not left_only and not right_only

    left_only_examples = list(left_only)[:5] if left_only else []
    right_only_examples = list(right_only)[:5] if right_only else []

    # ── Inner join cardinality ─────────────────────────────────────────────
    ok = True
    err = ""
    try:
        m = l_df.merge(
            r_df, on=keys, how="inner", validate="one_to_one",
            suffixes=("_l", "_r"),
        )
    except Exception as e:
        ok = False
        err = str(e)
        m = l_df.merge(r_df, on=keys, how="inner", suffixes=("_l", "_r"))

    # ── Key-set equality gate ──────────────────────────────────────────────
    key_set_pass = not require_key_set_equality or keys_equal
    if require_key_set_equality and not keys_equal:
        if not err:
            err = "key-set equality check failed: left-only / right-only keys exist"
        ok = False

    result: dict[str, Any] = {
        "keys": keys,
        "left_rows": int(len(l_df)),
        "right_rows": int(len(r_df)),
        "left_sha256": _sha256(left),
        "right_sha256": _sha256(right),
        "left_duplicate_rows": ldup,
        "right_duplicate_rows": rdup,
        "joined_rows": int(len(m)),
        "one_to_one": ok,
        "error": err,
        "key_set_analysis": {
            "keys_equal": keys_equal,
            "shared_key_count": len(shared),
            "left_only_count": len(left_only),
            "right_only_count": len(right_only),
            "left_only_examples": left_only_examples,
            "right_only_examples": right_only_examples,
        },
        "require_key_set_equality": require_key_set_equality,
    }
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Prove composite-key one_to_one join cardinality "
        "between two event tables before merging physics."
    )
    ap.add_argument("left", type=Path, help="Left table (.parquet or .csv).")
    ap.add_argument("right", type=Path, help="Right table (.parquet or .csv).")
    ap.add_argument(
        "--keys", nargs="+", default=["run", "evt"],
        help="Composite join key columns (default: run evt).",
    )
    ap.add_argument("--out", type=Path, required=True,
                     help="Output JSON path for the cardinality report.")
    ap.add_argument(
        "--require-key-set-equality", action="store_true",
        help="Also require exact key-set equality (no left-only/right-only keys).",
    )
    args = ap.parse_args(argv)
    for label, p in [("left", args.left), ("right", args.right)]:
        if not p.is_file():
            raise SystemExit(f"{label} table does not exist: {p}")
    res = validate(
        args.left, args.right, list(args.keys),
        require_key_set_equality=args.require_key_set_equality,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(res, indent=2) + "\n")
    print(json.dumps(res, indent=2))
    raise SystemExit(0 if res["one_to_one"] else 1)


if __name__ == "__main__":
    main()