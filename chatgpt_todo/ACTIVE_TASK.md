# Active Task

- **Task ID:** AUD-I885-002
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-23T14:23:31Z
- **Initial main SHA:** `27993fce7556e65decf8c760ac6f3a9d2928e0c7`
- **Implementation/evidence head:** `5c025154300ec7779d7d03cc944e922ebfdd9dff`
- **Scope:** correct issue #885 calibration-fit independence, regenerate the committed partial fit bundle from one seed-averaged point per energy, evaluate the straight-line model with residual diagnostics, and provide a byte-reproducible visual artifact.
- **Confirmed defects:** legacy P5/P5b fits counted seed files as independent observations; deuteron lines had zero residual degrees of freedom after seed averaging; R-squared alone hid severe proton nonlinearity relative to recorded statistical errors; the first compact SVG lacked an explicit committed canonical renderer.
- **Validated change:** added `refit_i885_campaign.py`, deterministic `render_i885_refit_svg.py`, and nine focused regression tests; replaced legacy fit records with accepted/rejected/skipped states; recorded seed-averaged points; generated a labelled byte-reproducible SVG; corrected summary/invalidation wording and all relevant audit ledgers.
- **Measured result:** no fit is accepted. Both deuteron fits are skipped at two independent energies. Proton SiPM and Birks-visible linear models are rejected with reduced chi-square 357.99 and 33391.66 for three residual degrees of freedom; the SiPM p-value is `1.62e-232` and the Birks-visible p-value underflows double precision.
- **Commands:** compile both tools/tests; focused combined pytest; refit exact committed CSV; canonical renderer; byte comparison; SHA-256/XML, deterministic-render, line-length, and Git-blob checks.
- **Validation:** combined focused tests returned `9 passed in 1.04s`; exact input CSV SHA-256 is `1a712157f1cba06f9d3b3847217c381c31bdc581337612c92b02ccc82a1691d4`; refit returned `accepted=0 rejected=2 skipped=2`; canonical SVG matched byte-for-byte with SHA-256 `725b592d9d217f43cf8624ca7682575a35cf5f4f1ec06d9ea7266a7a4f8a3332`.
- **Boundary:** no Geant4 or ROOT processing was rerun and no real-data calibration was performed. The goodness-of-fit test assumes independent Gaussian combined uncertainties and no systematic/model term. A replacement nonlinear or restricted-range response remains unselected and unvalidated.
- **Status:** COMPLETE for seed-independence correction, partial-bundle regeneration, linear-model rejection, focused tests, byte-reproducible visual evidence, and direct-to-main delivery; PARTIAL / BLOCKED for a scientifically accepted calibration function and complete campaign coverage.
