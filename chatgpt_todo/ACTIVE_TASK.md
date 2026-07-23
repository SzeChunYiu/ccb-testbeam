# Active Task

- **Task ID:** AUD-DELTAE-002
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-23T08:04:59Z
- **Base main SHA:** `7d226ec55a640c5ac4c9e16d378f496ea808ef0a`
- **Scope:** remove polarity ambiguity from the A-002 absolute-ADC conversion before any stopping-layer or ΔE–E rerun.
- **Assumption under test:** `abs(amplitude_adc - baseline_adc)` is an acceptable conversion once a table is classified as absolute ADC code.
- **Confirmed finding:** absolute/net convention does not identify pulse polarity. The prior absolute-value conversion silently mapped either side of the pedestal to positive energy and could turn a polarity mismatch into a threshold-passing deposit.
- **Files:** `scripts/single_stave/deltaE_E_data_bridge.py`, `tests/test_deltae_data_bridge_composite_key.py`, and `chatgpt_todo/` coordination records.
- **Change:** absolute input now requires explicit `amplitude_polarity` (`positive` or `negative`), uses the corresponding signed pedestal subtraction, rejects opposite-polarity rows and nonfinite conversion inputs, and records polarity plus the exact transformation in result metadata.
- **Validation plan executed:** compile the modified bridge and test module; run the focused pytest module; scan both files for lines over 100 characters; compare local Git blob hashes with GitHub content SHAs; inspect current-main commit order.
- **Validation result:** `10 passed in 2.78s`; compilation and line-length scan passed; local blob hashes exactly matched GitHub content SHAs `7f50ce667a6cde07e94717d0187831da4d8459ac` and `3b59a793f5d67e6a0d3c7117c42ec41ad7b84a90`. Full repository tests, ruff, real-data rerun, and GitHub Actions were not run and are not claimed.
- **Boundary:** no exact A-002 table or hash-bound polarity evidence was available. No stopping distribution, event CSV, ΔE–E plot, calibration, or detector-performance result was regenerated.
- **Status:** PARTIAL — polarity-safe code and focused synthetic regression are validated; real A-002 polarity authorization and output regeneration remain BLOCKED.
