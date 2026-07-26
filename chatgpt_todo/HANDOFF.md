# Latest Handoff

## Session

- **Task:** `AUD-DELTAE-007`
- **Stamp:** `2026-07-26T050335Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `6c25424ae2507396d352d0b7e45d737752b2872d`
- **Validated implementation/evidence head before handoff:** `54256005790b46d11ec0d025d14fab4f844402e3`
- **Destination:** direct commits to `main`; no task branch, force-push, history rewrite, PR merge, or deletion of unrelated work.
- **Focused acceptance:** canonical present-signal input boundary `VALIDATED / COMPLETE`.
- **Scientific acceptance:** A-002 physics remains `PARTIAL / BLOCKED`.

## Start-of-run review

Fetched current `main`, recent history, repository permissions, open draft PR #933, closed PR #868,
commit status, mandatory coordination records, the canonical DeltaE front door and retained numerical
core, existing DeltaE tests, prior CSV-key and Parquet-provenance evidence, backlog, blockers, and the
previous handoff. No active or completed task duplicated this input-integrity defect.

PR #933 remained draft, open, non-mergeable, and blocked by its red repository-wide gate. PR #868
remained closed, unmerged, and non-mergeable. Neither PR was modified or merged.

## Confirmed defect

Retained numerical-core blob `fe5dd5e4673f32fa5a4b94776531f2b392e12414` used
`pd.to_numeric(..., errors="coerce").fillna(0.0)` for supported B-layer signals. A malformed or
missing-value cell in an existing column could therefore become zero, while positive or negative
infinity remained. Extra MC `edep_B*` columns discovered dynamically for full-energy and stopping
calculations were not all finite-validated.

Exact former canonical front-door blob: `a5c255a971a7cf672f011f84b91a3c7b64d1f209`.

A present invalid measurement and a wholly absent detector-layer column are not equivalent data
states. Only the absent-column case is eligible for the established zero-fill convention.

Policy:

`DELTAE_PRESENT_SIGNAL_CELLS_MUST_BE_FINITE_NUMERIC`

Missing-layer policy:

`ZERO_ONLY_WHEN_SUPPORTED_COLUMN_IS_ABSENT`

## Remediation

The canonical front door now:

1. coerces every present data `amp_B2/B4/B6/B8` cell to numeric;
2. rejects nonnumeric, missing-value, NaN, positive-infinite, and negative-infinite present cells;
3. discovers and validates every present MC `edep_B*` column, including optional deeper layers;
4. fills zero only when a supported downstream column is wholly absent;
5. reports the affected column, invalid count, and first row indices in `SignalValueError`;
6. installs strict preparation functions into the retained core's production hooks;
7. publishes both policies in result and manifest reader contracts.

## Files changed

- `scripts/single_stave/deltaE_E.py`
- `tests/test_deltae_signal_value_contract.py`
- `tools/audit/audit_deltae_signal_value_contract.py`
- `tests/test_audit_deltae_signal_value_contract.py`
- `tools/audit/render_deltae_signal_value_evidence.py`
- `docs/validation/deltae_signal_value_contract_validation.json`
- `docs/validation/deltae_signal_value_contract.svg`
- `docs/validation/deltae_signal_value_contract_audit.md`
- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/BACKLOG.md`
- `chatgpt_todo/archive/2026-07-26T050335Z_AUD-DELTAE-007_SIGNAL_VALUE_INTEGRITY.md`
- this handoff.

## Exact identities

- former front-door blob: `a5c255a971a7cf672f011f84b91a3c7b64d1f209`;
- retained-core blob: `fe5dd5e4673f32fa5a4b94776531f2b392e12414`;
- corrected front-door blob: `be00a58dbbc3c2b9de424c80bea3b5a4be6fe119`, 10,349 bytes,
  SHA-256 `ef51bec47aa15eada369a4e46f4036dfe4ba54409030aa18adf1a3d951165548`;
- direct-test SHA-256: `569f53a27d302f6f005e6e87969bb36dcf35dac1eb1d69ce4e0484763d38b43c`;
- auditor SHA-256: `7bcf2874840a6728a7d45aff48513fbf3aa722382634e2fc50b40292503d4aa4`;
- audit-test SHA-256: `4823264f0a7a15dbae9c494cb1c409c5de5c9c353ebfef19c2625c49ac6dbeae`;
- renderer SHA-256: `1468e9ae3ee384ab1dbbe000f988f28046553570c457b90fb6f59100876783f1`.

