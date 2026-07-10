# S20 Geant4 Truth Integrity Audit

- **Ticket ID:** `1781181864.166771.778b7120`
- **Worker:** `testbeam-laptop-4`
- **Date:** 2026-07-10
- **Input ROOT:** `/home/billy/ccb-geant4/output_krakow_1M.root`
- **Committed reference:** `geant4/results/sim_summary.json`
- **Git commit:** `ca371e2f1b7cfe6c813c45ad515783e5f9e34c48`
- **Runtime:** 8.6 s with Python 3.7.6 and uproot 5.0.9
- **Verdict:** **FAIL**

## 1. Question

This audit asks whether the `hibeam` truth tree in `output_krakow_1M.root` is internally valid and whether `geant4/results/sim_summary.json` is reproducible from that raw ROOT file. The required observables are the event count, primary PDG and kinetic-energy spectrum, per-detector hit populations for `TARGET`, `ProtoTPC`, and `Sci_bar`, energy-conservation checks, and an independent recomputation of the committed per-layer Sci_bar summary.

## 2. Data and Schema

The ROOT file contains one TTree, `hibeam`, with 1,000,000 event entries. The analysis reads primary truth branches `PrimaryPDG` and `PrimaryEkin`, plus vector hit branches for the three detector groups. Each detector group contributes `TrackID`, `LayerID`, `PDG`, `EDep`, `Time`, and global position coordinates. The ROOT checksum used for this audit is:

```text
sha256(output_krakow_1M.root) = 2b62403f0aa7ecc8c6fc8ffb5006b59d833ff1a31a95a8f389f88f45a18542cc
```

## 3. Method

All observables are recomputed by streaming the ROOT TTree in chunks. For a detector group \(D\), event \(e\), and hit \(h\), the total sensitive-detector energy deposit is

```text
E_dep(e) = sum_D sum_{h in D(e)} EDep_{D,h}.
```

The primary kinetic-energy budget is

```text
E_kin(e) = sum_{p in Primary(e)} PrimaryEkin_p.
```

The conservative energy-conservation gate flags event \(e\) when \(E_dep(e) > E_kin(e) + 10^-9\) MeV. This is conservative because it sums only sensitive detector deposits, not passive material losses; any violation would therefore be a hard inconsistency.

For Sci_bar layer \(l\), the recomputed summary fields are

```text
hits_l        = count(h : LayerID_h = l)
hits_gt10_l   = count(h : LayerID_h = l and EDep_h > 10 MeV)
mean_edep_l   = (1 / hits_l) sum_{h:LayerID_h=l} EDep_h
p_frac_l      = count(h : LayerID_h=l and PDG_h=2212) / hits_l
d_frac_l      = count(h : LayerID_h=l and PDG_h=1000010020) / hits_l.
```

The `truth_protons` and `truth_deuterons` totals in the committed JSON are reproduced as the corresponding Sci_bar p/d hit counts summed over all eight layers.

## 4. Primary Truth Spectrum

| pdg | count | fraction_of_primary_records | mean_ekin_MeV | std_ekin_MeV | min_ekin_MeV | max_ekin_MeV |
| --- | --- | --- | --- | --- | --- | --- |
| 2212.000000 | 1.000000e+06 | 0.500000 | 104.366687 | 60.210188 | 19.260017 | 189.999328 |
| 1.000010e+09 | 1.000000e+06 | 0.500000 | 85.193315 | 60.210384 | 8.967618e-10 | 170.657311 |

The primary records contain the expected proton/deuteron two-body truth for every generated event. The kinetic-energy extrema remain finite and positive.

## 5. Detector Hit Populations

| detector | hits | mean_edep_MeV | hits_gt10MeV | p_frac | d_frac | max_edep_MeV | unique_layers |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TARGET | 2042996 | 3.858374 | 195032 | 0.495524 | 0.490648 | 65.070308 | 1 |
| ProtoTPC | 1855512 | 0.003685 | 0 | 0.271698 | 0.002726 | 0.985367 | 10 |
| Sci_bar | 1279440 | 21.131737 | 1080660 | 0.653828 | 0.245925 | 126.075485 | 8 |

The Sci_bar population dominates the committed summary. TARGET and ProtoTPC are included in the event-level energy budget and detector-level sanity checks.

## 6. Recomputed Sci_bar Layer Summary

