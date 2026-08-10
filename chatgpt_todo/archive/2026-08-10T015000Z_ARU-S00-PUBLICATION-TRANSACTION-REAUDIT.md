# ARU-S00-PUBLICATION-TRANSACTION-REAUDIT

## Session identity

- **Stamp:** 2026-08-10T015000Z
- **Task:** re-audit S00 publication transaction after merged PR #1122 / closed issue #1110
- **Initial remote main:** `381c02d814cc85852fab8b8f3f999df269e13780`
- **Primary issue:** #1110 (reopened during this session)
- **Selected atom:** staged S00 artifact set -> publication commit point -> canonical pulse-table/report identity
- **Evidence class:** source-level deterministic software/provenance defect plus a minimal local path-contract reproduction; no beam-data or Monte Carlo inference

## Atomic contract

Canonical configuration declares two distinct authoritative destinations:

```text
output_dir       = reports/S00_data_integrity_pipeline_reproduction
pulse_table_path = data/processed/s00_selected_b_pulses.csv.gz
```

The publication transaction must satisfy all of the following:

1. a completed staging tree must survive until the commit point;
2. interrupted publication must leave the previous authorising generation byte-identical;
3. the configured pulse-table destination must exist after successful publication;
4. manifest paths must resolve after publication and must never point to ephemeral staging paths;
5. concurrent readers must not observe a partially deleted canonical generation;
6. CL-001 source-data/source-manifest bindings must resolve to the actual authorised generation.

## Confirmed defect 1 — staging self-deletion

Current `main()` creates:

```python
staging = out_dir.parent / f".{out_dir.name}.staging-{os.getpid()}"
```

Current `atomic_publish()` independently creates:

```python
tmp = target_dir.parent / f".{target_dir.name}.staging-{os.getpid()}"
```

and then executes:

```python
if tmp.exists():
    shutil.rmtree(tmp)
staging_dir.rename(tmp)
```

For the actual caller, `target_dir == out_dir`, so `staging_dir == tmp`. The function therefore recursively deletes its own completed staging input, then attempts to rename the now-nonexistent path onto itself.

Minimal exact-logic reproduction:

```text
staging == atomic tmp: True
outcome: FileNotFoundError: .../.S00_data_integrity_pipeline_reproduction.staging-<pid> -> .../.S00_data_integrity_pipeline_reproduction.staging-<pid>
staging exists after failure: False
target exists after failure: False
```

The merged unit tests did not reproduce the real caller contract: they pass `tmp_path / "staging"` as the source, which is deliberately different from the internal `tmp` name.

## Confirmed defect 2 — configured pulse-table destination is not published

`main()` builds:

```python
staging_selected = staging / selected_path.name
selected.to_csv(staging_selected, ...)
```

and then publishes only:

```python
atomic_publish(staging, out_dir)
```

Even after defect 1 is fixed, this moves the selected-pulse file under the report directory rather than to configured `data/processed/s00_selected_b_pulses.csv.gz`. No copy/rename to the configured pulse-table parent is present in current control flow.

The manifest is also written before publication with `staging_selected` as its `selected_pulse_table` argument, so it serializes an ephemeral `.staging-<pid>` pathname that becomes invalid after a successful staging-tree rename.

Stdout nevertheless prints the configured `selected_path`, which can report a canonical data path that was not written by the transaction.

CL-001 currently still binds `source_data` to `data/processed/s00_selected_b_pulses.csv.gz` and `source_manifest` to `reports/S00_data_integrity_pipeline_reproduction/manifest.json`, so the transaction and claim-provenance contracts are inconsistent.

## Confirmed defect 3 — directory replacement is not rollback-safe

Current replacement sequence contains:

```python
if target_dir.exists():
    shutil.rmtree(target_dir)
tmp.rename(target_dir)
```

A crash or exception during/after `rmtree(target_dir)` destroys the previous authorising generation before the replacement is committed. During recursive deletion, concurrent readers can observe a partial generation. This violates issue #1110's explicit rollback/atomicity invariant.

## Mechanism universe and equivalence collapse

Candidate publication models:

- **H1 mutable-directory replacement:** delete old canonical directory then rename new directory into place. Rejected: not rollback-safe; observable partial/absent state.
- **H2 two-directory rename with backup:** rename old -> backup, new -> canonical, then remove backup. Better recovery but still has a commit-window/path-visibility contract unless platform-specific atomic exchange is used.
- **H3 immutable generations + atomic pointer:** publish `reports/S00_runs/<model_hash>/...`, fsync/validate, then atomically replace a small `CURRENT.json`/pointer on the same filesystem. Survives as preferred portable model.
- **H4 direct canonical writes after gates:** rejected because multi-file publication has no single atomic commit point and partial writes are observable.

