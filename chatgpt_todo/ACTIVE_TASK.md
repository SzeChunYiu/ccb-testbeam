# Active Task

- **Task ID:** AUD-I885-002
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-23T14:23:31Z
- **Initial main SHA:** `27993fce7556e65decf8c760ac6f3a9d2928e0c7`
- **Implementation/evidence head:** `84e901c0f0e649b2a635b4ff567b2ce4464c9690`
- **Scope:** correct issue #885 calibration-fit independence, regenerate the committed partial fit bundle from one seed-averaged point per energy, evaluate the straight-line model with residual diagnostics, and provide reproducible visual evidence.
- **Confirmed defects:** legacy P5/P5b fits counted seed files as independent observations; deuteron lines had zero residual degrees of freedom after seed averaging; R-squared alone hid severe proton nonlinearity relative to the recorded statistical errors.
- **Validated change:** added `scripts/single_stave/refit_i885_campaign.py` and six focused regression tests; replaced legacy fit records with accepted/rejected/skipped states; recorded seed-averaged points; generated a labelled SVG; corrected summary and invalidation wording.
- **Measured result:** no fit is accepted. Both deuteron fits are skipped at two independent energies. Proton SiPM and Birks-visible linear models are rejected with reduced chi-square 357.99 and 33391.66 for three residual degrees of freedom; the SiPM p-value is `1.62e-232` and the Birks-visible p-value underflows double precision.
- **Commands:** `python -m py_compile scripts/single_stave/refit_i885_campaign.py tests/test_refit_i885_campaign.py`; `python -m pytest tests/test_refit_i885_campaign.py -q`; refit CLI against the exact committed CSV; JSON/XML, line-length, deterministic-SVG, and Git-blob checks.
- **Validation:** focused tests returned `6 passed`; exact input CSV SHA-256 is `1a712157f1cba06f9d3b3847217c381c31bdc581337612c92b02ccc82a1691d4`; generator returned `status=PARTIAL accepted=0 rejected=2 skipped=2`.
- **Boundary:** no Geant4 or ROOT processing was rerun and no real-data calibration was performed. The goodness-of-fit test assumes independent Gaussian combined uncertainties and no systematic/model term. A replacement nonlinear or restricted-range response remains unselected and unvalidated.
- **Status:** COMPLETE for seed-independence correction, partial-bundle regeneration, model rejection, focused tests, visual evidence, and direct-to-main delivery; PARTIAL / BLOCKED for a scientifically accepted calibration function and complete campaign coverage.
