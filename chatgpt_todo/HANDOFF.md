# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-24T102230Z`
- **Task:** `AUD-WIKI-001`
- **Unit:** root-WIKI Rmax, duplicate-readout, and saturation-recovery fail-closed claim gate
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Initial remote `main`:** `74966884f40e6dbc8ac6243d4983eaa7dfb395ae`
- **Validated remote-main delivery head before this handoff:** `fcb3297762339a098d8a99bc7aa1c8417eb71130`
- **Destination:** direct sequential commits to `main`; no task branch, pull request, force-push, or history rewrite
- **Acceptance:** validator, focused tests, exact ledger-byte check, Markdown/JSON/SVG evidence, and immutable archive are `VALIDATED`; root `WIKI.md` remediation remains `PARTIAL`

## Start-of-run and concurrency review

Authenticated GitHub reads inspected repository metadata and permissions, recent
main history, current commit status, PR #868, `WIKI.md`,
`docs/claim_ledger.csv`, the current WIKI validator and tests, the latest
executive-summary handoff, and all mandatory `chatgpt_todo/` coordination
records. No concurrent commit appeared while the implementation and evidence
sequence was written.

PR #868 remains closed, unmerged, and non-mergeable and was not modified. No
status checks were attached to the initial or validated delivery head, so no
GitHub Actions success is inferred.

A direct clone was attempted but the runtime could not resolve `github.com`.
Repository reads and direct-main writes therefore used the authenticated GitHub
connector. Exact current ledger bytes were reconstructed locally and matched
the authenticated Git blob. The executable current-WIKI finding used an exact
claim-bearing excerpt reconstructed from authenticated line reads; it is not
claimed to be a complete local WIKI byte snapshot.

## Confirmed claim-gate bypass

`tools/audit/validate_wiki_claim_front_door.py` v1.1.0 bound only:

- `CL-007` — MV4 raw timing pull;
- `CL-011` — effective live-time.

It did not require canonical 43-column width for a bound claim and did not bind
Rmax, P04p duplicate readout, or P07e saturation recovery. A source-faithful
stale fixture returned `VALIDATED` when the new validator was deliberately
restricted to the former binding and phrase-check scope. The former gate could
therefore miss the reviewed public conflicts.

## Current public conflicts measured

The exact current claim ledger has 43 columns for all six required records:

`CL-007`, `CL-010`, `CL-011`, `CL-012`, `CL-015`, `CL-016`.

The root WIKI claim-bearing excerpt returned process status 1, `FLAWED`, with
21 findings:

- three status/ledger mismatches;
- three values published despite blank canonical values;
- three unsupported ML-win phrase findings;
- two missing canonical model rows;
- two missing WIKI statuses;
- two withheld-Rmax phrase findings;
- two missing required public caveats;
- one truth-type mismatch;
- one unresolved Rmax threshold;
- one unresolved Rmax derivation;
- one unsupported combined ML-win claim.

Specific evidence conflicts:

1. `CL-010` is `BLOCKED`, has no canonical value, and is blocked by
   `S-STAT-003`; WIKI publishes `3.044–3.05 MHz` as `VALIDATED` in two tables
   and repeats `mu_max = 0.38` plus the derived 3.04 MHz value.
2. `CL-012` is `SUPERSEDED` with no accepted value; WIKI presents
   approximately 3.05 MHz as the new canonical value.
3. `CL-015` is `GATED` because the P04p accepted-coverage interval crosses the
   selection threshold; WIKI still describes duplicate readout as an ML-win or
   confirmed-win domain.
4. `CL-016` is `GATED`; P07e external held-out duplicate closure is worse for
   ML than raw and producer bytes are unbound; WIKI still describes saturation
   recovery as an ML-win or promising domain.

## Correction delivered

Upgraded `tools/audit/validate_wiki_claim_front_door.py` to **v1.2.0** with
policy:

```text
WIKI_FRONT_DOOR_MUST_MATCH_EXACT_WIDTH_CANONICAL_CLAIMS
```

The validator now:

- requires exactly 43 unique ledger columns;
- refuses to interpret a required claim unless that row is exactly 43 columns;
- binds `CL-007`, `CL-010`, `CL-011`, `CL-012`, `CL-015`, and `CL-016`;
- checks public status and truth-type alignment;
- rejects unit-bearing Rmax values when the canonical value is withheld;
- rejects the stale Rmax threshold and derivation;
- rejects combined or domain-level ML-win wording;
- requires explicit statements that Rmax is withheld pending S-STAT-003 and
  that no production duplicate-readout model or saturation correction is
  authorized.

