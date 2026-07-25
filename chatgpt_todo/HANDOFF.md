# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-25T102318Z`
- **Task:** `AUD-WIKI-004`
- **Unit:** exact root-WIKI binding of the canonical S10b live10 claim
- **Initial remote `main`:** `dcd30497d7e83a35d686b8835aefdb2537fbcf02`
- **Destination:** direct focused commits to remote `main`; no force-push,
  branch transport, PR, or history rewrite
- **Acceptance:** **PARTIAL** — the defect, gate, tests, and evidence are
  validated; root-WIKI remediation remains open
- **Immutable archive:**
  `chatgpt_todo/archive/2026-07-25T102318Z_AUD-WIKI-004_TAU_EFF_PUBLIC_BINDING.md`

## Start-of-run review

Inspected current main and recent history, the root WIKI, exact-width `CL-011`,
Chapter 5, existing WIKI validators, mandatory coordination files, open PRs,
closed PR #868, and current-head status checks. Commit
`dcd30497d7e83a35d686b8835aefdb2537fbcf02` had just corrected Chapter 5, so
this session avoided duplicating that work and audited the still-stale public
WIKI. PR #868 remained closed, unmerged, non-mergeable, and untouched. The
initial head had no attached status checks.

## Canonical contract

`CL-011` binds S10b run-average live10 relative to CFD20 to:

- `124.79018394263471 ns`;
- run-bootstrap 95% interval
  `[123.33094981246663, 126.35875117626817] ns`;
- 14 runs and 252266 selected pulses;
- `data_measurement`, `DONE_DATA_ONLY`, validation not authorized;
- primary source commit
  `da9651c56ef6495ce9656d84b69b600daa6d8f86`;
- blocker `BLK-S10B-001`;
- no statistical/systematic/total uncertainty decomposition.

The result is threshold-, selection-, and run-weighting-specific, not a
universal detector dead time. MV5 reuses it as an input rather than independently
validating it.

## Confirmed WIKI defects

The canonical-results row publishes rounded `124.79 ns`, unsupported `0.5` and
`1.0` components, `data + MC self-consistent`, and `VALIDATED`.

The pile-up section states that tau-eff remains validated, publishes rounded
`124.79 ns` with `VALIDATED`, and omits the exact interval, run/pulse counts,
run-average estimand, non-universal caveat, MV5 reuse distinction, and
`BLK-S10B-001`.

## Delivered method

Added policy
`WIKI_TAU_EFF_MUST_BIND_EXACT_S10B_ESTIMAND_AND_INTERVAL` through:

- `tools/audit/validate_wiki_tau_eff_public_binding.py`;
- `tests/test_validate_wiki_tau_eff_public_binding.py`;
- `tools/audit/render_wiki_tau_eff_public_binding_evidence.py`.

The gate reads exact bytes once with strict UTF-8, requires one exact 43-column
`CL-011`, binds checks to unique canonical-table and pile-up-section anchors,
rejects decoy global tokens, and verifies the exact central value, interval,
counts, uncertainty semantics, truth type, status, blocker, and source
interpretation. It publishes JSON atomically and rejects input/output aliases.

## Validation

```text
python -m py_compile \
  tools/audit/validate_wiki_tau_eff_public_binding.py \
  tests/test_validate_wiki_tau_eff_public_binding.py \
  tools/audit/render_wiki_tau_eff_public_binding_evidence.py

PYTHONPATH=. pytest -q tests/test_validate_wiki_tau_eff_public_binding.py

7 passed in 1.63s
```

The exact current public excerpts returned `FLAWED` with 24 findings across
these families:

- canonical exact-value/interval binding missing;
- canonical unsupported uncertainty components;
- canonical truth-type and status mismatch;
- pile-up exact-value/interval binding missing;
- pile-up status mismatch;
- pile-up scientific caveats missing;
- stale public phrases present.

A corrected two-location fixture returned `VALIDATED` with zero findings. A
fixture containing all exact tokens in a decoy location still failed the stale
claim sites. Invalid UTF-8, duplicate anchors, malformed ledger contracts, and
destructive aliases failed closed. JSON and SVG parsed; changed Python lines
were at most 95 characters.

## Evidence files

- `docs/validation/wiki_tau_eff_public_binding_audit.md`
- `docs/validation/wiki_tau_eff_public_binding_validation.json`
- `docs/validation/wiki_tau_eff_public_binding.svg`

Remote source identities recorded in the validation record:

- WIKI blob: `91e82c59a2b59b285c6a529c0637ed665be2c4fd`;
- claim-ledger blob: `254dc5b64945260193d6b1bd4146bd6400ad28cf`;
- Chapter 5 correction commit:
  `dcd30497d7e83a35d686b8835aefdb2537fbcf02`.

## Direct-main commit sequence

- `1ba37eb9c47fc3e1c95891b6e35f6709e5f3a093` — validator;
- `a618463cac98d930625f3e6cd0b2600c7df6ed69` — focused tests;
- `1cad8900d21e356fed9c117d2adf6d5bd67233df` — evidence renderer;
- `e353bb4cc9217c9091ec68af744a820d147fb37e` — machine-readable evidence;
- `70c6eed4916c559f509e8b47edde42efebc71b50` — visual evidence;
- `18b38d59b23b7fe7f6b5216690acb3841e435627` — audit report;
- `a66925193f4c498fd2946ab70a2a9baea2fd2b4c` — active-task update;
- `672084c9a3aeb96519841ab740e875c7032bbfbd` — immutable archive.

GitHub contents writes returned successful direct-main commit SHAs. The final
handoff commit and subsequent confirmation SHA are recorded after publication.

## Next exact unit

Rewrite both root-WIKI claim locations to the exact S10b contract, then run:

1. `validate_wiki_tau_eff_public_binding.py`;
2. `validate_wiki_claim_front_door.py`;
3. `validate_wiki_canonical_results.py`;
4. the current broken-link checker.

Do not mark the public synchronization complete until all pass on the exact
committed WIKI and ledger bytes.

## Scientific boundary

No ROOT bytes were reprocessed, no waveform fit was rerun, and no new
uncertainty, detector-wide dead time, accepted Rmax, calibration, or detector-
performance result was produced.

`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, `MASTER_INDEX.md`, and aggregate
matrices were not replaced because only whole-file replacement was available
for these shared records. Replacing a partial reconstruction could erase
concurrent or append-only provenance. The immutable archive and this handoff
contain the complete append-equivalent record; this synchronization gap remains
explicitly open.
