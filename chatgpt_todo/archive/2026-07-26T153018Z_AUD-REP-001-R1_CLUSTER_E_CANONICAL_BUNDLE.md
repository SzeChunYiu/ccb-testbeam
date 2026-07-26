# Cluster E canonical source-bound bundle remediation

**Task:** `AUD-REP-001-R1`  
**Policies:** `CLUSTERE_HEADLINES_MUST_BIND_CANONICAL_LEDGER_AND_FULL_PROVENANCE`; `INPUT_BYTES_MUST_MATCH_BASE_COMMIT_BLOBS`  
**Status:** `VALIDATED` for the focused public claim/provenance bundle.

## Result

The public Cluster E front door now binds the canonical ledger claims exactly: CL-013 is 92 ADC/MeV with a 28 ADC/MeV heuristic envelope and remains GATED; CL-021 is Pearson chi2/ndf 68269.40598948313 and remains FLAWED; CL-022 is 283/87555 = 0.003232254011764034 and remains TRUTH_LEVEL_MC_ONLY. The Cluster D MV3 rerun 86135.4707883642 is displayed as a distinct diagnostic that does not supersede CL-021.

Schema-3 provenance records base commit `ca71b0f0b83f5bcd189c173cf7d8e28b287bc34f`, measured and commit-tree Git blob identities, equality state, SHA-256, byte count, strict UTF-8 snapshot policy, and the authorization policy for all six inputs. The bundle was committed as `268a033e8ff586878745a34f99e844b97523a437`.

## Validation

- Exact current producer identity: Git blob `b6d98f0040864ec6f0e46edfae9ea87005d1cfcd`, 13,910 bytes, SHA-256 `230df0122c6a56cdf6a6d99870cf16e254da7467580d630363b2eeb2f681fee8`.
- Concurrent exact-source focused suite: `11 passed in 0.20s`.
- Source-faithful local producer reconstruction: `9 passed in 0.09s`.
- Exact public bundle validator: `VALIDATED: 0 finding(s)`.
- JSON and SVG parse checks passed.

The execution container could not resolve `github.com`; therefore a full-checkout producer invocation was not performed. The current producer source was reconstructed byte-exact, and public bytes were deterministically rendered from exact canonical rows and exact commit-bound source identities. This limitation is explicit and no broad CI or physics claim is inferred.

## Delivery correction

Commit `d371f63976b323b7b79804c32bc0a061e1154840` accidentally replaced the legacy validator with malformed source. Commit `12b8aaaa6dd635be999fb5395cbe61f4f81dafde` immediately restored it and installed the v2 gate before public outputs were published. No validation result relies on the malformed intermediate file.

## Scientific boundary

No ROOT data, calibration, accepted stopping-profile closure, C12 beam-data identity, PID performance, timing performance, uncertainty model, or detector-performance result was produced or validated.

## Output SHA-256

- `reports/PROJECT_DASHBOARD.md`: `cccd6cfc066fc51adfb3b9c528ef6798ab70d756e0992e587ef27cbacdd50d4b`
- `reports/studies/clusterE/SUMMARY.md`: `28af10a7144816a0a6594c5f3693197732fce074824702e5f471264da18b2f6e`
- `reports/studies/clusterE/claims_table.csv`: `da1e5cad27261e41937d39cff02687ab85b42bb74df9a878d9a3da29227b5bad`
- `reports/studies/clusterE/metrics.json`: `bd21edfb58cbdf97883103dc695a8ade296308f922031f141468b365b64bcfd9`
- `reports/studies/clusterE/provenance.json`: `75d7d04524f42105e209a86c56c725fa27ac51ea637258ac67d28506f6234d99`
- `reports/studies/clusterE/VIS-CLAIM-001_claim_dashboard.svg`: `629e364ffe2f59b4a9a48aa8dd32374844e344589dd578ab8df3c121e36ffe44`