Added or updated:

- `tools/audit/validate_wiki_claim_front_door.py`;
- `tests/test_validate_wiki_claim_front_door.py`;
- `docs/validation/wiki_rmax_ml_claim_gate_audit.md`;
- `docs/validation/wiki_rmax_ml_claim_gate_validation.json`;
- `docs/validation/wiki_rmax_ml_claim_gate.svg`;
- `chatgpt_todo/ACTIVE_TASK.md`;
- `chatgpt_todo/archive/2026-07-24T102230Z_AUD-WIKI-001_ROOT_RMAX_ML_GATE.md`;
- this handoff.

## Validation performed

```text
python -m py_compile \
  tools/audit/validate_wiki_claim_front_door.py \
  tests/test_validate_wiki_claim_front_door.py

python -m pytest tests/test_validate_wiki_claim_front_door.py -q

10 passed in 0.04s
```

Additional validated checks:

- exact ledger Git blob:
  `853d955f449268ec614ac61f33f243d30cf473e0`;
- ledger bytes: `12077`;
- ledger SHA-256:
  `c0e283e6d43a1013a9565f2697c4f99f7b47d639245b9926a8ddc83786602e19`;
- committed validator blob:
  `6ae2df1018abde8d93a7bb04d787786ade95622a`;
- committed test blob:
  `ecaa4acd6d46e56861c83a32b071678cf4f3960f`;
- validation JSON parsed;
- SVG parsed as XML;
- maximum changed Python line lengths: 91 and 98 characters.

Full repository pytest, ruff, complete broken-link checking, ROOT processing,
model reruns, Rmax physics derivation, and GitHub Actions were not run.

## Direct-to-main commit and push sequence

Each authenticated connector write returned a successful direct-main commit:

1. `b088178443f68691dec285bcf4a098dc1553fd71` — `fix(audit): gate root WIKI Rmax and ML claims`
2. `c9ad71b03765f32a11d7bf82a847c780503150cc` — `test(audit): cover exact-width WIKI claim gate`
3. `f8ae60d70e8152e924e052ddc69baebeafda85c2` — `docs(validation): record root WIKI claim-gate audit`
4. `7aecb8dbd631b6eb27aaca6d364cf7dbc05ec6d7` — `docs(validation): add root WIKI claim-gate record`
5. `a13cc69c69d0119ffc93993b87d9dfe116a95eda` — `docs(validation): visualize root WIKI claim gate`
6. `a222221cac062e0f07d35fb7b3618ac59af949e1` — `docs(audit): track root WIKI claim gate`
7. `fcb3297762339a098d8a99bc7aa1c8417eb71130` — `docs(audit): archive root WIKI claim gate`

A post-write remote history read confirmed these commits consecutively on
remote `main`, with `fcb3297762339a098d8a99bc7aa1c8417eb71130`
as the delivery head before this handoff update.

## Scientific boundary and unresolved risk

This documentation-governance unit does **not**:

- determine an accepted Rmax;
- resolve S-STAT-003;
- select a P04p production model;
- authorize the P07e saturation correction;
- regenerate detector data, simulation, fit, uncertainty interval, calibration,
  or detector-performance results.

The root WIKI itself was not rewritten. `AUD-WIKI-001` therefore remains
`PARTIAL`. `CL-010` remains `BLOCKED`; `CL-012` remains `SUPERSEDED`; `CL-015`
and `CL-016` remain `GATED`.

`SESSION_LOG.md` was not replaced because the connector exposes whole-file
replacement rather than a byte-safe append operation and a complete current
byte snapshot was not safely assembled. Replacing the append-only file from
partial ranged reads could destroy prior provenance. The complete run is
retained in the immutable archive and this handoff.

## Next validated unit

1. Retrieve the exact complete current `WIKI.md` from latest `origin/main`.
2. Withhold every numerical Rmax pending S-STAT-003 and retain 3.0448717948717947
   MHz only in explicitly superseded correction history.
3. Replace combined/domain ML-win wording with separate P04p and P07e `GATED`
   statements and their exact limitations.
4. State that no production duplicate-readout model or saturation correction is
   authorized.
5. Run validator v1.2.0 against the exact complete WIKI and ledger, focused
   tests, and the broken-link checker.
6. Require validator status `VALIDATED` before closing `AUD-WIKI-001`.
