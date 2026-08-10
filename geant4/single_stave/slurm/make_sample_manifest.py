#!/usr/bin/env python3
"""Assemble a per-file sha256 + provenance manifest for a regenerated sample dir.

For each ``*.root`` in <sample_dir> it records: the output filename, byte size,
sha256, and the full provenance parsed from the sibling ``*.root.meta.json``
(auto-written by RunAction: seed, particle, energy, scales, birks, sipm_n_cells,
geometry_hash, optical-table hashes, git_commit). Emits:

  manifest.json   list of per-file records (full metadata)
  manifest.csv    one row per file with the key provenance fields

Pure stdlib, no network. Intended to run on LUNARC after regen_sample.sh.

Usage:
    python3 make_sample_manifest.py <sample_dir>
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import os
import sys
from pathlib import Path


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("sample_dir", type=Path, help="directory of *.root + *.meta.json")
    args = p.parse_args(argv)

    if not args.sample_dir.is_dir():
        sys.exit(f"not a directory: {args.sample_dir}")

    roots = sorted(glob.glob(str(args.sample_dir / "*.root")))
    if not roots:
        sys.exit(f"no .root files in {args.sample_dir}")

    records = []
    for r in sorted(roots):
        rpath = Path(r)
        meta_path = Path(str(rpath) + ".meta.json")
        meta = {}
        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text())
            except Exception as exc:  # noqa: BLE001
                meta = {"_meta_read_error": str(exc)}
        else:
            meta = {"_meta_read_error": "missing sidecar"}
        rec = {
            "file": rpath.name,
            "path": str(rpath),
            "size_bytes": rpath.stat().st_size,
            "sha256": sha256_of(rpath),
            "meta": meta,
        }
        records.append(rec)
        print(f"  {rpath.name}  sha256={rec['sha256'][:12]}...  "
              f"{rec['size_bytes']} B  part={meta.get('particle')} "
              f"E={meta.get('kinetic_energy_MeV')} seed={meta.get('seed')}")

    out_json = args.sample_dir / "manifest.json"
    out_csv = args.sample_dir / "manifest.csv"
    out_json.write_text(json.dumps(records, indent=2))

    # Compact CSV of the key provenance fields.
    cols = ["file", "sha256", "size_bytes", "particle", "kinetic_energy_MeV",
            "hit_x_cm", "seed", "n_events", "mode", "birks_kB_mm_per_MeV",
            "reflectivity_scale", "attenuation_scale",
            "scintillator_absorption_scale", "y11_bulk_attenuation_scale",
            "pde_scale",
            "coupling_efficiency", "collection_efficiency",
            "optical_interface_model", "sipm_n_cells", "geometry_hash", "git_commit"]
    with out_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for rec in records:
            m = rec["meta"]
            w.writerow([
                rec["file"], rec["sha256"], rec["size_bytes"],
                m.get("particle"), m.get("kinetic_energy_MeV"),
                m.get("hit_x_cm") or m.get("hit_x_cm"),
                m.get("seed"), m.get("n_events"), m.get("mode"),
                m.get("birks_kB_mm_per_MeV"), m.get("reflectivity_scale"),
                m.get("attenuation_scale"), m.get("scintillator_absorption_scale"),
                m.get("y11_bulk_attenuation_scale"), m.get("pde_scale"),
                m.get("coupling_efficiency"), m.get("collection_efficiency"),
                m.get("optical_interface_model"), m.get("sipm_n_cells"),
                m.get("geometry_hash"), m.get("git_commit"),
            ])

    print(f"\nwrote {out_json}")
    print(f"wrote {out_csv}")
    print(f"manifested {len(records)} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
