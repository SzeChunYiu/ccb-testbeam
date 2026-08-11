# Raw→sorted waveform-word closure — issue #953

**Schema:** `ccb-raw-sorted-word-closure/1`

Scalar `hrdMax` / selected-count agreement is recorded as
`INCOMPLETE_SCALAR_PROXY` and is **non-authorising**.

Authorising production requires exact per-word equality of preserved ADC traces
(or an explicit irreversible-transform contract — not implemented here).

Machine API: `ccb_mc_validation.daq.raw_sorted_closure`.
Adversarial fixtures in that module must fail while scalar counts can remain
unchanged.