| layer | hits | hits_gt10MeV | mean_edep_MeV | p_frac | d_frac |
| --- | --- | --- | --- | --- | --- |
| 0.000000000000 | 3.710890000000e+05 | 3.112470000000e+05 | 23.344708975559 | 0.495404067488 | 0.392485360655 |
| 1.000000000000 | 2.882300000000e+05 | 2.451970000000e+05 | 20.907364379187 | 0.548450889914 | 0.363307081150 |
| 2.000000000000 | 1.754890000000e+05 | 1.480420000000e+05 | 20.535003877147 | 0.692145946470 | 0.201363048396 |
| 3.000000000000 | 1.435800000000e+05 | 1.220230000000e+05 | 17.717564025451 | 0.727448112550 | 0.189657333891 |
| 4.000000000000 | 1.007970000000e+05 | 86361.000000000000 | 16.944771998080 | 0.895205214441 | 0.008026032521 |
| 5.000000000000 | 95953.000000000000 | 81368.000000000000 | 23.224951481137 | 0.885110418642 | 0.005283836878 |
| 6.000000000000 | 69737.000000000000 | 58409.000000000000 | 22.593892240014 | 0.901945882387 | 0.003627916314 |
| 7.000000000000 | 34565.000000000000 | 28013.000000000000 | 19.905209765020 | 0.886503688702 | 0.004223925937 |

## 7. Delta Against `sim_summary.json`

| quantity | recomputed | reference | delta | abs_delta | pass |
| --- | --- | --- | --- | --- | --- |
| events | 1.000000000000e+06 | 1.000000000000e+06 | 0.000000000000 | 0.000000000000 | True |
| truth_protons | 8.365340000000e+05 | 8.365340000000e+05 | 0.000000000000 | 0.000000000000 | True |
| truth_deuterons | 3.146460000000e+05 | 3.146460000000e+05 | 0.000000000000 | 0.000000000000 | True |
| layer_0.hits | 3.710890000000e+05 | 3.710890000000e+05 | 0.000000000000 | 0.000000000000 | True |
| layer_0.hits_gt10MeV | 3.112470000000e+05 | 3.112470000000e+05 | 0.000000000000 | 0.000000000000 | True |
| layer_0.mean_edep_MeV | 23.344708975559 | 23.344708975559 | -3.552713678801e-15 | 3.552713678801e-15 | True |
| layer_0.p_frac | 0.495404067488 | 0.495404067488 | 0.000000000000 | 0.000000000000 | True |
| layer_0.d_frac | 0.392485360655 | 0.392485360655 | 0.000000000000 | 0.000000000000 | True |
| layer_1.hits | 2.882300000000e+05 | 2.882300000000e+05 | 0.000000000000 | 0.000000000000 | True |
| layer_1.hits_gt10MeV | 2.451970000000e+05 | 2.451970000000e+05 | 0.000000000000 | 0.000000000000 | True |
| layer_1.mean_edep_MeV | 20.907364379187 | 20.907364379187 | 0.000000000000 | 0.000000000000 | True |
| layer_1.p_frac | 0.548450889914 | 0.548450889914 | 0.000000000000 | 0.000000000000 | True |
| layer_1.d_frac | 0.363307081150 | 0.363307081150 | 0.000000000000 | 0.000000000000 | True |
| layer_2.hits | 1.754890000000e+05 | 1.754890000000e+05 | 0.000000000000 | 0.000000000000 | True |
| layer_2.hits_gt10MeV | 1.480420000000e+05 | 1.480420000000e+05 | 0.000000000000 | 0.000000000000 | True |
| layer_2.mean_edep_MeV | 20.535003877147 | 20.535003877147 | 0.000000000000 | 0.000000000000 | True |
| layer_2.p_frac | 0.692145946470 | 0.692145946470 | 0.000000000000 | 0.000000000000 | True |
| layer_2.d_frac | 0.201363048396 | 0.201363048396 | 0.000000000000 | 0.000000000000 | True |
| layer_3.hits | 1.435800000000e+05 | 1.435800000000e+05 | 0.000000000000 | 0.000000000000 | True |
| layer_3.hits_gt10MeV | 1.220230000000e+05 | 1.220230000000e+05 | 0.000000000000 | 0.000000000000 | True |
| layer_3.mean_edep_MeV | 17.717564025451 | 17.717564025451 | -7.105427357601e-15 | 7.105427357601e-15 | True |
| layer_3.p_frac | 0.727448112550 | 0.727448112550 | 0.000000000000 | 0.000000000000 | True |
| layer_3.d_frac | 0.189657333891 | 0.189657333891 | 0.000000000000 | 0.000000000000 | True |
| layer_4.hits | 1.007970000000e+05 | 1.007970000000e+05 | 0.000000000000 | 0.000000000000 | True |
| layer_4.hits_gt10MeV | 86361.000000000000 | 86361.000000000000 | 0.000000000000 | 0.000000000000 | True |
| layer_4.mean_edep_MeV | 16.944771998080 | 16.944771998080 | -3.552713678801e-15 | 3.552713678801e-15 | True |
| layer_4.p_frac | 0.895205214441 | 0.895205214441 | 0.000000000000 | 0.000000000000 | True |
| layer_4.d_frac | 0.008026032521 | 0.008026032521 | 0.000000000000 | 0.000000000000 | True |
| layer_5.hits | 95953.000000000000 | 95953.000000000000 | 0.000000000000 | 0.000000000000 | True |
| layer_5.hits_gt10MeV | 81368.000000000000 | 81368.000000000000 | 0.000000000000 | 0.000000000000 | True |
| layer_5.mean_edep_MeV | 23.224951481137 | 23.224951481137 | 0.000000000000 | 0.000000000000 | True |
| layer_5.p_frac | 0.885110418642 | 0.885110418642 | 0.000000000000 | 0.000000000000 | True |
| layer_5.d_frac | 0.005283836878 | 0.005283836878 | 0.000000000000 | 0.000000000000 | True |
| layer_6.hits | 69737.000000000000 | 69737.000000000000 | 0.000000000000 | 0.000000000000 | True |
| layer_6.hits_gt10MeV | 58409.000000000000 | 58409.000000000000 | 0.000000000000 | 0.000000000000 | True |
| layer_6.mean_edep_MeV | 22.593892240014 | 22.593892240014 | 0.000000000000 | 0.000000000000 | True |
| layer_6.p_frac | 0.901945882387 | 0.901945882387 | 0.000000000000 | 0.000000000000 | True |
| layer_6.d_frac | 0.003627916314 | 0.003627916314 | 0.000000000000 | 0.000000000000 | True |
| layer_7.hits | 34565.000000000000 | 34565.000000000000 | 0.000000000000 | 0.000000000000 | True |
| layer_7.hits_gt10MeV | 28013.000000000000 | 28013.000000000000 | 0.000000000000 | 0.000000000000 | True |
| layer_7.mean_edep_MeV | 19.905209765020 | 19.905209765020 | -3.552713678801e-15 | 3.552713678801e-15 | True |
| layer_7.p_frac | 0.886503688702 | 0.886503688702 | 0.000000000000 | 0.000000000000 | True |
| layer_7.d_frac | 0.004223925937 | 0.004223925937 | 0.000000000000 | 0.000000000000 | True |

