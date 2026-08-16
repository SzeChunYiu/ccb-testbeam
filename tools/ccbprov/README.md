# ccbprov — provenance & reproducibility toolkit

Pure-Python helpers that make every CCB test-beam run reproducible: content
hashing, a run-manifest builder, a closure-matrix ledger, schema validation,
and report-directory scaffolding. Records conform to the JSON schemas in
`schemas/` (`run_manifest`, `plot_record`, `closure_record`).

## Modules

| Module        | What it gives you |
|---------------|-------------------|
| `hashing`     | `sha256_file(path)`, `file_record(path)` → `{path, sha256, size_bytes}` |
| `manifest`    | `RunManifest` builder (auto git-commit, environment capture, UTC timing) |
| `closure`     | `ClosureRow`, `write_closure_matrix(rows, csv, json)` |
| `validate`    | `validate_record(record, schema_path)` → list of errors (uses `jsonschema` if present, else a built-in fallback) |
| `report`      | `init_report_dir(base, task_slug)` → scaffolds the report dir |

## Quick start: build, write, and validate a manifest

```python
from tools.ccbprov import RunManifest, validate_record

# git_commit auto-detects via `git rev-parse HEAD`; pass an explicit
# 40-hex string to override on a machine without git.
m = RunManifest(
    task_id="TK-DEMO",
    command=["python", "analysis/decode.py", "--run", "42"],
    seed_policy="numpy default_rng(1234)",
)
m.start()
m.add_input("data/raw/run42.root")     # -> {path, sha256, size_bytes}
m.add_config("configs/decode.yaml")
# ... do the work, produce outputs ...
m.add_output("out/run42_hits.parquet")
m.finish()

m.write("out/manifest.json")

errors = validate_record(m.to_dict(), "schemas/run_manifest.schema.json")
assert not errors, errors
```

## Closure matrix

```python
from tools.ccbprov import ClosureRow, write_closure_matrix

rows = [
    ClosureRow(
        task_id="TK-DEMO",
        status="DONE",                 # from CLOSURE_STATUSES enum
        dependencies=["TK-INGEST"],
        evidence=["out/manifest.json", "out/run42_hits.parquet"],
        acceptance=[
            {"criterion": "hit multiplicity matches MC truth within 2%",
             "passed": True, "evidence": "figures/mult.png"},
        ],
        notes="baseline decode",
    ),
]
write_closure_matrix(rows, "reports/closure_matrix.csv", "reports/closure_matrix.json")
```

`write_closure_matrix` writes a flat CSV
(`task_id,status,issue,dependencies,evidence,notes,n_acceptance,n_passed`)
and a JSON array of full closure records. An invalid `status` raises
`ValueError` before anything is written.

## Report directory

```python
from tools.ccbprov import init_report_dir

d = init_report_dir("reports", task_slug="project-completion")
# -> reports/project_completion_<YYYYMMDDTHHMMSSZ>/
#    { REPORT.md, closure_matrix.csv, manifest.json, commands.log, figures/ }
```

Existing directories are never overwritten (a numeric suffix is appended).
