#!/usr/bin/env bash
set -euo pipefail

report_dir="reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest"
manifest_backup="$(mktemp "$report_dir/manifest.full.XXXXXX")"
cp "$report_dir/manifest.json" "$manifest_backup"

python scripts/01_build_pulse_table_from_root.py \
  --config "$report_dir/s01b_s00_reproduction_local.yaml"

mv "$report_dir/manifest.json" "$report_dir/s00_generator_manifest.json"
mv "$manifest_backup" "$report_dir/manifest.json"
