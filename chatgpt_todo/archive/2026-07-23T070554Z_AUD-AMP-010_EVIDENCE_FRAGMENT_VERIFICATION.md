# Immutable Session Record — AUD-AMP-010

## Session identity

- UTC: 2026-07-23T07:05:54Z
- Owner: scheduled ChatGPT audit session
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote `main`: `7021e5491fc60ae2f59645ffb62f156d578b0947`
- Validated code/test head: `357153ad421d47b98cdbca17d4f3aacc169142ee`
- Delivery target: direct to `main`

## Start-of-run inspection

- Attempted a direct clone; DNS resolution for `github.com` failed, so authenticated GitHub connector reads and writes were used.
- Confirmed the current main head and recent commit sequence before editing.
- Inspected PR #868: closed, not merged, non-mergeable, head `7992aa318b6f13b5f4bcbd828ad97996075fed4b`; no merge or reopen was attempted.
- Inspected the open PR inventory for concurrent work.
- Read `tools/audit/validate_amplitude_evidence_map.py`, `tools/audit/amplitude_convention_audit.py`, focused evidence tests, and the required `chatgpt_todo/` coordination files.

## Confirmed defect

Validator v1.2.0 split `evidence_reference` at `#` only to locate the supporting file. It hashed and verified the file bytes but ignored the fragment. Therefore a record such as:

```text
producer_contract.md#claim-that-does-not-exist
```

was accepted whenever `producer_contract.md` existed and its SHA-256 matched. The stored reference looked claim-specific, but the claimed location was not demonstrated to exist. This weakened reproducibility and allowed decorative fragments to masquerade as claim-level provenance.

## Corrective method

`tools/audit/validate_amplitude_evidence_map.py` is now v1.3.0.

- Whole-file references remain valid.
- Optional fragments must be canonical GitHub-style line references:
  - `#L<start>`
  - `#L<start>-L<end>`
- Start and end must be positive integers.
- End must not precede start.
- The referenced end line must exist in the measured supporting artifact.
- Empty, semantic-only, malformed, reversed, or out-of-range fragments fail closed.
- Normalized records now include:
  - `evidence_reference_file`
  - `evidence_reference_scope`
  - `evidence_reference_line_start`
  - `evidence_reference_line_end`
  - `evidence_reference_line_count`
  - `evidence_reference_fragment_verified`
  - `evidence_validator_version`
- CLI output includes `n_verified_line_fragments`.

The convention auditor consumes the shared validator, so invalid fragments are rejected before physics authorization.

## Regression coverage

Updated:

- `tests/test_amplitude_evidence_integration.py`

Added:

- `tests/test_amplitude_evidence_reference_fragments.py`

Coverage includes:

- exact single-line and multi-line references;
- whole-file references;
- empty fragments;
- semantic-only fragments;
- zero line numbers;
- reversed ranges;
- malformed ranges;
- ranges beyond the supporting artifact;
- propagation of verified scope and bounds into auditor output.

## Validation executed

Exact local reconstruction used the GitHub file contents and matched returned Git blob SHAs for the updated validator and integration test.

```text
python -m py_compile \
  tools/audit/validate_amplitude_evidence_map.py \
  tools/audit/amplitude_convention_audit.py \
  tests/test_validate_amplitude_evidence_map.py \
  tests/test_amplitude_evidence_reference_fragments.py \
  tests/test_amplitude_evidence_integration.py

python -m pytest \
  tests/test_validate_amplitude_evidence_map.py \
  tests/test_amplitude_evidence_reference_fragments.py \
  tests/test_amplitude_evidence_integration.py -q

36 passed in 0.06s
```

A changed-file scan found no lines longer than 100 characters. Ruff was not installed. The complete repository suite and GitHub Actions were not run. GitHub reported no status checks or workflow runs for the code/test head.

## Direct-to-main commits

- `816af6419517ffbe5a189630b1b8a66a78f12de0` — `fix(audit): verify evidence reference line ranges`
- `8e71aea1fb59218f711cab4bd69e42153a43f1db` — `test(audit): require verifiable evidence line fragments`
- `357153ad421d47b98cdbca17d4f3aacc169142ee` — `test(audit): cover evidence reference line ranges`
- `16f4a8c3a1d6cd746f945cf9f76db368d3493d1d` — `docs(audit): claim evidence fragment verification`
- `9a364cc7f939016406b0bc01b5b400847c626a5a` — `docs(audit): track evidence fragment verification`
- `9ad3fcfea422884c8b4074af5365f3c1de624a32` — `docs(audit): index evidence fragment traceability`
- `6707e184cf6950ff34fcad78573308035a7f641a` — `docs(audit): map evidence fragments to physics authorization`
- `e9da4932dab8c6989ac2729a8c1876c98b87140e` — `docs(audit): refine amplitude evidence blocker`

No force push or history rewrite was used.

## Scientific boundary

No real A-002 pulse table or supporting evidence artifact was available. This session does not determine whether A-002 `amplitude_adc` is absolute or net and does not claim corrected stopping counts, fractions, CSV, DeltaE-E figure, calibration, or detector performance. Historical A-002 outputs remain quarantined under `BLK-AMP-001`.

## Acceptance state and next action

- Supporting-file byte verification: VALIDATED by prior focused regression.
- Evidence line-fragment existence gate: VALIDATED by focused synthetic regression.
- Full repository lint/tests/CI: NOT RUN.
- Real A-002 amplitude convention and regenerated outputs: BLOCKED.

Obtain the exact A-002 table and supporting artifact. Create a map containing both SHA-256 values, an accepted evidence basis, and either a whole-file reference or the exact supporting `#L<start>[-L<end>]` range. Run the validator and full-table auditor without `--max-rows`; regenerate quarantined outputs only after all warnings are resolved and `physics_acceptance=ACCEPTABLE`.
