# AUD-WIKI-002 — WIKI front-door consistency audit

## Session identity

- UTC: `2026-07-24T033502Z`
- Owner: scheduled ChatGPT audit session
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote `main`: `e8b01b4414d2a797c5f97fe3ee98f88e99ad254a`
- Validated code/test/evidence head: `57dee4451352b27fc191cbc36805a2d0316600ff`
- Concurrent remote `main` incorporated before final handoff: `6338aed736deee7ac4496981ae04da2b01722ed4`
- Destination: direct to `main`
- Task state: `PARTIAL`; the public inconsistency and validator are validated, while WIKI remediation remains open.

## Start-of-run and concurrency review

- Confirmed repository admin/push permission and default branch `main`.
- Inspected current commits, coordination files, `WIKI.md`, the canonical claim ledger, and PR #868.
- PR #868 remains closed, unmerged, and non-mergeable; it was not modified.
- `AUD-REPO-001` remains owned by another active session and was not duplicated.
- A concurrent non-overlapping `AUD-G4-021` remediation advanced `main`; all this session's later coordination writes were based on the advanced remote history. No force push, history rewrite, task branch, pull request, or unrelated rollback was used.
- A direct checkout was unavailable because the runtime could not resolve GitHub hosts. Exact repository text was inspected through authenticated GitHub contents/ranged reads, and all writes were direct-main connector commits.

## Repository evidence inspected

- `WIKI.md`
  - Git blob SHA-1: `c27a1e555145cb248e253f17a6f6d1cfe64542a8`
  - inspected front matter, confidence-status legend, canonical results table, timing key-results table, and MC validation matrix.
- `docs/claim_ledger.csv`
  - Git blob SHA-1: `6f4d4023814b42a566826912bcef7df9903c41e7`
  - inspected authoritative rows `CL-007` and `CL-011`.
- `chatgpt_todo/{README.md,BACKLOG.md,ACTIVE_TASK.md,HANDOFF.md,BLOCKERS.md,MASTER_INDEX.md,CLAIM_EVIDENCE_MATRIX.md}`.
- Recent repository history and PR #868 metadata.

## Confirmed public claim-state defects

### 1. Status vocabulary and ledger mismatch

The WIKI labels the MV4 raw timing-pull result `PASS` in three separate front-door tables. `PASS` is not a member of the WIKI confidence-status legend. Canonical ledger row `CL-007` records the claim state as `VALIDATED`.

Measured issue counts:

- `STATUS_OUTSIDE_LEGEND`: 3
- `STATUS_LEDGER_MISMATCH`: 3

### 2. Effective live-time truth-type mismatch

The WIKI canonical results table labels `τeff` as `data_only`. Canonical ledger row `CL-011` records `data_mc_self_consistent` and explicitly notes that the truth classification was upgraded during review.

Measured issue count:

- `TRUTH_TYPE_LEDGER_MISMATCH`: 1

### 3. Unsupported uncertainty-completeness statement

The WIKI front matter says `Every number has uncertainty.` The canonical claim ledger contains explicit `CI_MISSING_BLOCKING` fields, including within `CL-007` and `CL-011`. The public statement therefore overstates the completeness of the uncertainty inventory.

Measured issue count:

- `OVERSTATED_UNCERTAINTY_COMPLETENESS`: 1

Total machine-detected issues in the exact cited reconstruction: 8.

These are documentation/claim-governance defects. They do not alter the stored numerical values or establish a new timing or pile-up result.

## Better method and policy

Registered policy:

`WIKI_FRONT_DOOR_MUST_MATCH_CANONICAL_LEDGER`

A complete remediation must:

1. replace all three raw timing `PASS` labels with the canonical `VALIDATED` state;
2. align the effective live-time truth type with `data_mc_self_consistent` using readable WIKI wording;
3. replace the blanket uncertainty-completeness statement with an explicit pointer to unresolved ledger fields;
4. run the validator against the complete exact current WIKI and ledger;
5. require status `VALIDATED` before completing `AUD-WIKI-002`;
6. preserve the distinction between a claim-state label and still-missing uncertainty inputs for `CL-007`.

## Added code, tests, and visual evidence

