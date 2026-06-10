# S16g: forced/random HRD pedestal ROOT acquisition audit

## Abstract

Ticket `1781031000.2375.3d7f6489` asked whether the true forced/random HRD pedestal ROOT sample can be acquired or mirrored, and whether S16f can then be rerun as a direct electronics pedestal truth comparison without the quiet-proxy fallback. I reran the raw-ROOT selected-pulse gate, searched the visible data mirrors and archive members, and inspected ROOT trigger/branch metadata for non-beam entries. The direct truth gate remains empty.

## Inputs and Reproducibility

- Ticket: `1781031000.2375.3d7f6489`
- Worker: `testbeam-laptop-3`
- Git commit: `da916840857c78ecb6bd8f4910bed3baf86ec915`
- Raw ROOT directory: `/home/billy/ccb-data/extracted/root/root`
- Config: `configs/s16g_1781031000_2375_3d7f6489_forced_random_root_acquisition.json`
- Script: `scripts/s16g_1781031000_2375_3d7f6489_forced_random_root_acquisition.py`

Search roots:
- `data`: present
- `/home/billy/ccb-data`: present
- `/home/billy/Desktop/test_beam/data`: present
- `/projects/hep/fs9/shared/nnbar/billy/ccb-testbeam/data`: missing

## Raw-ROOT Reproduction Gate

For each configured B-stack run \(r\), channel \(c\in\{B2,B4,B6,B8\}\), and sample \(t\), the seed pedestal was

\[
p_{irc}=\operatorname{median}\{x_{irc0},x_{irc1},x_{irc2},x_{irc3}\},
\]

and the selected-pulse indicator was

\[
I_{irc}=\mathbf{1}\left[\max_t (x_{irct}-p_{irc}) > 1000\;\mathrm{ADC}\right].
\]

The reproduced sum is `640737` selected B-stave pulses; the expected gate is `640737`.

|                         |            value |
|:------------------------|-----------------:|
| events_total            |      1.09673e+06 |
| selected_b_stave_pulses | 640737           |

The gate reproduction table is `reproduction_match_table.csv`; all run contributions are in `selected_count_by_run.csv`.

## Acquisition and Mirror Audit

The acquisition test treats a file or archive member as a candidate only if its name contains a strict forced/random/pedestal/no-pulse token. Generic `trigger` names are retained for context but do not count as a forced/random pedestal source. Archive members of visible `.zip` files were listed without extracting new data.

| quantity | value |
|---|---:|
| filesystem/archive rows audited | 438 |
| strict forced/random archive or ROOT candidates | 0 |
| missing search roots | 1 |

The complete inventory is `file_archive_inventory.csv`. The canonical LUNARC data path is listed as a search root; in this local run it is absent, so no mirroring source was available from that path.

## ROOT Trigger and Branch Audit

A direct S16f truth comparison requires events whose trigger or metadata identify non-beam forced/random/no-pulse acquisitions. For each ROOT file I inspected the `h101` branch list and counted

\[
N_{\mathrm{nonbeam}} = \sum_i \mathbf{1}[\mathrm{TRIGGER}_i \ne 1].
\]

| stack   |   files |   entries |   non_beam_trigger_entries |   files_with_tag_like_branch |
|:--------|--------:|----------:|---------------------------:|-----------------------------:|
| hrda    |      57 |   1652508 |                          0 |                            0 |
| hrdb    |      53 |   1649802 |                          0 |                            0 |

Across the visible HRDA/HRDB ROOT bundle, `N_nonbeam = 0`. The only branches are the standard DAQ fields; there is no separate random/forced/pedestal tag branch.

## Direct S16f Rerun Gate

The direct no-proxy candidate table contains `0` B-stack entries. Since this is zero, no estimator can be scored against forced/random electronics pedestal truth and no bootstrap confidence interval is statistically defined. I did not run the quiet-event proxy fallback because the ticket asks specifically for the direct truth comparison.

| estimand                                    |   n_truth_entries |   value_adc |   ci95_low_adc |   ci95_high_adc | status                                   |
|:--------------------------------------------|------------------:|------------:|---------------:|----------------:|:-----------------------------------------|
| direct forced/random pedestal estimator MAE |                 0 |         nan |            nan |             nan | not estimable: zero direct truth entries |

## Result

No forced/random HRD pedestal ROOT source or non-beam B-stack entry is visible in the mounted mirrors. The S16f direct truth comparison remains blocked; the only scientifically valid winner for this ticket is `none_no_direct_truth_sample` rather than a quiet-proxy estimator.

## Systematics and Caveats

- This is an absence-in-visible-mirror result, not proof that forced/random pedestal data were never recorded.
- ROOT trigger semantics are inherited from prior S16 work: `TRIGGER == 1` is treated as the beam trigger; non-beam truth would require a different value or a dedicated tag branch.
- The scan covers the local data symlinks, `/home/billy/ccb-data`, `/home/billy/Desktop/test_beam/data`, and the configured LUNARC canonical path if mounted. It cannot inspect unmounted offline archives.
- The selected-pulse reproduction verifies that the same B-stack raw ROOT bundle used by the main studies is being audited, but it does not create a no-pulse truth sample.

## Artifacts

- `result.json`
- `REPORT.md`
- `manifest.json`
- `input_sha256.csv`
- `selected_count_by_run.csv`
- `reproduction_match_table.csv`
- `root_trigger_branch_audit.csv`
- `file_archive_inventory.csv`
- `direct_nonbeam_entries.csv`
