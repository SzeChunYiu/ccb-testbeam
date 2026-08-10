# Latest Handoff

## Session

- **Task ID:** `ARU-S00-PUBLICATION-TRANSACTION-REAUDIT`
- **Stamp:** `2026-08-10T015000Z`
- **Owner:** hourly Atomic Research Universe audit session
- **Initial remote main:** `381c02d814cc85852fab8b8f3f999df269e13780`
- **Branch:** `audit/s00-publication-transaction-reaudit`
- **Primary issue:** #1110, reopened this session
- **Acceptance:** current S00 publication transaction `FLAWED / BLOCKED`; no scientific number changed.

## Why #1110 was reopened

Merged PR #1122 introduced a staging/publication transaction intended to isolate sensitivity runs and protect canonical S00 artifacts. Re-audit of the exact current caller uncovered three deterministic defects that violate the issue's own acceptance criteria.

### 1. Real caller self-deletes staging before publication

`main()` creates:

```python
staging = out_dir.parent / f".{out_dir.name}.staging-{os.getpid()}"
```

`atomic_publish()` creates the same pathname as `tmp`, deletes it if it exists, then tries to rename `staging_dir` to `tmp`. For the actual caller, `staging_dir == tmp`, so completed staging is deleted and the next rename raises `FileNotFoundError`.

Minimal exact-logic reproduction:

```text
staging == atomic tmp: True
outcome: FileNotFoundError: .../.S00_data_integrity_pipeline_reproduction.staging-<pid> -> .../.S00_data_integrity_pipeline_reproduction.staging-<pid>
staging exists after failure: False
target exists after failure: False
```

The merged rollback tests missed this because they pass a source directory literally named `staging`, not the source name produced by `main()`.

### 2. Canonical pulse-table path and manifest path are wrong

Config declares:

```text
reports/S00_data_integrity_pipeline_reproduction
and
data/processed/s00_selected_b_pulses.csv.gz
```

Current code writes the pulse table inside the report staging tree and publishes only that tree. No current successful-path statement publishes it to `data/processed/s00_selected_b_pulses.csv.gz`. `write_manifest()` is passed the pre-publication staging pathname, so a successful tree rename would leave `manifest["selected_pulse_table"]` pointing at a vanished `.staging-<pid>` path. Stdout still prints the configured data path.

`CL-001` currently names the configured data path and report manifest, so claim provenance and producer semantics are inconsistent until repaired.

### 3. Directory replacement is not crash-safe

The commit sequence recursively deletes the old target and only then renames the new candidate into place. A crash during or after deletion can destroy the last authorising generation; concurrent readers can observe partial or absent state. This violates the explicit rollback invariant.

## Preferred repair architecture

Publish immutable model-bound generations and make authority a small atomic pointer update:

```text
staging -> validate/gates -> immutable generation/<model_hash>/
        -> CURRENT.json.tmp -> fsync -> os.replace(..., CURRENT.json)
```

Do not recursively delete the current authoritative generation as part of the commit point. Garbage collection happens after successful pointer publication. If a compatibility copy at `data/processed/s00_selected_b_pulses.csv.gz` is retained, update it separately with atomic file replacement from the authorised immutable generation and record both immutable source and compatibility alias in the manifest.

## Required regression set

- exact `main()` staging-name integration test;
- authorising fixture successfully publishes without self-delete;
- injected failure before/at commit preserves previous generation hashes;
- configured `pulse_table_path` exists after publication and hash-matches staged bytes;
- manifest resolves only stable post-publication paths and contains no `.staging-<pid>`;
- concurrent reader sees only complete old/new generations;
- CL-001 source-data/source-manifest paths revalidate after repair.

## Four review passes

- **Data/reconstruction lead — BLOCK:** successful current transaction is unreachable and configured data destination is not honored.
- **Adversarial reviewer — REJECT closure:** merged tests validate a different source-name contract and omit crash-after-delete/post-publication-path falsifiers.
- **Validation reviewer — BLOCK:** gates do not protect failures in the publication commit itself; transactional fault injection is required.
- **Claims/provenance reviewer — BLOCK:** CL-001 path binding is inconsistent with current producer behavior.

## Repository actions

- Reopened #1110.
- Added detailed ARU re-audit comment to #1110 with concern IDs and acceptance delta.
- Added immutable archive: `chatgpt_todo/archive/2026-08-10T015000Z_ARU-S00-PUBLICATION-TRANSACTION-REAUDIT.md`.
- Updated `ACTIVE_TASK.md` and this handoff on branch `audit/s00-publication-transaction-reaudit`.

## Scientific boundary

No raw ROOT production run, Geant4 job, calibration, timing result, penetration/PID result, or detector-performance claim was produced. Historical S00 artifacts may still exist from earlier code; the present finding says current `main` cannot be assumed to regenerate/publish them safely or at the declared paths.

## Next atom

After #1110 transaction repair, audit `S00_selector_v1` model identity. Current canonical code routes configurable `baseline_samples` into `estimate_pedestal_v1_batched`, while the manifest identity string says `v1_first_four_median`. Prove the historical selector cannot silently change indices/expected counts under the same semantic label, and collapse mathematically equivalent candidate selectors before comparing pedestal models.
