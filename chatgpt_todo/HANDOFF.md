# Latest Scientific Review Handoff

## Session

- UTC: `2026-07-24T033502Z`
- Task: `AUD-WIKI-002`
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote main: `e8b01b4414d2a797c5f97fe3ee98f88e99ad254a`
- Validated code/test/evidence head: `57dee4451352b27fc191cbc36805a2d0316600ff`
- Remote main after concurrent work and archive, immediately before this handoff: `ba6aaa95dec282928879a6ba3ed5c1bf3df6f277`
- Destination: direct to `main`
- Acceptance: `PARTIAL`; the public WIKI inconsistency and checking tool are validated, but the complete WIKI has not yet been remediated and revalidated.

## Start-of-run and concurrent-work review

- Confirmed repository admin/push permission, default branch `main`, recent history, current coordination records, and PR #868 status.
- PR #868 remains closed, unmerged, and non-mergeable. It was not modified or merged.
- `AUD-REPO-001` remains owned by another active session and was not duplicated.
- A concurrent non-overlapping `AUD-G4-021` remediation advanced `main` during this run. Later writes incorporated its final handoff commit `6338aed736deee7ac4496981ae04da2b01722ed4`; no concurrent commit was discarded.
- No task branch, pull request, force push, history rewrite, unrelated rollback, or destructive data edit was used.
- A direct checkout was unavailable because the runtime could not resolve GitHub hosts. Exact repository text was inspected through authenticated GitHub contents/ranged reads, and repository writes were direct-main connector commits.

## Repository evidence inspected

### Public front door

- `WIKI.md`
- Git blob SHA-1: `c27a1e555145cb248e253f17a6f6d1cfe64542a8`
- Reviewed front matter, confidence-status legend, canonical results table, timing key-results table, and Monte Carlo validation matrix.

### Canonical claim state

- `docs/claim_ledger.csv`
- Git blob SHA-1: `6f4d4023814b42a566826912bcef7df9903c41e7`
- Reviewed authoritative records `CL-007` and `CL-011`.

### Coordination and history

- `chatgpt_todo/README.md`
- `MASTER_INDEX.md`
- `BACKLOG.md`
- `ACTIVE_TASK.md`
- `HANDOFF.md`
- `BLOCKERS.md`
- `CLAIM_EVIDENCE_MATRIX.md`
- recent commits and PR #868 metadata.

## Confirmed public claim-state defects

### 1. Status outside the published legend and inconsistent with the ledger

The WIKI labels the MV4 raw timing-pull claim `PASS` in three public tables:

- canonical results table;
- timing key-results table;
- Monte Carlo validation matrix.

However:

- `PASS` is not defined in the WIKI confidence-status legend;
- canonical claim-ledger record `CL-007` classifies the claim as `VALIDATED`.

Measured validator findings:

- `STATUS_OUTSIDE_LEGEND`: 3
- `STATUS_LEDGER_MISMATCH`: 3

### 2. Effective live-time truth-type mismatch

The WIKI canonical results table labels `τeff` as `data_only`. Canonical claim-ledger record `CL-011` uses `data_mc_self_consistent` and notes that the truth classification was upgraded during review.

Measured validator finding:

- `TRUTH_TYPE_LEDGER_MISMATCH`: 1

### 3. Unsupported uncertainty-completeness statement

The WIKI front matter says:

`Every number has uncertainty.`

The canonical claim ledger still contains explicit `CI_MISSING_BLOCKING` fields, including for the reviewed raw timing-pull and effective live-time records. The public sentence therefore overstates the completeness of the uncertainty inventory.

Measured validator finding:

- `OVERSTATED_UNCERTAINTY_COMPLETENESS`: 1

Total measured issues in the exact cited reconstruction: 8.

These are documentation and claim-governance defects. They do not alter the numerical values or constitute a new timing, pile-up, data, or simulation result.

## Better method and policy

Registered policy:

`WIKI_FRONT_DOOR_MUST_MATCH_CANONICAL_LEDGER`

A complete remediation must:

1. replace all three MV4 raw `PASS` labels with the canonical `VALIDATED` state;
2. align the effective live-time truth type with `data_mc_self_consistent`, using readable WIKI wording;
3. replace the blanket uncertainty statement with wording that explicitly points to unresolved ledger fields;
4. run the validator against the complete exact current WIKI and claim ledger;
5. require status `VALIDATED` before marking `AUD-WIKI-002` complete;
6. preserve the caveat that `CL-007` still lacks a complete uncertainty reconstruction despite its claim-state label.

## Added code, tests, and evidence

Added:

- `tools/audit/validate_wiki_claim_front_door.py` v1.0.0
- `tests/test_validate_wiki_claim_front_door.py`
- `docs/validation/wiki_claim_front_door_audit.md`
- `docs/validation/wiki_claim_front_door_validation.json`
- `docs/validation/wiki_claim_front_door.svg`

The validator:

