# Latest Handoff

## Session

- **UTC:** 2026-07-22T02:10:31Z
- **Task:** AUD-ANOM-001 (PARTIAL)
- **Initial remote main:** `7047be4e49d4ed27356b235dc10c071ea6378024`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Write target:** direct to `main`

## Repository state inspected

- `README.md`;
- `WIKI.md` C12/MV6 summary entries;
- `docs/academic_chapters/09_anomaly_id.md` title, evidence banner, and abstract;
- `scripts/sync_c12_public_claims.py`;
- `tests/test_sync_c12_public_claims.py`;
- `chatgpt_todo/HANDOFF.md` and `SESSION_LOG.md`;
- recent remote-main history.

A direct clone was attempted with:

```bash
git clone --depth 1 https://github.com/SzeChunYiu/ccb-testbeam.git /tmp/ccb-testbeam
```

It failed with `Could not resolve host: github.com`. Repository reads and writes therefore used the authenticated GitHub connector. Local Python validation used exact temporary copies of the modified synchronizer and test module.

## Confirmed scientific-documentation flaw

`README.md` still promoted two Monte-Carlo-only results beyond their demonstrated evidence:

1. proton/deuteron PID AUC 0.986 was labelled `MC-validated`, although transfer to real beam data is not demonstrated;
2. the C12 anomaly was presented as an identified real anomaly, although the inspected evidence is a truth-labelled MC population of 283 / 87,555 tracks (0.32%), with approximately 55% C12 inside that selected simulated class.

The supported interpretation is that these are truth-labelled-MC results. The related real-data transfer and species identity remain unvalidated.

## Work pushed directly to main

1. Extended `scripts/sync_c12_public_claims.py` with exact README replacements.
2. Added a dedicated regression test requiring scientifically qualified README wording and removal of the two overclaim phrases.
3. Updated README headline results directly on `main`:
   - PID now states truth-labelled MC only and unvalidated data transfer;
   - the C12 line now reports the MC numerator/denominator, selected-class composition, and unvalidated real-data identity.
4. Appended the complete run record to `chatgpt_todo/SESSION_LOG.md`.

## Validation

Executed on exact temporary copies:

```bash
python -m py_compile \
  /tmp/sync_c12_public_claims.py \
  /tmp/test_sync_c12_public_claims.py
python -m pytest /tmp/test_sync_c12_public_claims.py -q
```

Result:

```text
6 passed in 0.05s
```

No raw data, Monte Carlo output, numerical analysis result, plot, cached artifact, or generated binary was changed. No empirical C12-in-data or data PID-performance claim is made.

## Main progression

- Initial remote main: `7047be4e49d4ed27356b235dc10c071ea6378024`
- `b7a87ad70d080a1fe270340008f53f78d20b9e72` — `fix(validation): include README in C12 claim synchronizer`
- `23bf0e45e8fcdf230677315369f5de30ac7b39d4` — `test(validation): cover README C12 evidence wording`
- `bef8e62aab5339a17d4b7fba892a40e5e9c72649` — `docs: qualify README PID and C12 headline evidence`
- `d0ae94615f1cf8f5bc1060722aa5f86a7fafe8ba` — `docs(audit): record README evidence qualification session`
- This handoff update is the final session commit and must be verified as remote-main head.

## Acceptance status

- README evidence correction: COMPLETE.
- Synchronizer README coverage: COMPLETE.
- Synthetic unit validation: COMPLETE (`6 passed`).
- WIKI synchronization: NOT_STARTED on the public file.
- Chapter 9 synchronization: NOT_STARTED on the public file.
- Matched data/MC closure: BLOCKED on traceable inputs and compute.
- Empirical C12 identification in data: BLOCKED.

## Next action

In a working checkout based on latest `origin/main`:

```bash
python scripts/sync_c12_public_claims.py
python scripts/sync_c12_public_claims.py --check
python -m pytest tests/test_sync_c12_public_claims.py -q
python scripts/broken_link_checker.py
```

Review the exact `WIKI.md` and Chapter 9 diff before committing synchronized wording directly to `main`. The synchronizer now also verifies that README remains in the corrected state.
