# Invalid Probe Ticket Audit: `1781212296.2046139.667a6c20`

- **Study ID:** `INVALID-PROBE-TICKET`
- **Author (worker label):** `testbeam-laptop-3`
- **Date:** 2026-07-10
- **Claimed ticket:** `1781212296.2046139.667a6c20`
- **Ticket title:** `TEST-PROBE-DELETEME`
- **Depends on:** none
- **Input checksum(s):** ticket metadata and raw B-stack ROOT sentinels in `result.json`
- **Git commit at audit start:** `3defbda9afa80dc0895f57f15924a3ad627e8a66`
- **Config:** not applicable

## 0. Question

The queue item contains no scientific question. The only auditable question for this
artifact is whether the claimed ticket contains enough pre-registered information to run
the required raw-ROOT reproduction, traditional baseline, ML/NN benchmark, run-held-out
bootstrap confidence intervals, and winner declaration.

The answer is no. The claimed ticket file is:

```text
id=1781212296.2046139.667a6c20
project=testbeam
title=TEST-PROBE-DELETEME
prio=P2
type=task
deps=
files=
created=1781212297
retries=1
===BODY===

```

## 1. Raw-ROOT Reproduction Gate

The worker goal requires reproducing the ticket's number from raw ROOT. This ticket has
no reported number, detector observable, selection, run range, stave, target variable,
or tolerance. Therefore there is no well-defined ROOT-derived quantity to reproduce.

The local data store was checked so that this conclusion is not a data-availability
failure:

| Quantity | Value |
|---|---:|
| Raw ROOT files under `data/root/root` | 110 |
| Raw B-stack ROOT files | 53 |
| Raw A-stack ROOT files | 57 |
| Sorted B-stack ROOT files | 53 |
| Sorted A-stack ROOT files | 53 |
| First B raw ROOT key checked with `uproot` | `h101;1` |
| Second B raw ROOT key checked with `uproot` | `h101;1` |

Sentinel checksums:

| File | SHA-256 |
|---|---|
| `data/root/root/hrdb_run_0012.root` | `84f09fe5eabb8f0af30907c82be33dfae19cf1b78d2799ac7141da7e98649cf9` |
| `data/root/root/hrdb_run_0065.root` | `fd443fd416e8e64b25f4358754c1cc7042a8c3b61c5a13fd82276873807e07bb` |

Match table:

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| Ticket-specific ROOT-derived number | not specified | not computed | not applicable | not specified | no, ticket invalid |

This is not a physics mismatch. It is a malformed administrative probe ticket.

## 2. Traditional Method

No traditional non-ML method can be selected fairly. A strong traditional comparator
requires a target observable, a metric, an allowed feature set, a held-out split, and a
decision rule. The ticket contains none of these. Running a conventional method anyway
would create an unregistered study under a misleading ticket ID and would violate the
analysis discipline that the target and metric must precede model selection.

Formally, a benchmark would need an estimand such as

```text
theta = T(Y, X, R)
```

where `Y` is the target, `X` the observed ROOT-derived features, `R` the run identifier,
and `T` the specified statistic. Here `Y`, `T`, and the admissible event population are
undefined. The loss `L(y, f(x))` is therefore undefined, and no traditional estimate
`f_trad(x)` can be evaluated.

## 3. ML And Neural Methods

No ridge, gradient-boosted tree, MLP, 1D-CNN, or new architecture was trained. The
missing items are fundamental:

| Required item | Ticket value | Consequence |
|---|---|---|
| Label or regression target | absent | no supervised loss can be defined |
| Physics observable | absent | no raw-ROOT reproduction target exists |
| Run split | absent | no run-held-out evaluation can be registered |
| Metric | absent | no model ranking or CI can be computed |
| Tolerance or decision rule | absent | no pass/fail criterion exists |
| Falsification test | absent | no scientific claim exists to falsify |

Training models under these conditions would produce an apparently complete artifact
with no scientific meaning. It would also create hidden multiple-testing risk: the
analysis could choose a convenient target after seeing the malformed ticket.

