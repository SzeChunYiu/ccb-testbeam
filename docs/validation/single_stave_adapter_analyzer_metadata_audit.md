# Single-stave adapter/analyzer metadata consistency audit

**Task:** `AUD-G4-023`  
**Status:** `FLAWED` for the current adapter metadata; audit gate `VALIDATED`  
**Policy:** `ADAPTER_METADATA_MUST_MATCH_CURRENT_ANALYZER_OPTICAL_CONTRACT`

## Question

Does the metadata emitted by `adapt_geant4_events.py` accurately describe the
current downstream analyzer contract after the analyzer optical-bookkeeping
remediation?

## Repository facts

The current adapter is version 1.0.0. Its normalized table already preserves
scintillation, WLS, and Cerenkov generated-track counts, constructs
`n_optical_generated_total`, and rejects selected-end arrivals above that total.
However, its metadata still publishes:

- `analysis_compatibility = SCHEMA_ADAPTER_ONLY`; and
- a `downstream_blocker` saying that `analyze_single_stave.py` still validates
  arrivals against `n_scint_generated` alone and must be changed to use the
  total.

That statement was true when the adapter was introduced, but it is no longer
true on current `main`.

The current analyzer is version 2.0.0 under policy
`ANALYZER_MUST_PRESERVE_COMPONENT_OPTICAL_COUNTS_AND_USE_EXACT_TOTAL`. For the
current component-sum contract it returns `n_optical_generated_total` as the
arrival and collection-efficiency denominator. `EVENT_CONTRACT.md` already
states this corrected behavior.

## Confirmed defect

A successful current adapter run therefore emits a machine-readable record that
contradicts both the code that consumes its output and the repository's current
contract documentation. This is a provenance defect: a downstream reviewer or
automated gate could incorrectly infer that the normalized table remains
incompatible, while a stale blocker can hide the actual remaining boundary,
which is execution on immutable real ROOT bytes.

The exact current source inspection yields eight fail-closed findings:

1. stale compatibility label;
2. three stale-blocker statements;
3. missing analyzer version;
4. missing analyzer policy;
5. missing current optical-contract identity; and
6. missing explicit software-valid/real-ROOT-pending acceptance state.

## Better contract

The adapter metadata should be versioned and should publish:

```json
{
  "analysis_compatibility": "SCHEMA_AND_OPTICAL_BOOKKEEPING_COMPATIBLE",
  "downstream_analyzer_contract": {
    "version": "2.0.0",
    "policy": "ANALYZER_MUST_PRESERVE_COMPONENT_OPTICAL_COUNTS_AND_USE_EXACT_TOTAL",
    "optical_generation_contract": "CURRENT_COMPONENT_SUM",
    "collection_efficiency_denominator": "n_optical_generated_total",
    "acceptance": "SOFTWARE_CONTRACT_VALIDATED_REAL_ROOT_PENDING"
  }
}
```

The obsolete blocker should be removed and replaced by the actual scientific
boundary: no immutable production ROOT file has completed the full
adapter-to-analyzer path with producer sidecar, hashes, row-count closure,
result/manifest hashes, and reviewed plots.

## Validation delivered

Added a reusable strict-UTF-8 audit tool and focused regression suite. The gate
checks analyzer version/policy, total-denominator semantics, section-level
contract documentation, stale blocker phrases, required adapter metadata, exact
input byte hashes when run in a checkout, atomic JSON publication, invalid
UTF-8, and destructive output aliasing.

```text
python -m py_compile \
  tools/audit/audit_single_stave_adapter_analyzer_metadata.py \
  tests/test_audit_single_stave_adapter_analyzer_metadata.py \
  tools/audit/render_single_stave_adapter_analyzer_metadata_evidence.py

PYTHONPATH=. pytest -q \
  tests/test_audit_single_stave_adapter_analyzer_metadata.py

6 passed, 1 skipped in 1.96s
```

The skipped test is the exact-current-source integration check, because this
execution container has no complete checkout and cannot resolve `github.com`.
Exact current Git blobs and relevant line ranges are retained in the JSON. The
corrected fixture validates with zero findings; the current-like stale fixture
fails closed. JSON and SVG parsing passed, and changed Python lines are no
longer than 100 characters.

## Acceptance boundary

This unit validates the defect and the remediation gate. It deliberately does
not rewrite the adapter metadata in the same audit step. `AUD-G4-023` remains
`PARTIAL` until the adapter payload and its focused CLI regression are corrected
and the exact current-source audit returns `VALIDATED`.

No Geant4 event, ROOT file, optical yield, calibration, resolution, PID, or
detector-performance quantity was generated or changed.
