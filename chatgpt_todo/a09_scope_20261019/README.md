A09 (2026-10-19): scientific publication remains NOT_AUTHORIZED.

Confirmed text contradiction: chapter 09 describes E_raw as evaluating the E_vis-fitted PE calibration against E_raw, but the source fits PE separately against each training target. Nominal E_vis slope/intercept: 11.769423738661718 / 0.49049523285773405. E_raw slope/intercept: 7.473050355804283 / 49.00038173026658. Both use n_train=6000 and n_heldout=4000. The reported E_raw metrics cannot be interpreted as an E_vis-calibration-on-E_raw evaluation. Repair that caption and retain GATED state.