There are 0 failed summary fields. The maximum absolute delta is 7.105e-15.

## 8. Integrity Gates

| check | value | threshold | pass | interpretation |
| --- | --- | --- | --- | --- |
| tree_entries | 1000000 | exactly 1000000 | True | The ROOT tree has the requested one million event rows. |
| committed_summary_reproduced | 43 | 43 summary fields pass | True | Independent chunked recomputation matches sim_summary.json. |
| energy_conservation | 185 | 0 events with sum detector EDep > sum primary Ekin | False | No event deposits more sensitive-detector energy than primary kinetic energy. |
| finite_edep | 0 | 0 non-finite EDep values | True | No NaN or infinite EDep entries were found. |
| nonnegative_edep | 0 | 0 negative EDep values | True | No negative deposited energies were found. |
| scibar_layer_domain | 0 | 0 Sci_bar hits outside layer IDs 0..7 | True | Sci_bar layers match the eight-layer summary contract. |
| duplicate_exact_hit_rows | 0 | 0 exact duplicate detector hit tuples | True | No exact duplicate hit records after rounded numeric tuple comparison. |
| geometry_positions_finite | 0 | 0 non-finite global hit positions | True | No non-finite global positions; no numeric geometry escape sentinel found. |

There are 1 failed integrity gates. The maximum event-level ratio \(E_dep/E_kin\) is 1.013177; the mean sensitive-detector deposit per event is 34.926271 MeV.

## 9. Systematics and Caveats

- This is a truth-tree integrity audit, not a detector-response validation. It does not test Birks quenching, optical transport, ADC conversion, trigger emulation, or waveform reconstruction.
- The energy-conservation check is intentionally one-sided and conservative: sensitive-detector EDep must not exceed primary kinetic energy, but equality is not expected because passive material losses and escaping particles are not included in the sensitive-detector sum.
- Exact duplicate detection uses rounded numeric hit tuples within each streamed chunk. It is designed to catch duplicated persisted hit rows, not physically distinct hits with nearly identical floating-point values.
- Geometry-escape checks here are numeric and schema-level: non-finite global positions and Sci_bar layer IDs outside 0..7 are treated as failures. A full geometric containment proof would need the geometry solids and material boundaries.
- No ADC saturation can be inferred from truth EDep alone. The reported saturation gate is therefore a truth-side proxy: finite, nonnegative EDep values and no event with unphysical detector energy excess.

## 10. Conclusion

The claimed S20 audit **fails**: the one-million-event ROOT truth tree is readable, the committed `sim_summary.json` is independently reproduced field-by-field from raw ROOT, primary and detector spectra are finite, and 185 events violate the sensitive-detector energy-conservation bound. The result stored in `result.json` names `sim_summary_json_reproduced_but_truth_integrity_energy_budget_fails` as the winner/conclusion because this ticket is a deterministic integrity audit rather than a machine-learning benchmark.

## 11. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s20_1781181864_166771_778b7120_g4_truth_integrity.py \
  --root /home/billy/ccb-geant4/output_krakow_1M.root \
  --summary geant4/results/sim_summary.json \
  --out reports/1781181864.166771.778b7120__s20_g4_truth_integrity
```
