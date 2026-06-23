# ADR-0001: MC Validation Architecture

**Status:** accepted  
**Date:** 2026-06-23  
**Context:** CCB HiBeam testbeam analysis (`ccb-testbeam`)

## Decision

Implement the Monte Carlo validation program as an installable Python package
(`ccb-mc-validation`) with a strict configuration layer, shared schema records,
and a single CLI entry point (`ccb-mc-validation`) that orchestrates MV0–MV9
study lines defined in `studies/MC_VALIDATION_PROGRAM.md`.

## Problem

The project completed ~230 data-driven studies without Monte Carlo truth.
Krakow GEANT4 simulation (`hibeam_g4`) now provides labeled truth in ROOT, but
data analysis operates on 18-sample ADC waveforms. Research directions split
into:

- **Tier-1 (truth-direct):** PID, energy/range, stopping depth — compare MC
  truth branches directly to data-driven inferences.
- **Tier-2 (digitizer-dependent):** timing, pile-up, pulse shape, pedestal,
  saturation — require MV0 truth→waveform digitizer before validation.

Ad-hoc scripts cannot enforce shared contracts (units, splits, manifests) across
many MV studies and LUNARC jobs.

## Architecture

```text
configs/mc_validation/base.yaml
        │
        ▼
  load_config() ──► ResolvedConfig (+ SHA256, env expansion)
        │
        ├── audit ─────────────► docs/mc_validation/REPOSITORY_AUDIT.md
        ├── truth-build ───────► MC schema fingerprint + manifest
        ├── mv1 / mv2 / mv3 ───► Tier-1 prerequisite validation
        ├── mv0-digitize ──────► digitizer parameter scaffold
        ├── mv4..mv8 ──────────► blocked until MV0 (StudyBlockedError)
        └── synthesize ────────► MV9 synthesis scaffold
```

### Package modules

| Module | Responsibility |
| --- | --- |
| `config` | YAML loading, unknown-key rejection, `${ENV}` expansion, resolved snapshots |
| `schemas` | Frozen dataclasses for branches, metrics, manifests, study status |
| `units` | Energy/time unit validation and MeV↔ADC conversion |
| `exceptions` | Typed errors mapped to exit codes 0–10 |
| `cli` | Subcommand router and Phase A–B orchestration |

### Configuration contract

- `schema_version` gates breaking changes.
- Relative paths resolve from `paths.repo_root`.
- Resolved configs are written under `reports/mc_validation/resolved_configs/`
  with content SHA256 for provenance replay.

### Truth schema

The `hibeam` tree must expose arm (`LayerID1`), depth (`LayerID`), `PDG`,
`EDep` (MeV), and `time` (ns). `truth-build` verifies presence via uproot
(optional extra `[root]`).

## Consequences

**Positive**

- One installable tool for local smoke tests and LUNARC job wrappers.
- Strict config catches typos before expensive MC/stat runs.
- Tier-2 studies fail fast with `StudyBlockedError` instead of silent no-ops.

**Negative**

- Tier-1 commands in Phase A–B validate prerequisites and write scaffolds;
  full physics plots remain in per-study `scripts/mv*_*.py` (Phase C+).
- uproot is optional; truth-build requires the `[root]` extra.

## Alternatives considered

1. **Flat scripts only** — rejected; no shared manifest or exit-code discipline.
2. **Monolithic notebook driver** — rejected; poor CI/LUNARC integration.
3. **Immediate Tier-2 stubs returning fake metrics** — rejected; blocked stubs
   with explicit errors preferred over misleading green checks.

## Follow-ups

- Phase C: MV0 digitizer calibration against `s00_selected_b_pulses.csv.gz`.
- Phase D: MV4–MV8 command bodies wired to digitized pulse tables.
- Phase E: MV9 updates `reports/SUMMARY.md` MC verdict column.