H1 and H4 are observationally equivalent with respect to interrupted multi-file authority: both can expose a partially updated canonical state. They are collapsed and rejected.

## Discriminating tests required

1. Build staging with the exact expression used by `main()`; publication must not self-delete.
2. Inject failure immediately before commit point; old generation hashes must remain identical.
3. Inject failure immediately after candidate preparation and during pointer replacement; old pointer or new pointer must resolve, never an absent/partial generation.
4. After successful publication, require configured `pulse_table_path` to exist and hash-match the authorised staged table.
5. Require `manifest["selected_pulse_table"]` to resolve after publication and contain no `.staging-<pid>` component.
6. Spawn a concurrent reader loop during repeated publication; every observed authoritative pointer must resolve to a complete generation.
7. Revalidate CL-001 source-data and source-manifest paths against the repaired transaction.

## Preferred implementation

Use immutable model-bound generation directories. Treat publication as an atomic pointer update rather than recursive directory replacement:

```text
raw/config/model -> staging generation -> all gates -> fsync/close
                 -> immutable generation/<model_hash>/
                 -> write CURRENT.json.tmp
                 -> fsync CURRENT.json.tmp
                 -> os.replace(CURRENT.json.tmp, CURRENT.json)
```

The canonical data and report consumers should resolve through the pointer/manifest. Garbage collection of old generations happens only after successful pointer publication and is not part of the authority commit point.

If a stable compatibility copy at `data/processed/s00_selected_b_pulses.csv.gz` must remain, its update needs a separate atomic file replacement from the authorised immutable generation and the manifest must distinguish immutable source from compatibility alias.

## Four sequential review passes

### Data/reconstruction lead — BLOCK

Evidence: current source path algebra and config destinations. Strongest counter-hypothesis: perhaps `atomic_publish` receives a differently named staging directory in production. Falsifier: exact `main()` source constructs the same `.staging-<pid>` name as `atomic_publish`; counter-hypothesis eliminated. Residual uncertainty: none for self-delete/path mismatch; real ROOT run not needed.

### Adversarial mechanism reviewer — REJECT closure

Evidence: merged tests and actual caller. Strongest counter-hypothesis: unit tests covering rollback imply the production transaction is safe. Falsifier: tests use `tmp_path / "staging"`, not the production source name, and contain no crash-after-delete or post-publication manifest-path assertion. Residual uncertainty: filesystem/platform details affect exact exception text, not the path identity defect.

### Validation/statistics reviewer — BLOCK

Evidence: no beam/MC statistic is needed; this is deterministic publication-state integrity. Strongest counter-hypothesis: fixed-count and sorted gates protect the output. Falsifier: defects occur after gates, at publication, and can delete the authorised candidate or previous target independently of count correctness. Required validation is transactional fault injection plus hash/path invariants.

### Claims/provenance reviewer — BLOCK

Evidence: CL-001 source_data/source_manifest bindings and current transaction. Strongest counter-hypothesis: manifest/config digest is sufficient provenance. Falsifier: manifest serializes the pre-publication staging pathname and configured source_data is not actually written by current successful-path logic. Residual uncertainty: existing historical artifact may still exist from older code; that does not validate current producer semantics.

## Repository actions this session

- Reopened GitHub issue #1110.
- Added a source-backed re-audit comment with stable concern IDs, exact reproduction, acceptance delta, and preferred repair architecture.
- Created this immutable archive record on branch `audit/s00-publication-transaction-reaudit` for review/merge.

## Claim consequences

- CL-001 should remain GATED. No numerical count is changed by this source-level finding.
- Do not treat a newly generated S00 artifact set from current `main` as authoritative until the publication transaction is repaired and integration-tested.
- Downstream timing/PID/penetration results that consume a pre-existing historical table are not numerically invalidated by this code defect, but their provenance must identify the exact producer commit/artifact hash rather than assuming current `main` can regenerate the same authoritative path safely.

## Child atoms

1. `S00 canonical model identity`: canonical status currently depends primarily on threshold provenance; selector/baseline/config identity needs an immutable authorisation contract.
2. `S00 selector-v1 immutability`: current batched v1 function accepts caller-provided baseline indices while its identity string says `v1_first_four_median`.
3. `S00 authoritative pointer resolution`: every downstream consumer must resolve a generation rather than infer authority from a mutable path.
4. `S00 concurrent-reader semantics`: define whether readers require lock-free snapshot consistency and how stale generations are retained.

## Next highest-value atom

Audit and harden **selector-v1 identity**: prove that the canonical `v1_first_four_median` label cannot be paired with non-first-four baseline indices or a modified expected-count contract, and collapse mathematically equivalent candidate selectors before any pedestal-model comparison.