- `tools/audit/validate_wiki_claim_front_door.py` v1.0.0
  - one-snapshot UTF-8 reads with bytes/SHA-256 provenance;
  - claim-ledger schema and duplicate-ID checks;
  - WIKI legend, status, truth-type, and uncertainty-overclaim checks;
  - JSON output;
  - status 0 `VALIDATED`, status 1 `FLAWED`, status 2 controlled input error.
- `tests/test_validate_wiki_claim_front_door.py`
- `docs/validation/wiki_claim_front_door_audit.md`
- `docs/validation/wiki_claim_front_door_validation.json`
- `docs/validation/wiki_claim_front_door.svg`

The SVG explicitly identifies itself as synthetic documentation/provenance evidence, not detector data, and communicates mismatches with text, layout, and arrows rather than color alone.

## Validation commands and measured results

Executed in a local reconstruction of the committed new files:

```text
python -m py_compile \
  tools/audit/validate_wiki_claim_front_door.py \
  tests/test_validate_wiki_claim_front_door.py

python -m pytest tests/test_validate_wiki_claim_front_door.py -q

5 passed in 0.03s
```

Additional passed checks:

- machine-readable validation JSON parse;
- SVG XML parse;
- corrected synthetic WIKI state returns `VALIDATED`;
- missing required claim ID raises a controlled error;
- invalid UTF-8 returns status 2;
- maximum validator line length: 91 characters;
- maximum test line length: 92 characters.

Exact cited reconstruction:

- WIKI excerpt SHA-256: `7ff43954b0ae435d161ae6b6c96b9178f5aeda0d870857047e2e446fc1a28f14`
- ledger excerpt SHA-256: `e89519ff2099af61c68cea2151918fd61db506387b4247927daa0ac1d59d50e9`
- validator status: `FLAWED`
- process status: 1
- issue count: 8

Committed new-file SHA-256 values recorded by validation:

- validator: `d8bc0f814d2855501b599d54d691d5a7e3939a58040690e7825364823773639f`
- focused test: `b118e7ab1287a11d3fae097eea57789dd4616538672d0af06127c4348916fc74`

Not run:

- complete current-file validator execution in a checkout;
- WIKI remediation;
- broken-link checker;
- full repository pytest;
- ruff;
- data/ROOT processing;
- simulation;
- GitHub Actions.

No CI success is claimed; no status checks were attached to the validated code/test/evidence head.

## Direct-to-main commits

- `ad582c6dc09e3c790e435ebe1506963f62e2d685` — `feat(audit): validate WIKI front-door claims`
- `cd1bbb5eb2be2c1d189c0b0fbe803d4f12104294` — `test(audit): cover WIKI front-door claim consistency`
- `45aebc50067ce8f7a9c216646d12cb9e7ac24791` — `docs(validation): record WIKI claim front-door audit`
- `03bbb9df5a8b3b64fc1e3931e65fa9dea142e992` — `docs(validation): add WIKI front-door validation record`
- `57dee4451352b27fc191cbc36805a2d0316600ff` — `docs(validation): visualize WIKI claim front-door inconsistencies`
- `85e17a502949c6ccbb9875e5ca60e351ac912423` — `docs(audit): activate WIKI front-door consistency task`
- `846c1883d4a3568f177e831787216383fe3e9f54` — `docs(audit): register WIKI front-door consistency task`

All returned successful direct-main GitHub commits. A local `git push` transcript is unavailable because no checkout/network path was available; authenticated write responses and subsequent remote-main reads are the delivery evidence.

## Coordination state and next action

Updated:

- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/BACKLOG.md`

Added stable task:

- `AUD-WIKI-002`: `PARTIAL`

The next unit is to update the complete current `WIKI.md`, execute the validator against complete exact current files, run focused tests and the broken-link checker, inspect the exact diff, update the relevant claim/index/visual ledgers, and then mark the task complete only if the validator returns `VALIDATED`.

## Scientific boundary

This run did not recalculate the MV4 pull, effective live-time, pile-up rate, confidence intervals, or detector performance. It did not fill any missing uncertainty component or change the canonical claim ledger. The result is a validated documentation inconsistency and a reproducible fail-closed audit gate, not a new empirical or simulation result.