## Validation

Executed against the exact proposed front door, tests, audit gate, and renderer:

```text
python -m py_compile \
  scripts/single_stave/deltaE_E.py \
  tools/audit/audit_deltae_signal_value_contract.py \
  tests/test_deltae_signal_value_contract.py \
  tests/test_audit_deltae_signal_value_contract.py \
  tools/audit/render_deltae_signal_value_evidence.py

PYTHONPATH=. pytest -q \
  tests/test_deltae_signal_value_contract.py \
  tests/test_audit_deltae_signal_value_contract.py

19 passed in 3.06s
```

Environment: Python `3.13.5`, pandas `2.2.3`, NumPy `2.3.5`.

Validated controls:

- malformed present data cell fails closed rather than becoming zero;
- NaN and both infinities fail closed;
- invalid required and optional MC layers, including `edep_B10`, fail closed;
- wholly absent supported downstream columns still zero-fill;
- finite numeric strings preserve their values;
- result and manifest contain both policies;
- retained-core production hooks point at the strict functions;
- exact-source audit returns `VALIDATED` with zero findings;
- malformed-contract mutation, invalid UTF-8, and destructive output alias fail closed;
- JSON is atomically replaced; JSON and SVG parse; Python lines are at most 100 characters.

The networkless validation checkout used the exact proposed front door/tests/auditor/renderer and a
minimal retained-core stub to exercise this focused boundary. A complete clone could not be
materialized because `github.com` DNS resolution failed. Repository-wide pytest/ruff, actual ROOT or
Parquet processing, GitHub Actions, and the full link inventory were not run and are not claimed.

## Better-method decision

Continuing zero fill was rejected because it conceals invalid measurements. Dropping invalid rows was
rejected as the default because it silently changes event cardinality and can introduce selection
bias. The selected method fails closed on every present invalid signal and preserves zero fill only
for a wholly absent supported downstream layer.

## Direct-main commits before handoff

- `6dc2d50c4d8d6a10f99ff2c5ab351c515d86cd18` — task claim;
- `63348699fe3a507fb9008ee582b193c28c7a7b20` — implementation;
- `03439cbb7b66e300a21eeadb4e8f880b8a10620c` — direct tests;
- `c08f1e23bc82eb8bcedf78694907e67133e621f3` — fail-closed audit;
- `cff6e38e947855a06bec096be07db37208697a15` — audit tests;
- `f38c2eb713d802ea3bbbde4f4c288989ad0f1c32` — evidence renderer;
- `115e2c7b3905d07d5c5d847b974961bdc85f8f5a` — validation JSON;
- `cf21c48f3231d3c6167a57f227d5c22d5a69d47b` — visual evidence;
- `bd4d1fc72c2d51e03cecadd21aa49523511d5a7f` — audit report;
- `ac029b8ffbb5efa2995ce942783bf571cc1642f7` — backlog synchronization;
- `b1348234f019ffb0a620ee75e94987bbad739616` — immutable archive;
- `54256005790b46d11ec0d025d14fab4f844402e3` — active-task completion.

GitHub returned successful direct-main commit SHAs for every write. No force update was used.

## Coordination limitation

`SESSION_LOG.md` was not appended. The connector exposes complete-file replacement rather than a
byte-safe append operation, while the complete append-only file could not be materialized in the
networkless checkout. Replacing a partial reconstruction could erase prior provenance. This unmet
mandatory step is recorded explicitly here and in the immutable archive rather than reported as
complete.

## Scientific boundary and next action

No exact A-002 pulse table, ROOT file, amplitude convention, pulse polarity, stopping fraction,
DeltaE-E PID result, uncertainty budget, calibration, or detector-performance result was produced.
`AUD-DELTAE-001`, `AUD-DELTAE-002`, `AUD-AMP-009`, `AUD-AMP-010`, and `BLK-AMP-001` remain open.

Next, obtain hash-bound convention and polarity evidence and execute a content-addressed production
rerun through the strict input boundary, followed by event-cardinality, uncertainty, plot, and claim
validation.
