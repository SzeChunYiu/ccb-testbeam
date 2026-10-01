# Issue 2470: Raw ROOT Path Probe

## Scope

Issue `#2470` requested a portable raw ROOT path convention after the S47b
follow-up found that the worker-visible files live under
`/home/billy/ccb-data/data/extracted/root/root`, while older scripts and reports
often cite `/home/billy/ccb-data/extracted/root/root`.

This change adds a reusable resolver in `ccb_mc_validation.raw_root_paths` and a
CLI probe:

```bash
uv run python -m ccb_mc_validation raw-root-probe --repo-root .
```

## Resolution Rule

The resolver checks candidates in this order:

| Priority | Candidate | Role |
|---:|---|---|
| 1 | `CCB_RAW_ROOT_DIR` | explicit operator override |
| 2 | `/home/billy/ccb-data/data/extracted/root/root` | canonical worker-visible mount |
| 3 | `data/extracted/root/root` | repo-relative alias |
| 4 | `/home/billy/ccb-data/extracted/root/root` | legacy absolute alias |

A candidate is usable only when it is a directory and contains at least one
B-stack `hrdb_run_*.root` file. The canonical worker mount is intentionally
checked before repo-relative aliases so stale symlinks cannot silently override
the fleet-wide path.

## Probe Evidence

The probe run on this worker resolved:

| Field | Value |
|---|---|
| resolved path | `/home/billy/ccb-data/data/extracted/root/root` |
| source | `canonical-worker-mount` |
| A-stack ROOT files | 57 |
| B-stack ROOT files | 53 |
| total ROOT files | 110 |

Machine-readable evidence is stored in `raw_root_probe.json`.

## Documentation Changes

`DATA.md` now names the worker-visible canonical mount, the repo-local alias,
and the legacy path. `docs/02_data_and_runs.md` points new raw-ROOT consumers to
the probe command instead of encouraging hard-coded absolute paths.

## Verification

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src pytest -q tests/test_raw_root_paths.py
```

Result: `4 passed`.

```bash
uv run python -m ccb_mc_validation raw-root-probe --repo-root . \
  --output reports/2470__raw_root_path_probe/raw_root_probe.json
```

Result: resolved `/home/billy/ccb-data/data/extracted/root/root` with 57 A-stack
and 53 B-stack ROOT files.

## Ticket Lifecycle Note

The required single `tn-ticket claim testbeam-laptop-1 --project testbeam`
invocation returned `# null`/`null` with exit code 0 and did not attach
`worker:testbeam-laptop-1` to any issue. The underlying GitHub query showed
`#2470` as the oldest open `project:testbeam` issue, so the same label swap was
applied manually to exactly that issue. No second `tn-ticket claim` invocation
was run.
