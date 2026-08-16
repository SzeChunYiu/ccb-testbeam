# Immutable session record — AUD-G4-019

## Session

- UTC: `2026-07-23T23:08:25Z`
- Repository: `SzeChunYiu/ccb-testbeam`
- Owner: scheduled ChatGPT scientific-review session
- Initial remote `main`: `eec220db6807d3d3615d92c6d39d4fb2e18e4335`
- Destination: direct to `main`
- Status: COMPLETE for simulation-table parse/provenance byte-snapshot identity; accepted stopping-power physics closure remains PARTIAL/BLOCKED.

## Start-of-run review

- Fetched current remote-main history and confirmed admin/push permission.
- Re-read the canonical stopping-power comparison, shared simulation parser, focused parser tests, active task, backlog, previous handoff, master index, result map, study ledger, claim matrix, visualization matrix, and blocker register.
- Rechecked PR #868: closed, unmerged, non-mergeable; it was not modified or merged.
- Direct clone/fetch failed with `Could not resolve host: github.com`; exact files were reconstructed through authenticated GitHub reads.
- `AUD-REPO-001` remained owned by a concurrent session and was not duplicated.

## Confirmed defect

`validate_stopping_power_sim_table.py` v1.1.0 parsed event rows with `Path.read_text()`, then later measured `Path.stat().st_size` and streamed the path again through `sha256_file()`. These were separate path reads. If the file was replaced between those operations, normalized rows could describe bytes A while `input_bytes` and `input_sha256` described bytes B.

A deterministic synthetic regression intercepted the parser after data-line formation and replaced the path. The former algorithm returned rows from the original table but size/hash from the replacement table. The former algorithm also allowed invalid UTF-8 to escape as an uncaught `UnicodeDecodeError` rather than a controlled input failure.

## Validated correction

Validator v1.2.0 now:

1. reads exact input bytes once;
2. decodes and parses that byte string;
3. derives byte count from `len(input_bytes)`;
4. derives SHA-256 from the same byte string;
5. records `input_snapshot_method=SINGLE_READ_EXACT_BYTES`;
6. converts invalid UTF-8 into `SimulationTableError`, producing CLI status 2 with no validation success line.

No change was made to particle, energy, deposit, track-length, raw/quenched, alias, physical-value, or row-completeness acceptance rules.

## Validation

Executed on exact local reconstructions:

```text
python -m py_compile \
  tools/audit/validate_stopping_power_sim_table.py \
  tests/test_validate_stopping_power_sim_snapshot.py

python -m pytest \
  tests/test_validate_stopping_power_sim_table.py \
  tests/test_validate_stopping_power_sim_snapshot.py -q

19 passed in 2.01s
```

Negative control against the former algorithm:

```text
2 failed
```

The failures are the expected provenance mismatch after path replacement and uncontrolled invalid-UTF-8 decoder exception.

Additional checks:

- validation JSON parsed;
- SVG parsed as XML;
- maximum changed Python line length: 94;
- validated implementation SHA-256: `35068d8dd59680ab12ac9f4f595cbc00fb406713d09c931a7071ca7caf317bee`;
- validated implementation Git blob: `6a57b93d6fb4f63a7b714b858d379f02b5a7eda0`;
- focused test SHA-256: `847b7a41c779ed8cf3ad8a76bb108552e42f6ab0f9788ac0aaffdd16b593145d`;
- focused test Git blob: `6143cb222539c29b05251a9f777e753012521785`.

Not run:

- full repository pytest;
- ruff;
- Geant4 build/CTest;
- ROOT processing;
- real simulation execution;
- GitHub Actions.

## Evidence

- `docs/validation/stopping_power_sim_snapshot_audit.md`
- `docs/validation/stopping_power_sim_snapshot_validation.json`
- `docs/validation/stopping_power_sim_snapshot.svg`

The SVG is explicitly labelled synthetic software regression evidence, not detector data.

## Direct-main commits

- `efc9610bd382ea52f6bbc8e53be87af6c74766fa` — `fix(audit): bind simulation rows to one byte snapshot`
- `76b5e1dcf5e8fb3ad9c66a9646dd8ddab3d3dcea` — `test(audit): cover simulation byte-snapshot provenance`
- `964042dc25b1b0abcd0eac0ec35e4f1b3268abe7` — `docs(validation): record simulation byte-snapshot audit`
- `f28049ce952bf5e8194f7c3936adab2401d713b6` — `docs(validation): add simulation snapshot validation record`
- `807febe85c35b537c53a5acdf1795ee9a67d7cb2` — `docs(validation): visualize simulation byte-snapshot gate`
- `17322a138cc160eef09beadd2ede6df5a4076625` — `docs(audit): claim simulation byte-snapshot task`
- `462738e51fdfc93cb5eaef34e0de1d8260369c83` — `docs(audit): record simulation byte-snapshot task`

Every write targeted `main`; no force push, ref rewrite, task branch, or unrelated deletion was used.

## Scientific boundary

This establishes software/provenance identity between parsed rows and the reported input digest. It does not validate a real Geant4 export, establish that local deposited energy equals projectile total energy loss, quantify secondary escape or energy evolution, implement an uncertainty budget, or demonstrate Geant4/PSTAR agreement.

`BLK-G4-SP-001` remains open. The next scientific work remains immutable real-export validation (`AUD-G4-011`) and an accepted projectile-loss closure (`AUD-G4-005`).

## Coordination limitation

`SESSION_LOG.md` is append-only, but the connector exposes complete-file replacement rather than a safe append primitive and the full current file was not available as one byte-safe payload. It was not replaced because doing so could destroy prior provenance. This immutable archive is the complete session record.