## 4. Head-To-Head Benchmark

| Method family | Required method | Status | Metric | Value with CI | Notes |
|---|---|---|---|---|---|
| Traditional | strong non-ML comparator | not run | not applicable | not applicable | no target or metric exists |
| Linear ML | ridge | not run | not applicable | not applicable | no label exists |
| Tree ML | gradient-boosted trees | not run | not applicable | not applicable | no label exists |
| Neural net | MLP | not run | not applicable | not applicable | no label exists |
| Neural net | 1D-CNN | not run | not applicable | not applicable | no waveform target exists |
| New architecture | only when sensible | not run | not applicable | not applicable | not sensible for an empty probe ticket |

Verdict: no winner can be named. `result.json` records the winner as
`not_applicable_invalid_ticket` so downstream aggregation can distinguish this
administrative closure from a real ML loss or a traditional-method win.

## 5. Bootstrap CIs And Run Splits

The requested split-by-run bootstrap would require per-event or per-run metric values:

```text
Delta_b = M({(y_i, f_a(x_i), r_i): r_i in S_b})
        - M({(y_i, f_b(x_i), r_i): r_i in S_b})
```

where each bootstrap sample `S_b` resamples held-out runs. Because the ticket provides
no `y_i`, no model functions, and no metric `M`, the bootstrap distribution cannot be
constructed. Reporting a CI over an invented endpoint would be more misleading than
leaving the benchmark unrun.

## 6. Systematics And Caveats

**Administrative validity:** the central systematic is that this is not a study ticket.
The title itself says `TEST-PROBE-DELETEME`, and the body is empty.

**Data availability:** raw data are present and readable. The invalid verdict is not due
to missing ROOT files or a failed `uproot` import.

**Benchmark selection:** any physics endpoint chosen after claiming this ticket would be
post hoc. The audit therefore declines to define a target.

**Data leakage:** no modeling was performed. The raw data preflight used only file
counts, sentinel checksums, and ROOT key inspection.

**Queue handling:** this ticket should be closed rather than released. Releasing it would
cause another worker to claim the same malformed probe and repeat the same administrative
failure.

## 7. Provenance

Primary artifacts in this directory:

- `REPORT.md`
- `result.json`
- `manifest.json`
- `claimed_ticket.txt`
- `raw_root_inventory.csv`

Commands used:

```bash
tn-ticket claim testbeam-laptop-3 --project testbeam
sed -n '1,120p' /home/billy/.config/tn/tickets/testbeam/claimed/1781212296.2046139.667a6c20
find -L data/root/root -maxdepth 1 -type f -name '*.root' | wc -l
find -L data/root/root -maxdepth 1 -type f -name 'hrdb_run_*.root' | wc -l
find -L data/root/root -maxdepth 1 -type f -name 'hrda_run_*.root' | wc -l
find -L data/sorted-b -maxdepth 1 -type f -name '*.root' | wc -l
find -L data/sorted-a -maxdepth 1 -type f -name '*.root' | wc -l
sha256sum /home/billy/.config/tn/tickets/testbeam/claimed/1781212296.2046139.667a6c20
sha256sum /home/billy/.config/tn/tickets/testbeam/claimed/1781212296.2046139.667a6c20.lease
sha256sum data/root/root/hrdb_run_0012.root data/root/root/hrdb_run_0065.root
/home/billy/anaconda3/bin/python -c "import uproot, glob; paths=sorted(glob.glob('data/root/root/hrdb_run_*.root'))[:2]; [print(path, list(uproot.open(path).keys())[:5]) for path in paths]"
```

## 8. Conclusion

The claimed queue item is an administrative probe, not an actionable testbeam study.
The raw ROOT data mirror is present and readable, but there is no ticket-specific number
to reproduce and no benchmark definition for a traditional method, ridge, gradient-boosted
trees, MLP, 1D-CNN, or any new architecture. The scientifically defensible action is to
close the malformed probe ticket with this audit artifact and append no scientific
follow-up ticket.
