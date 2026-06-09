# Study report: P07b - natural B2 saturation recovery impact

- **Ticket:** `1781004956.668.7d00443a`
- **Worker:** `testbeam-laptop-3`
- **Date:** 2026-06-09
- **Inputs:** raw B-stack ROOT, runs 58, 59, 60, 61, 62, 63, 65
- **Command:** `/home/billy/anaconda3/bin/python reports/1781004956.668.7d00443a/p07b_natural_saturation_recovery.py`

## Reproduction first
The P07 leakage-free fixed-ceiling benchmark was reproduced directly from the raw ROOT before
the new natural-pulse study. For `C=4000 ADC`, the P07 ML res68 was
`0.032431778078` and this script reproduced
`0.032431778078`.

## Artificial-clip held-out benchmark
Each fold holds out one complete run. Models train on artificial `C=4000 ADC` clips of clean
unsaturated B2 pulses from the other runs.

- Traditional amplitude-binned template/rising-edge extrapolation res68:
  **0.1480**
  with run-bootstrap 95% CI **[0.1461, 0.1501]**.
- ML gradient-boosted regressor res68:
  **0.0298**
  with run-bootstrap 95% CI **[0.0279, 0.0323]**.
- ML median fractional bias:
  **-0.0005**
  with run-bootstrap 95% CI **[-0.0018, 0.0011]**.

## Natural saturated B2 transfer
Natural high-amplitude B2 pulses are selected with observed `A >= 7000 ADC` and
peak sample 4-13. There is no true amplitude label, so the transfer metrics are charge/template
and timing-tail diagnostics relative to the observed saturated waveform.

- Natural saturated B2 pulses: **5266**.
- Traditional mean `q_template` shift:
  **0.0010**
  with run-bootstrap 95% CI **[0.0008, 0.0012]**.
- ML multi-ceiling ratio regressor mean `q_template` shift:
  **-0.0897**
  with run-bootstrap 95% CI **[-0.0947, -0.0864]**.
- Observed timing-tail fraction:
  **0.0384**.
- Traditional timing-tail fraction:
  **0.0384**
  with run-bootstrap 95% CI **[0.0174, 0.0593]**.
- ML multi-ceiling ratio regressor timing-tail fraction:
  **0.0329**
  with run-bootstrap 95% CI **[0.0175, 0.0470]**.

## Leakage checks
Leakage flags: **0**. The checks cover exact P07 reproduction, run-held-out splitting,
implausibly tiny ML error, shuffled-target behavior, ML/traditional gap, and forbidden feature
presence. See `leakage_checks.csv`.

## Conclusion
On artificial clips, ML remains substantially better than the traditional rising-edge template
baseline under run-held-out evaluation. On naturally saturated B2 pulses, the ratio-transfer ML
applies a larger charge/template correction than the traditional method and shifts CFD20 timing relative to the
observed saturated amplitude definition; however, the timing-tail diagnostic does not improve
monotonically for every held-out run, so natural-pulse use should carry this as a calibration
systematic rather than a production correction.

## Artifacts
`result.json`, `manifest.json`, `input_sha256.csv`, `p07_reproduction_table.csv`,
`artificial_clip_by_run.csv`, `natural_transfer_by_run.csv`, `natural_predictions_sample.csv.gz`,
`leakage_checks.csv`, and three PNG diagnostics are in this folder.
