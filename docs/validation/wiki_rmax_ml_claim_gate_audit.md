# Root WIKI Rmax and ML claim gate audit

## Scope

This unit reviews public claim governance in `WIKI.md` against the exact current
`docs/claim_ledger.csv`. It does not recalculate pile-up physics, train a model,
or analyze detector data. The exact current ledger bytes were reconstructed and
matched to Git blob `853d955f449268ec614ac61f33f243d30cf473e0`.
Authenticated GitHub line reads were used to reconstruct the exact WIKI rows and
sentences bearing the Rmax, duplicate-readout, and saturation-recovery claims.

Direct checkout was attempted but unavailable because the runtime could not
resolve `github.com`. Consequently, executable current-state validation used the
exact claim-bearing WIKI excerpt rather than claiming a complete local WIKI byte
snapshot. The root WIKI remains unchanged in this unit.

## Confirmed gate bypass

Validator v1.1.0 bound only `CL-007` and `CL-011`. It did not require the
canonical 43-column width for a bound row and did not bind the public Rmax,
P04p, or P07e statements. A source-faithful stale fixture therefore returned
`VALIDATED` when evaluated under the former binding scope.

The current public WIKI still conflicts with exact-width canonical records:

1. `CL-010` is `BLOCKED`, has no canonical value, and is blocked by
   `S-STAT-003`; the WIKI publishes `3.044–3.05 MHz` as `VALIDATED` in two
   tables and repeats a `mu_max = 0.38` derivation.
2. `CL-012` is `SUPERSEDED` and has no accepted value; the historical table
   presents approximately 3.05 MHz as the new canonical value.
3. `CL-015` is `GATED` because the reported GBT accepted-coverage interval
   crosses the selection threshold; the WIKI still calls duplicate readout an
   ML-win domain.
4. `CL-016` is `GATED`; external duplicate closure is worse for ML than raw and
   the producer bytes are unbound. The WIKI still calls saturation recovery an
   ML-win or promising domain.

The exact claim-bearing excerpt produced 21 findings. These include three
status mismatches, three values published despite a blank canonical value,
three unsupported ML-win phrase findings, two missing canonical model rows,
two missing statuses, two withheld-Rmax phrase findings, and two missing public
caveats.

## Better method

`tools/audit/validate_wiki_claim_front_door.py` v1.2.0 implements:

`WIKI_FRONT_DOOR_MUST_MATCH_EXACT_WIDTH_CANONICAL_CLAIMS`

The gate now:

- requires the ledger header to contain exactly 43 unique columns;
- refuses to interpret any required claim row unless it also has exactly 43
  columns;
- binds `CL-007`, `CL-010`, `CL-011`, `CL-012`, `CL-015`, and `CL-016`;
- checks public status and truth-type alignment;
- rejects an Rmax unit-bearing value when the canonical value is withheld;
- rejects the stale Rmax threshold and derivation;
- rejects combined or domain-level ML-win wording;
- requires explicit statements that Rmax is withheld and that neither a
  production duplicate-readout model nor saturation correction is authorized.

## Reproducible validation

```text
python -m py_compile \
  tools/audit/validate_wiki_claim_front_door.py \
  tests/test_validate_wiki_claim_front_door.py

python -m pytest tests/test_validate_wiki_claim_front_door.py -q

10 passed in 0.04s
```

The focused suite covers the current Rmax/ML overclaims, a corrected state,
missing claims, 42- and 44-column required rows, a 42-column header, controlled
CLI status, invalid UTF-8, and an explicit former-v1.1-scope negative control.
The machine-readable record is
`docs/validation/wiki_rmax_ml_claim_gate_validation.json` and the visual summary
is `docs/validation/wiki_rmax_ml_claim_gate.svg`.

## Acceptance boundary

The validator, focused tests, exact ledger-byte check, current-state finding
record, and remediation contract are validated. `AUD-WIKI-001` remains
`PARTIAL`: the complete root WIKI has not yet been rewritten and validated as a
full exact byte snapshot. No Rmax value, P04p winner, P07e correction, detector
calibration, or detector-performance result is authorized by this audit.
