# C12 anomaly public-claim status

**Audit status:** `TRUTH_LEVEL_MC_ONLY`

**Authoritative evidence boundary:** The inspected repository evidence supports a truth-labelled Monte Carlo anomaly population, not an empirical carbon-12 species assignment in beam data.

## Supported statements

- Study MV6 reports 283 anomaly-classified tracks among 87,555 truth-labelled MC tracks, approximately 0.32%.
- Within that MC-selected anomaly class, approximately 55% of tracks are labelled carbon-12.
- Carbon-12 is therefore a candidate mechanism demonstrated in the inspected simulation sample.

## Unsupported or premature statements

The following formulations must not be treated as established real-data results:

- “C12 anomaly fraction = 0.32%” without explicitly identifying the denominator as the truth-labelled MC sample.
- “C12 nuclear recoils were discovered in beam data.”
- “The real-data anomaly is carbon-12.”
- Any veto-efficiency, background-rejection, or deuteron-systematic claim derived from the MC-labelled class without matched data/MC closure.

The repository also reports a related real-data anomaly near 4%, more than an order of magnitude above 0.32%. No inspected artifact provides event-level species truth for that real-data population. This rate mismatch is a blocking transfer-validity question, not evidence that the two populations are identical.

## Known public-document inconsistencies

At the time of this audit, `WIKI.md` still contains two stale statements:

1. The canonical-results table labels “C12 anomaly fraction, 0.32%” as `VALIDATED` and “MC-identified”.
2. Section 9 repeats “0.32% of tracks” as `VALIDATED`.

`docs/academic_chapters/09_anomaly_id.md` also uses discovery language and presents several downstream physical and systematic conclusions as settled. Those statements exceed the evidence boundary recorded in `docs/claim_ledger.csv` and `chatgpt_todo/CLAIM_EVIDENCE_MATRIX.md`.

Until the public files are fully synchronized, this notice and the claim ledger define the conservative interpretation.

## Required public wording

Use wording equivalent to:

> In a truth-labelled Monte Carlo sample, 283 of 87,555 tracks (about 0.32%) were assigned to an early-peak anomaly class, and about 55% of that MC class carried a carbon-12 label. This establishes carbon-12 as a simulated candidate mechanism. Transfer to the reported real-data anomaly is unvalidated and requires a frozen matched data/MC closure study.

## Promotion gate

A stronger statement requires all acceptance criteria in `docs/validation/C12_DATA_MC_CLOSURE_SPEC.md`, including:

- frozen and traceable data/MC populations;
- identical preprocessing and a preregistered cross-domain classifier;
- exact counts, denominators, Wilson intervals, and data/MC rate effect size;
- morphology closure with identical binning and uncertainty displays;
- run, detector, seed, preprocessing, and model-choice stability checks;
- negative controls and holdouts;
- machine-readable outputs and input hashes.

The phrase “C12 identified in data” additionally requires an independent event-level species tag or a separately validated proxy with a measured confusion matrix.

## Evidence classification

- **Observed repository fact:** the public wiki and Chapter 9 currently overstate the MC-to-data transfer.
- **Simulation result:** 283/87,555 MC tracks in the anomaly class; approximately 55% C12 within that MC class.
- **Observed repository report:** a related real-data anomaly near 4%.
- **Unresolved question:** whether the MC morphology transfers to the real-data population.
- **Not claimed:** real-data C12 identification, validated veto performance, or a 0.1% deuteron systematic.
