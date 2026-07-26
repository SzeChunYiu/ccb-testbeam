# AUD-REP-002 — Cluster E input/base-commit binding

- **Stamp:** `2026-07-26T150519Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `f30ff1100592e06396598ebf6975afa88e84444f`
- **Policy:** `INPUT_BYTES_MUST_MATCH_BASE_COMMIT_BLOBS`
- **Status:** `COMPLETE`

## Finding

The canonical Cluster E producer read input bytes and later hashed the live path.
It did not prove that the retained bytes equalled `base_commit:path`. A path
replacement could split parsed content from the recorded Git blob identity, and a
dirty but semantically valid worktree input could be published under a clean base
commit.

## Correction

The producer now calculates the Git blob SHA-1 from the retained input bytes and
requires equality with `git rev-parse <base_commit>:<path>`. Provenance schema 3
records the per-input commit, expected commit blob, measured retained-byte blob,
exact equality state, SHA-256, byte count, snapshot policy, and authorization policy.
Validator v2.1.0 rejects legacy or mismatched provenance.

## Validation

```text
python -m py_compile \
  scripts/clusterE/clusterE_canonical_frontdoor.py \
  tools/audit/validate_clusterE_canonical_binding_v2.py \
  tests/test_clusterE_canonical_frontdoor.py \
  tests/test_validate_clusterE_canonical_binding_v2.py \
  tools/audit/render_clusterE_input_commit_binding_evidence.py

PYTHONPATH=. pytest -q \
  tests/test_clusterE_canonical_frontdoor.py \
  tests/test_validate_clusterE_canonical_binding_v2.py

11 passed in 0.20s
```

The deterministic dirty-input and replacement-after-snapshot controls fail closed.
The evidence JSON is `VALIDATED` with zero findings and the SVG parses as XML.

## Delivered files

- `scripts/clusterE/clusterE_canonical_frontdoor.py`
- `tests/test_clusterE_canonical_frontdoor.py`
- `tools/audit/validate_clusterE_canonical_binding_v2.py`
- `tests/test_validate_clusterE_canonical_binding_v2.py`
- `tools/audit/render_clusterE_input_commit_binding_evidence.py`
- `docs/validation/clusterE_input_commit_binding_validation.json`
- `docs/validation/clusterE_input_commit_binding.svg`
- `docs/validation/clusterE_input_commit_binding_audit.md`

## Direct-main implementation sequence

- `d4ae31bbe2c5065b7904ee1c93273204240f7a3e` — bind retained inputs to the base commit;
- `75144e43bd69040b80743bd29b787dd5a621f594` — producer regressions;
- `a77e1853c5658c62aa9dd4d7f13f5330d4e11584` — provenance validator gate;
- `0c084bb821a6c4e630068f1f7a22002fd168f487` — validator regressions;
- `bbfe1cb0b79f83bd2d334a2a987149ba5b1ed9eb` — evidence renderer;
- `35340e6d8852f5f540b0dbe3ad3c1704d6d4438f` — validation JSON;
- `dffcfd2c172a23edc20087f206ded7ddef22c593` — SVG evidence;
- `0938e1a907d37ae33a0dcce4dffc4d7481515f4f` — audit report.

## Scientific boundary

No scientific central value, calibration, stopping-profile closure, C12 identity,
data/MC transfer, uncertainty, or detector-performance result was recalculated or
validated. A complete clean-checkout regeneration of the public schema-3 Cluster E
bundle remains a separate execution task.

Repository-wide pytest, ruff, ROOT processing, link checking, the paper build, and
GitHub Actions were not run. PR #939 remains unmerged and PR #868 remains closed and
unmerged.
