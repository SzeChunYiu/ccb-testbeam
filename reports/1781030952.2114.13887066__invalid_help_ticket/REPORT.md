# Invalid Queue Ticket Audit: `1781030952.2114.13887066`

- **Study ID:** `INVALID-HELP-TICKET`
- **Author (worker label):** `testbeam-laptop-4`
- **Date:** 2026-06-10
- **Claimed ticket:** `1781030952.2114.13887066`
- **Ticket title:** `--help`
- **Depends on:** none
- **Input checksum(s):** ticket metadata and two raw B-stack ROOT sentinels in `result.json`
- **Git commit at audit start:** `bda0a0daace64360d90a3fc531da9e2052c19211`
- **Config:** not applicable

## 0. Question

The queue item contains no scientific question. The only valid question for this artifact is:
does the claimed ticket contain enough pre-registered information to run the required
reproduction, traditional baseline, ML benchmark, and winner declaration?

The answer is no. The claimed ticket file is:

```text
id=1781030952.2114.13887066
project=testbeam
title=--help
prio=P2
type=task
deps=
files=
created=1781030952
retries=0
===BODY===

rescued=1
```

## 1. Reproduction

The worker goal requires reproducing the ticket's number from raw ROOT. This ticket has no
reported number, observable, selection, run range, stave, target variable, or tolerance. Therefore
there is no well-defined ROOT-derived quantity to reproduce.

The data store itself was checked so that this conclusion is not caused by missing local data:

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

This is not a physics mismatch. It is a malformed queue item.

## 2. Traditional Method

No traditional non-ML method can be selected fairly. A strong traditional baseline requires at
least a target observable, a metric, a held-out split, and a decision rule. The ticket contains
none of those fields. Running a conventional method anyway would create an unregistered study
under a misleading ticket ID and would violate the fleet rule against post-hoc metric selection.

## 3. ML Method

No ridge, gradient-boosted tree, MLP, 1D-CNN, or new neural architecture was trained. The missing
items are fundamental:

- no label or regression target;
- no physics observable or detector subsystem beyond the global project context;
- no run-held-out split definition;
- no metric and no bootstrap unit;
- no pre-registered falsification test.

Training models under those conditions would produce an apparently complete artifact with no
scientific meaning.

## 4. Head-To-Head Benchmark

| Method | Metric | Value with CI | Notes |
|---|---|---|---|
| Traditional baseline | not applicable | not applicable | no target or metric exists |
| ML or NN model | not applicable | not applicable | no label, metric, or split exists |

Verdict: no winner can be named. `result.json` records the winner as
`not_applicable_invalid_ticket` so downstream aggregation can distinguish this from a real ML loss
or a traditional-method win.

## 5. Falsification

- **Pre-registration:** absent. The ticket body is empty.
- **Falsification test:** absent. No claim exists to falsify.
- **Result:** not applicable. The audit falsifies only the administrative premise that this is an
actionable scientific study ticket.

## 6. Threats to Validity

**Benchmark/selection:** the main risk is fabricating a benchmark after seeing an empty ticket.
This report avoids that by declining to define a target post hoc.

**Data leakage:** no modeling was performed. The raw data preflight used only file counts,
sentinel checksums, and ROOT key inspection.

**Metric misuse:** no physics metric is reported. The report explicitly avoids treating queue
closure as a scientific performance result.

**Post-hoc selection:** this is the decisive issue. Any physics study chosen after seeing the
empty `--help` ticket would be post-hoc and unauditable.

## 7. Provenance Manifest

The adjacent `manifest.json` records the commands used for the claim inspection, raw data
preflight, and output hashing. The adjacent `claimed_ticket.txt` is an exact copy of the claimed
ticket content at audit time.

## 8. Findings And Next Steps

The queue item is an administrative artifact, not a study. It should be closed rather than
released, because releasing it would cause another worker to claim the same malformed `--help`
ticket and repeat this failure. No novel scientific follow-up ticket is appended from this audit:
there is no physics hypothesis here.

Operational hypothesis: this item was created by a previous accidental `tn-ticket append --help`
or similar command-line invocation and later recovered into the open queue with `rescued=1`.
The expected information gain from a future queue-maintenance improvement would be operational,
not scientific: prevent empty or help-like titles from entering `project:testbeam`.

## 9. Reproducibility

Commands used:

```bash
tn-ticket claim testbeam-laptop-4 --project testbeam
sed -n '1,220p' /home/billy/.config/tn/tickets/testbeam/claimed/1781030952.2114.13887066
sha256sum /home/billy/.config/tn/tickets/testbeam/claimed/1781030952.2114.13887066
sha256sum /home/billy/.config/tn/tickets/testbeam/claimed/1781030952.2114.13887066.lease
find -L data/root/root -maxdepth 1 -type f -name '*.root' | wc -l
find -L data/root/root -maxdepth 1 -type f -name 'hrdb_run_*.root' | wc -l
find -L data/root/root -maxdepth 1 -type f -name 'hrda_run_*.root' | wc -l
find -L data/sorted-b -maxdepth 1 -type f -name '*.root' | wc -l
find -L data/sorted-a -maxdepth 1 -type f -name '*.root' | wc -l
sha256sum data/root/root/hrdb_run_0012.root data/root/root/hrdb_run_0065.root
/home/billy/anaconda3/bin/python - <<'PY'
import uproot
for path in ['data/root/root/hrdb_run_0012.root', 'data/root/root/hrdb_run_0013.root']:
    print(path, list(uproot.open(path).keys())[:1])
PY
```

Artifacts written:

- `REPORT.md`
- `result.json`
- `manifest.json`
- `claimed_ticket.txt`
- `raw_root_inventory.csv`