- reads WIKI and ledger bytes once and records byte count and SHA-256;
- validates the claim-ledger schema and duplicate IDs;
- extracts the confidence-status vocabulary from the WIKI;
- binds the three raw-timing rows to `CL-007` and `τeff` to `CL-011`;
- checks status vocabulary, canonical state, truth type, and uncertainty-completeness wording;
- emits machine-readable JSON;
- returns 0 for `VALIDATED`, 1 for `FLAWED`, and 2 for controlled input/schema/UTF-8 errors.

The SVG explicitly labels itself as synthetic documentation/provenance evidence, not detector data, and uses text, layout, and arrows rather than color alone.

## Validation commands and results

Executed in a local reconstruction of the committed new files:

```text
python -m py_compile \
  tools/audit/validate_wiki_claim_front_door.py \
  tests/test_validate_wiki_claim_front_door.py

python -m pytest tests/test_validate_wiki_claim_front_door.py -q

5 passed in 0.03s
```

Focused coverage:

- current-like public inconsistencies produce eight expected issues;
- a corrected front door returns `VALIDATED`;
- missing required canonical claim IDs raise controlled errors;
- the CLI writes machine-readable flaw output and returns status 1;
- invalid UTF-8 returns status 2.

Exact cited reconstruction:

- WIKI excerpt SHA-256: `7ff43954b0ae435d161ae6b6c96b9178f5aeda0d870857047e2e446fc1a28f14`
- ledger excerpt SHA-256: `e89519ff2099af61c68cea2151918fd61db506387b4247927daa0ac1d59d50e9`
- status: `FLAWED`
- process status: 1
- issue count: 8

Committed new-file SHA-256 values recorded by the validation:

- validator: `d8bc0f814d2855501b599d54d691d5a7e3939a58040690e7825364823773639f`
- test: `b118e7ab1287a11d3fae097eea57789dd4616538672d0af06127c4348916fc74`

Additional passed checks:

- validation JSON parse;
- SVG XML parse;
- maximum validator line length: 91 characters;
- maximum test line length: 92 characters.

Not run:

- complete exact-file validator execution in a checkout;
- WIKI remediation;
- broken-link checker;
- full repository pytest;
- ruff;
- ROOT/data processing;
- simulation;
- GitHub Actions.

No CI success is claimed. No status checks were attached to the validated code/test/evidence head.

## Direct-to-main commit sequence

Implementation and evidence:

- `ad582c6dc09e3c790e435ebe1506963f62e2d685` — `feat(audit): validate WIKI front-door claims`
- `cd1bbb5eb2be2c1d189c0b0fbe803d4f12104294` — `test(audit): cover WIKI front-door claim consistency`
- `45aebc50067ce8f7a9c216646d12cb9e7ac24791` — `docs(validation): record WIKI claim front-door audit`
- `03bbb9df5a8b3b64fc1e3931e65fa9dea142e992` — `docs(validation): add WIKI front-door validation record`
- `57dee4451352b27fc191cbc36805a2d0316600ff` — `docs(validation): visualize WIKI claim front-door inconsistencies`

Coordination and provenance:

- `85e17a502949c6ccbb9875e5ca60e351ac912423` — `docs(audit): activate WIKI front-door consistency task`
- `846c1883d4a3568f177e831787216383fe3e9f54` — `docs(audit): register WIKI front-door consistency task`
- `ba6aaa95dec282928879a6ba3ed5c1bf3df6f277` — `docs(audit): archive WIKI front-door consistency audit`

All operations returned successful direct-main GitHub commits. A local `git push` transcript is unavailable because no checkout/network path was available; authenticated write responses and subsequent remote-main reads are the push evidence. The commit containing this handoff is the final remote-main verification target.

## `chatgpt_todo/` updates

Updated:

- `ACTIVE_TASK.md`
- `BACKLOG.md`
- `HANDOFF.md`

Added stable task:

- `AUD-WIKI-002`: `PARTIAL`

Added immutable session record:

- `chatgpt_todo/archive/2026-07-24T033502Z_AUD-WIKI-002_FRONT_DOOR_CONSISTENCY.md`

`SESSION_LOG.md` was not replaced in this session. Although a prior concurrent session reconstructed and appended its own entry from complete ranged reads, repeating a complete-file replacement while `main` was changing would add avoidable provenance-loss and lost-update risk. The immutable archive and this handoff contain the full run record; the missing append is an explicit coordination limitation to be reconciled in a byte-safe checkout or subsequent complete snapshot append.

## Scientific boundary and next action

This run did not:

- recalculate the MV4 raw pull;
- recalculate effective live-time or pile-up rate;
- complete missing confidence intervals or uncertainty components;
- process beam data or ROOT files;
- execute simulation;
- change the canonical claim ledger;
- change the public WIKI text.

`AUD-WIKI-002` remains `PARTIAL`. The next unit is to edit the complete current `WIKI.md`, run the validator against complete exact current files, execute focused tests and the broken-link checker, inspect the exact diff, update the relevant claim/index/visual ledgers, and mark the task complete only when the validator returns `VALIDATED`.
