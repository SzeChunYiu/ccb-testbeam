# P04p winner robustness and CL-015 ledger reconstruction

## Scope

This audit reviews the B2 duplicate-readout harm-veto benchmark behind malformed claim-ledger row `CL-015`. It does not rerun ROOT processing or designate a production model. It checks the reported winner-selection rule against the run-block bootstrap coverage intervals already committed by the study and reconstructs `CL-015` to the canonical 43-column schema without promoting the claim beyond `GATED`.

## Exact repository evidence

- `docs/claim_ledger.csv` pre-change Git blob: `009f48e218b2439f80b2cebf8ebb06a845488089`
- P04p report Git blob: `b9029f1c7f8d8d87499b8a7a88d807692b56ae71`
- P04p result Git blob: `e2c75352b5c66f70923ef525d8251be3af9cfdc8`
- P04p manifest Git blob: `00b244470bb9dbd4060769e69e720b79c07f756d`
- P04p producer Git blob: `6f3bbf1638b8729e425088e6b1f8a0663b3a5615`
- P04p config Git blob: `d11592ba547a7028527dea3ac5fc3329362cb9a4`
- Manifest/source commit: `c31b40fdadff23272b13e3824e769f518c53b38e`

The report defines the winner as the method with accepted coverage at least `0.50`, followed by minimum accepted charge res68, timing abs68, and calibration ECE. The script implements that gate using the point estimate of accepted coverage.

## Measured winner instability

The reported gradient-boosted-tree point has:

- accepted coverage: `0.5016432417313474`;
- run-block-bootstrap 95% interval: `[0.4781032287979763, 0.5382552094265317]`;
- accepted charge res68: `0.03902452880489024`.

Its point estimate is only `0.001643` above the hard 0.50 coverage threshold, while the interval crosses below that threshold. The result JSON does not declare whether eligibility is controlled by the point estimate, a confidence bound, or another uncertainty rule.

A conservative sensitivity check that requires the lower 95% coverage bound to satisfy the same 0.50 gate excludes the reported winner. Under that sensitivity rule, the MLP is the first eligible method:

- accepted coverage: `0.5470846194571808`;
- lower 95% bound: `0.5225633159229767`;
- accepted charge res68: `0.04055070702536622`.

This does **not** establish the MLP as the canonical winner. The lower-bound rule was not recorded as the preregistered selection contract. It demonstrates that the winner claim is sensitive to an unspecified treatment of uncertainty at the hard coverage boundary.

## Better method

Before selecting or deploying a harm-veto model, freeze one uncertainty-aware coverage contract, for example:

1. require the lower bound of a preregistered run-level interval to exceed the minimum coverage;
2. use constrained selection with a prespecified probability of satisfying the coverage requirement;
3. reserve independent runs or a cross-stave transfer sample for final model choice after tuning;
4. report the full selection path and multiplicity/model-family search;
5. repeat on B4/B6/B8 and on new runs because the current closure target is B2-only and is not truth energy.

The policy registered by this audit is:

```text
COVERAGE_GATE_MUST_USE_PREDECLARED_UNCERTAINTY_RULE
```

## Ledger correction

`CL-015` had 36 fields under a 43-column header. It is reconstructed to exactly 43 fields with:

- metric: B2 accepted charge res68 for the reported GBT veto;
- central value: `0.03902452880489024`;
- run-block-bootstrap 95% interval: `[0.03566372530746706, 0.042719761350795714]`;
- events: `100107`;
- evaluation runs: `8`;
- traditional-rule baseline: `0.07854122474166687`;
- delta versus baseline: `-0.03951669593677663`;
- truth type: `data_external_duplicate_readout`;
- status: `GATED`;
- blocker: `BLK-P04P-001`.

The ledger schema state advances from 5/26 to 6/26 exact-width rows; 20 rows remain withheld because of width mismatch.

## Reproducible validation

Commands:

```text
PYTHONPATH=. python -m py_compile \
  tools/audit/audit_p04p_winner_robustness.py \
  tests/test_audit_p04p_winner_robustness.py \
  tests/test_claim_ledger_p04p_row.py

PYTHONPATH=. python -m pytest \
  tests/test_audit_p04p_winner_robustness.py \
  tests/test_claim_ledger_p04p_row.py -q
```

Result:

```text
6 passed in 1.14s
```

The source-faithful current-like fixture returns `FLAWED` with two findings:

- `COVERAGE_GATE_UNCERTAINTY_POLICY_MISSING`;
- `WINNER_CHANGES_UNDER_CI_LOWER_BOUND_GATE`.

The corrected synthetic contract returns `VALIDATED`. The exact validated code blobs are `faea3340ef55b9e1fd5f84c1813d65e88d4cce2a` (auditor), `c913edafb1f65ca8c8fb58f5e61fedfe6a2565a0` (audit tests), and `0a762b80f477f897cd6dbdba9fea22d38cf0318b` (ledger-row test). The generated JSON files parse, both SVG files parse as XML, and `CL-015` is exactly 43 fields.

## Scientific boundary

No raw ROOT file, waveform, classifier, bootstrap ensemble, cross-stave transfer sample, or new detector result was generated. The committed P04p point estimates and intervals are treated as repository facts. The new SVG is a software-method visualization of those committed metrics, not detector-response evidence. The B2 harm-veto claim remains `GATED` pending a preregistered uncertainty-aware selection rule and independent transfer validation.
