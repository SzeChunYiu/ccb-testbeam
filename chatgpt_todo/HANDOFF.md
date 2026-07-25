# Latest Handoff — AUD-LEDGER-004 data-side Rmax occupancy semantics

## Delivery identity

- **Session stamp:** `2026-07-25T210216Z`
- **Task ID:** `AUD-LEDGER-004`
- **Initial remote `main`:** `5f4847036ab6d3ee8fb268f9ed96abc36852bbc4`
- **Validated audit/evidence through:**
  `58c89c26a05e58489a9db48762365f0ab7cb1690`
- **Destination:** direct GitHub contents-API commits to remote `main`; no force-push,
  history rewrite, task branch, or PR transport.
- **Push-output boundary:** successful commit SHAs were returned rather than conventional
  textual `git push` stdout.

## Reviewed state

Reviewed repository history, open PRs, closed PR #868, the canonical claim ledger, the
new raw-beam data-side producer and report, the exact S10b `CL-011` live-time record, the
existing `CL-010` quarantine validator, and current coordination records.

Exact reviewed source identities:

- `docs/claim_ledger.csv` blob `83238de4b244b741bd2227986455edf04bff3265`;
- `scripts/studies/data_side_real_beam.py` blob
  `22a86dd5c5c8fa9f993e501abd426791034ac16c`;
- `reports/studies/data_side/REPORT.md` blob
  `daf9ba94b66eac6988f748597fa0fae799f6aea4`.

No open PR existed. PR #868 remained closed, unmerged, and non-mergeable and was not
modified.

## Confirmed scientific-governance defect

The raw-beam study measures selected B-stave pulse multiplicity over composite
`(run,eventno)` keys: 640,737 selected pulses over 584,602 events, or mean multiplicity
`1.0960225931488432`. This is useful descriptive occupancy evidence. It does not provide
run exposure, event-arrival rate, trigger live-time accounting, luminosity, or an
independently measured maximum acceptable pile-up mean.

The producer nevertheless sets `mu_max=0.38`, assumes `tau_eff=130 ns`, calculates
`2.923076923076923 MHz`, calls the result data-derived, and says occupancy grounds the
convention. The `CL-010` row then publishes `2.92 MHz`, adds unsupported `0.10` and
`0.20 MHz` uncertainty components, changes status to `DONE_DATA_ONLY`, points to this
study, and removes blocker `S-STAT-003`.

That upgrade conflicts with the tracked source-conflict quarantine: `0.38` is a legacy
duty-factor convention, the recovery-failure ceiling was not crossed, and the exact S10b
`CL-011` estimand is `124.79018394263471 ns`, not the ad hoc `130 ns` value.

## Independent calculation

```text
0.38 / 124.79018394263471 ns = 3.045111305987686 MHz
0.38 / 130 ns               = 2.923076923076923 MHz
```

The former 130 ns choice differs by `-0.12203438291076338 MHz`, or
`-4.007550813357915%`, from the exact-CL-011 model calculation. Both values remain
model/convention sensitivities. Neither becomes a data-derived absolute rate because a
selected-pulse occupancy histogram is available.

## Delivered audit gate

Added policy:

`OCCUPANCY_DOES_NOT_IDENTIFY_ABSOLUTE_RMAX_WITHOUT_RATE_EXPOSURE`

The validator:

- reads exact bytes once with strict UTF-8 and records SHA-256 and size;
- enforces the canonical 43-column ledger schema and unique `CL-010`/`CL-011` rows;
- requires the existing source-conflict quarantine for `CL-010`;
- binds `CL-011` to the exact S10b data-only estimand and blocker;
- rejects producer/report language that authorizes absolute Rmax from occupancy;
- requires a future fail-closed contract with `rmax_authorized=false` and `Rmax withheld`;
- reconstructs both reciprocal calculations independently;
- publishes JSON atomically and rejects destructive output aliases.

## Validation

```text
python -m py_compile \
  tools/audit/audit_data_side_rmax_semantics.py \
  tests/test_audit_data_side_rmax_semantics.py \
  tools/audit/render_data_side_rmax_semantics_evidence.py

pytest -q tests/test_audit_data_side_rmax_semantics.py
6 passed in 0.03s
```

Additional results:

- executable current-like fixture matching the observed contract: `FLAWED`, 34 findings;
- corrected contract fixture: `VALIDATED`, zero findings;
- altered exact `CL-011` tau: rejected;
- duplicate `CL-010`: controlled input error;
- invalid UTF-8: controlled status 2;
- destructive input/output alias: rejected;
- JSON parse: PASS;
- SVG XML parse: PASS;
- maximum changed Python line length: 93 characters.

This environment did not contain a full repository checkout, so the exact GitHub files
were inspected through repository reads and represented by the executable current-like
fixture; no claim is made that the new CLI was run against locally cloned production bytes.

## Delivered files

- `tools/audit/audit_data_side_rmax_semantics.py`
- `tests/test_audit_data_side_rmax_semantics.py`
- `tools/audit/render_data_side_rmax_semantics_evidence.py`
- `docs/validation/data_side_rmax_semantics_validation.json`
- `docs/validation/data_side_rmax_semantics.svg`
- `docs/validation/data_side_rmax_semantics_audit.md`
- `chatgpt_todo/archive/2026-07-25T210216Z_AUD-LEDGER-004_RMAX_OCCUPANCY_SEMANTICS.md`
- updated `chatgpt_todo/ACTIVE_TASK.md`
- updated `chatgpt_todo/HANDOFF.md`

The SVG is software/documentation provenance evidence, not detector-rate data.

## Direct-main sequence

- `c00a81ab9621aad5f718b20eb896554416262482` — audit gate
- `37191d19adc165b9d4f43414ab0ead348a0be049` — focused tests
- `40bf2765ead988817e4b15423b2cbb728f8030cf` — evidence renderer
- `2c9c5497178d104c48e86a4edb375b855ae9cfd4` — machine-readable evidence
- `370cf3b2adf1e57c181e4f1628ee6e2016f9a844` — visual evidence
- `d91b106cc0153cda7fa5ee7a07aa173362763811` — audit report
- `3ce00819b46f31aa164db081a813afb0bcee8904` — immutable archive
- `58c89c26a05e58489a9db48762365f0ab7cb1690` — active-task record

## Acceptance boundary and next action

The audit implementation, tests, arithmetic reconstruction, machine-readable record,
visual evidence, archive, and coordination handoff are `VALIDATED`. The production
`CL-010` claim remains `BLOCKED`; `accepted_rmax_mhz` is null.

The next focused unit must remediate `scripts/studies/data_side_real_beam.py`,
`reports/studies/data_side/REPORT.md`, the occupancy figure/metadata, and the `CL-010`
ledger row together. It must preserve the measured multiplicity as descriptive evidence,
remove unsupported uncertainty components, restore `S-STAT-003`, and require both this
validator and `tools/audit/validate_claim_ledger_cl010.py` to return zero findings.

No raw ROOT data were rerun. No absolute event rate, live exposure, luminosity, pile-up
tolerance, recovery ceiling, calibration, or detector-performance result was produced.
Repository-wide pytest/ruff, broad link checking, production figure regeneration, and
GitHub Actions were not run.

`SESSION_LOG.md`, `MASTER_INDEX.md`, `BACKLOG.md`, `BLOCKERS.md`, and aggregate matrices
were not replaced because their complete append-only bytes were available only through
paged or truncated views while the connector offers whole-file replacement rather than a
byte-safe append. Replacing a partial reconstruction could erase unrelated provenance.
The immutable archive and this handoff preserve the complete append-equivalent record.
