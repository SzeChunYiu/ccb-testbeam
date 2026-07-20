# CCB test-beam scientific audit harness (`tools/audit`)

Read-only, deterministic auditors that surface **publication-blocking scientific
integrity risks** as *candidates for human triage*. Nothing here mutates the repo,
the data, or the physics. Every finding is a lead to investigate, not a verdict.

**Severity model**
- **P0** — publication-blocking. A wrong physics number can result if unresolved.
  Static/CLI tools **exit nonzero** when a P0 is present (so they gate CI).
- **P1 / P2** — portability, hygiene, disclosure. Worth fixing; never gates.

The `run_repo_audit.py` wrapper is the exception: it is an **inventory**, so it
always exits 0 and merely prints the P0 count.

---

## Tools

### `audit_repository.py` — repo-wide static auditor
Walks a `--repo` root (skipping `.git`, `.venv`, `__pycache__`, plus any
`--exclude REL_DIR`), parsing every `.py` (AST + regex), `REPORT.md`, `.json`,
and `docs/claim_ledger.csv`. Emits `findings.csv`, `inventory.csv`,
`summary.json`, `REPORT.md`. Codes:

| Code | Sev | What it means |
|------|-----|---------------|
| `AMPLITUDE_SCHEMA_DOUBLE_SUBTRACTION` | P0 | `amplitude_adc` and `baseline_adc` subtracted — verify the pulse contract isn't double-subtracting the baseline. |
| `EVENTNO_ONLY_JOIN` | P0 | An event-level `.merge/.join` keys on `eventno` without `run` — cross-run event collisions fan out rows. |
| `MC_WEIGHT_NOT_DECLARED` | P0 | An MC truth reader (uproot) declares no `PrimaryWeight` and no explicit unweighted justification. |
| `INDEX_PARITY_SPLIT` | P0 | An `index % 2` / `legacy_parity` train/test split can leak correlated rows/events. |
| `VALIDATED_WITH_BLOCKING_UNCERTAINTY` | P0 | A `REPORT.md` claims "validated" while uncertainty is missing/blocking. |
| `CLAIM_VALIDATED_CI_MISSING` | P0 | A claim-ledger row is VALIDATED but its CI/uncertainty cell is `CI_MISSING`. |
| `CLAIM_SOURCE_MISSING` | P0 | A claim-ledger `source_*` path does not exist on disk (broken provenance). |
| `UNSEEDED_RANDOMNESS` | P1 | `np.random.choice`/`.sample(` with no `default_rng`/`seed`/`random_state`. |
| `ABSOLUTE_PATH`, `ABSOLUTE_PATH_JSON` | P1 | Committed `/home`,`/projects`,`/scratch`,`/tmp` path hurts portability. |
| `UNUSED_ARGUMENT` | P1 | An argparse `--flag` is declared but referenced only once. |
| `REPORT_SECTION_MISSING` | P1 | `REPORT.md` lacks a reproduction/method/result/provenance section. |
| `DUPLICATE_STUDY_ID` | P1 | The same study id is claimed by >1 report. |
| `READ_ERROR`,`JSON_INVALID`,`PYTHON_SYNTAX_ERROR` | P1 | File could not be parsed. |
| `AUTO_GENERATED_DISCLOSURE` | P2 | An auto-generated report needs independent scientific review. |

```bash
python tools/audit/audit_repository.py --repo . --out reports/audit --exclude tools/audit
```

### `run_repo_audit.py` — inventory wrapper (never gates)
Runs `audit_repository.collect` over `--root` (default: repo root), excluding
`.git`, **`tools/audit` itself**, and vendored/cache dirs. Writes `findings.csv`,
`findings.json`, and `summary.json` (counts by severity **and** code). Always
exits 0; prints the P0 count.

```bash
python tools/audit/run_repo_audit.py --root . --out reports/reaudit_20260720/audit_harness
```

### `validate_event_keys.py` — join-cardinality proof
Attempts a strict `one_to_one` inner merge of two tables on a composite key
(default `run evt`). Exits 1 if the join fans out (duplicate composite keys).

```bash
python tools/audit/validate_event_keys.py left.parquet right.parquet --keys run evt --out ek.json
```

### `validate_pulse_schema.py` — selected-pulse schema check
Validates a pulse table against `REQUIRED=[run, evt, stave, baseline_adc]`.
Flags P0 `MISSING_REQUIRED_COLUMNS`, `AMBIGUOUS_AMPLITUDE_ADC` (bare
`amplitude_adc` with no `peak_height_adc`/`peak_code_adc`), `DUPLICATE_PULSE_KEY`.

```bash
python tools/audit/validate_pulse_schema.py pulses.parquet --schema-version v1 --out ps.json
```

### `audit_mc_weight_usage.py` — MC weight / ESS check
Opens a ROOT `--tree` (default `hibeam`), looks for `PrimaryWeight`/`weight`/
`EventWeight`. No weight branch → P0 `P0_NO_WEIGHT_BRANCH` (exit 1). Otherwise
reports effective sample size `ESS = (Σw)² / Σw²`.

```bash
python tools/audit/audit_mc_weight_usage.py truth.root --tree hibeam --out mc.json
```

---

## Reading the findings

1. Every P0 is a **candidate**, not a proven defect — open the cited
   `path:line` and confirm. E.g. `EVENTNO_ONLY_JOIN` is only a real bug if the
   two sides span multiple runs; a single-run merge is benign.
2. Triage P0 codes by physics impact first: `AMPLITUDE_SCHEMA_DOUBLE_SUBTRACTION`,
   `EVENTNO_ONLY_JOIN`, `MC_WEIGHT_NOT_DECLARED`, `INDEX_PARITY_SPLIT` change
   numbers; `CLAIM_SOURCE_MISSING` breaks provenance.
3. `findings.csv`/`findings.json` list every hit; `summary.json` has the
   severity/code histogram for prioritisation.
4. **Finding paths are absolute** (faithful to the walk); `inventory.csv` paths
   are repo-relative with SHA-256 for provenance pinning.

## Tests

```bash
python -m pytest tests/test_audit_tools.py -q
```
