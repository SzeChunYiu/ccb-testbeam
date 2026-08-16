#!/usr/bin/env python3
"""Fail-closed exact key-set closure audit for event-domain comparisons.

This complements ``validate_event_keys.py``.  The latter proves join cardinality;
this tool proves that two declared event domains contain exactly the same unique,
non-null composite keys.  It never coerces key dtypes silently.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

import pandas as pd


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".csv", ".gz"} or path.name.endswith(".csv.gz"):
        return pd.read_csv(path)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    raise ValueError(f"unsupported table format: {path}")


def _dtype_signature(df: pd.DataFrame, keys: list[str]) -> dict[str, str]:
    return {key: str(df[key].dtype) for key in keys}


def audit_key_set_closure(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    keys: list[str],
    require_matching_dtypes: bool = True,
    example_limit: int = 20,
) -> dict:
    if not keys:
        raise ValueError("at least one key is required")

    for name, df in (("left", left), ("right", right)):
        missing = [key for key in keys if key not in df.columns]
        if missing:
            raise ValueError(f"{name} missing key columns: {missing}")

    left_null = int(left[keys].isna().any(axis=1).sum())
    right_null = int(right[keys].isna().any(axis=1).sum())
    left_dup = int(left.duplicated(keys, keep=False).sum())
    right_dup = int(right.duplicated(keys, keep=False).sum())

    left_dtypes = _dtype_signature(left, keys)
    right_dtypes = _dtype_signature(right, keys)
    dtype_match = left_dtypes == right_dtypes

    # Do not silently coerce.  If exact dtype matching is required and does not
    # hold, no key-domain comparison is authorised.
    if require_matching_dtypes and not dtype_match:
        return {
            "keys": keys,
            "left_rows": int(len(left)),
            "right_rows": int(len(right)),
            "left_null_key_rows": left_null,
            "right_null_key_rows": right_null,
            "left_duplicate_key_rows": left_dup,
            "right_duplicate_key_rows": right_dup,
            "left_key_dtypes": left_dtypes,
            "right_key_dtypes": right_dtypes,
            "key_dtypes_match": False,
            "matched_unique_keys": None,
            "left_only_unique_keys": None,
            "right_only_unique_keys": None,
            "left_only_examples": [],
            "right_only_examples": [],
            "exact_key_set": False,
            "status": "KEY_DTYPE_MISMATCH",
        }

    lkeys = left[keys].drop_duplicates()
    rkeys = right[keys].drop_duplicates()
    merged = lkeys.merge(rkeys, on=keys, how="outer", indicator=True, validate="one_to_one")
    left_only = merged[merged["_merge"] == "left_only"][keys]
    right_only = merged[merged["_merge"] == "right_only"][keys]
    matched = int((merged["_merge"] == "both").sum())

    exact = (
        left_null == 0
        and right_null == 0
        and left_dup == 0
        and right_dup == 0
        and (dtype_match or not require_matching_dtypes)
        and len(left_only) == 0
        and len(right_only) == 0
    )
    status = "PASS" if exact else "FAIL"
    return {
        "keys": keys,
        "left_rows": int(len(left)),
        "right_rows": int(len(right)),
        "left_unique_keys": int(len(lkeys)),
        "right_unique_keys": int(len(rkeys)),
        "left_null_key_rows": left_null,
        "right_null_key_rows": right_null,
        "left_duplicate_key_rows": left_dup,
        "right_duplicate_key_rows": right_dup,
        "left_key_dtypes": left_dtypes,
        "right_key_dtypes": right_dtypes,
        "key_dtypes_match": dtype_match,
        "matched_unique_keys": matched,
        "left_only_unique_keys": int(len(left_only)),
        "right_only_unique_keys": int(len(right_only)),
        "left_only_examples": left_only.head(example_limit).to_dict(orient="records"),
        "right_only_examples": right_only.head(example_limit).to_dict(orient="records"),
        "exact_key_set": bool(exact),
        "status": status,
    }


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("left", type=Path)
    ap.add_argument("right", type=Path)
    ap.add_argument("--keys", nargs="+", default=["run", "evt"])
    ap.add_argument("--allow-dtype-mismatch", action="store_true")
    ap.add_argument("--example-limit", type=int, default=20)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(list(argv) if argv is not None else None)

    for label, path in (("left", args.left), ("right", args.right)):
        if not path.is_file():
            raise SystemExit(f"{label} table does not exist: {path}")

    try:
        result = audit_key_set_closure(
            load_table(args.left),
            load_table(args.right),
            keys=list(args.keys),
            require_matching_dtypes=not args.allow_dtype_mismatch,
            example_limit=args.example_limit,
        )
    except (ValueError, KeyError) as exc:
        raise SystemExit(str(exc)) from exc

    result["left_input"] = {
        "path": str(args.left),
        "bytes": args.left.stat().st_size,
        "sha256": sha256_file(args.left),
    }
    result["right_input"] = {
        "path": str(args.right),
        "bytes": args.right.stat().st_size,
        "sha256": sha256_file(args.right),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["exact_key_set"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
