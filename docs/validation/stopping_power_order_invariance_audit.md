# Stopping-power aggregation row-order audit

## Scope

This validation checks whether the stopping-power diagnostic produces the same grouped sufficient statistics when the same validated event multiset is written in a different CSV row order.

## Confirmed defect

The previous aggregation used repeated binary64 `+=` operations for deposited energy and track length. Floating-point addition is not associative, so physically identical event multisets could produce different `deposit_sum_MeV`, `sim_total_MeV_cm2_g`, ratios, or point-estimate classifications solely because rows were reordered.

Exact pre-change source provenance:

- Git blob: `79ea276741807d896cc6d2a99e8071605cc238f0`
- The reconstructed bytes matched this blob exactly.
- Synthetic deposits: one `1.0 MeV` value and ten `1e-16 MeV` values at one particle/energy group.
- Large-first sequential sum: `1.0 MeV`.
- Small-first sequential sum: `1.000000000000001 MeV`.
- Corresponding mass-stopping proxies at 11 mm and 1 g/cm3: `0.9090909090909092` and `0.9090909090909101 MeV cm2/g`.

The new regression against the exact old blob produced `2 failed, 1 passed`, demonstrating both the order dependence and the absence of summation provenance.

## Correction

`compare_stopping_power.py` now:

1. collects deposited-energy and track-length values per exact `(particle, energy_MeV)` group;
2. evaluates each grouped sum using `math.fsum`;
3. records `summation_method=MATH_FSUM_PER_GROUP` in every result and CSV row;
4. prints the summation method in terminal output.

The parser already materializes validated rows in memory, so the grouped lists do not change the dominant input-memory model.

## Validation

Executed on exact local reconstructions:

```text
python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tests/test_compare_stopping_power_order_invariance.py \
  tests/test_compare_stopping_power_report_precision.py \
  tests/test_compare_stopping_power_report_reproducibility.py

python -m pytest \
  tests/test_compare_stopping_power_order_invariance.py \
  tests/test_compare_stopping_power_report_precision.py \
  tests/test_compare_stopping_power_report_reproducibility.py -q

8 passed in 0.06s
```

Additional checks:

- new script Git blob: `4e45e55b48c1d51320b9e6d0959b0b8423d0b2fc`;
- new script SHA-256: `ee61e0f2a76fa2e94513d176ce7b34698acaada02d84defe480df38a2f32dd72`;
- new test SHA-256: `5607b1d0da7fec7f083462ac54b45967a4c4c9bb2d95016a4e040df3edf4ba27`;
- no changed Python line exceeded 100 characters.

## Scientific interpretation

This removes a numerical file-order artifact from the diagnostic sufficient statistics. It does not provide an uncertainty budget, validate a real Geant4 export, establish that local deposited energy equals projectile total energy loss, or demonstrate Geant4/PSTAR agreement.
