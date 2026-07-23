# AUD-DELTAE-002 — absolute pulse-polarity gate

## Session

- UTC: `2026-07-23T08:04:59Z`
- Initial remote `main`: `7d226ec55a640c5ac4c9e16d378f496ea808ef0a`
- Repository: `SzeChunYiu/ccb-testbeam`
- Owner: scheduled ChatGPT audit session
- Destination: direct to `main`

## Start-of-run inspection

- Confirmed push/admin access, current `main`, recent commit history, and no concurrent main update before code writes.
- Inspected PR #868: closed, not merged, non-mergeable, head `7992aa318b6f13b5f4bcbd828ad97996075fed4b`; no merge or reopen was attempted.
- Inspected open PRs. PR #881 modifies only separate single-stave review/handoff documents and does not touch the bridge or its regression test.
- Read the A-002 bridge, focused test, pulse-table contract, current audit handoff, backlog, master index, code-result map, blockers, and session log.
- A direct clone failed with `Could not resolve host: github.com`; authenticated GitHub connector reads/writes and exact local reconstructions were used.

## Confirmed defect

`scripts/single_stave/deltaE_E_data_bridge.py` converted absolute ADC codes with:

```python
df[signal_column] = (df[ampcol] - df["baseline_adc"]).abs()
```

Absolute/net convention does not determine pulse polarity. Taking `abs` accepts both sides of the pedestal and can turn an opposite-polarity excursion, wrong convention, or malformed pedestal relation into a positive signal that passes the 200 ADC stopping threshold. The existing test itself encoded below-pedestal absolute codes while the canonical contract describes an above-pedestal `peak_code_adc`, demonstrating that polarity was not represented explicitly.

## Change

- Added required `amplitude_polarity="positive"|"negative"` for absolute input.
- Positive-going conversion uses `amplitude - baseline`.
- Negative-going conversion uses `baseline - amplitude`.
- Removed the polarity-blind absolute value.
- Opposite-polarity rows fail closed.
- Nonnumeric/nonfinite absolute amplitude or baseline rows fail closed.
- Supplying polarity for a net field is rejected.
- Result metadata records `amplitude_polarity` and the exact signed formula.
- Composite-key and stopping-bin cardinality invariants are unchanged.

## Regression validation

Executed on exact local files later matched to the GitHub content blobs:

```text
python -m py_compile \
  scripts/single_stave/deltaE_E_data_bridge.py \
  tests/test_deltae_data_bridge_composite_key.py

python -m pytest tests/test_deltae_data_bridge_composite_key.py -q

10 passed in 2.78s
```

The focused tests cover composite-key cardinality, ambiguous convention rejection, required polarity, positive- and negative-going signed conversion, opposite-polarity rejection, nonfinite rejection, net pass-through, missing baseline, and multiple explicit amplitude fields. A line-length scan found no lines over 100 characters.

Local Git blob hashes matched the connector-returned content SHAs:

- bridge: `7f50ce667a6cde07e94717d0187831da4d8459ac`
- test: `3b59a793f5d67e6a0d3c7117c42ec41ad7b84a90`

Full repository tests, ruff, real-data analysis, and GitHub Actions were not run and are not claimed.

## Direct-to-main commits before archive/log/handoff

- `4fc261dc83c5463c23392f6cf71e04735471ee2c` — `fix(deltae): require explicit absolute pulse polarity`
- `dd7ffbba6da463e1c63a9a7c71bd43f33f23f147` — `test(deltae): cover absolute pulse polarity gate`
- `e15fe84827a6c2901e08326d9fbab0cfc6fe3020` — `docs(audit): claim A-002 pulse polarity gate`
- `4ac3b109d0a53bc75f82f3bf0b2d55d2a0976449` — `docs(audit): track A-002 pulse polarity gate`
- `7e6d89efa7d24ca477566722e35a61e583b373b7` — `docs(audit): index A-002 pulse polarity risk`
- `bbd16416641158de1346d39a5abc499a004848d7` — `docs(audit): map A-002 polarity to stopping outputs`
- `65f083907cb08736f87212051e5375dbeb29e4f5` — `docs(audit): refine A-002 amplitude blocker with polarity`

## Scientific boundary

No exact A-002 pulse table or immutable polarity evidence was available. This session does not claim that A-002 is absolute or net, positive- or negative-going, or that any historical stopping count, fraction, CSV, or ΔE–E plot is correct. Historical outputs remain quarantined under `BLK-AMP-001`.

## Next action

Obtain and hash the exact A-002 table and producer/schema evidence that identifies both amplitude convention and pulse polarity. Validate the evidence map, run the full-table convention audit, then execute the bridge with the authorized polarity. Require zero polarity violations, one row per composite physical key, stopping-bin totals equal to event count, and complete JSON/CSV/plot provenance before promoting any result.
