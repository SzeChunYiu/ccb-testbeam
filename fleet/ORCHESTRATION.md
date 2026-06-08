# Fleet orchestration

How the CCB test-beam studies get worked by a fleet of codex agents, coordinated through the
`tn-ticket` queue, with Claude as orchestrator.

## Roles
- **Orchestrator (Claude):** owns `studies/STUDIES.md`, cuts tickets, launches/monitors the
  fleet, gathers `reports/`, and writes the rolling summary (`reports/SUMMARY.md`). Gives
  *general direction*; does not micro-manage each fit.
- **Workers (codex agents):** claim a ticket, do the study end-to-end per
  [`studies/STUDY_TEMPLATE.md`](../studies/STUDY_TEMPLATE.md), commit code + a `reports/` entry,
  open follow-up tickets, mark done.

## Queue
- Backend: GitHub issues in `SzeChunYiu/factory-tickets`, scoped by label **`project:testbeam`**.
- CLI: `tn-ticket {list,claim,append,done,release,reaper} [--project testbeam]`.

```bash
tn-ticket list --project testbeam
tn-ticket claim testbeam-laptop-1 --project testbeam     # pops oldest open S-ticket
# ... do the work, commit, write reports/S<NN>_.../REPORT.md ...
tn-ticket append "S04b: full-RMS + chi2/ndf for residual fits" --body "..." --project testbeam
tn-ticket done <id>
```

## Compute
- **Laptop `billy`** (RTX A3000 6 GB): 6–8 codex panes for `[L]` studies (reproduction, fits,
  classical ML). Launched via `csup`.
- **LUNARC** (`ssh lunarc`, user `scyiu`): `[C]` CPU-heavy and `[G]` GPU training (S08, S09,
  S14, S17). Book a node, run a worker set there; raw data mirrored to
  `/projects/hep/fs9/shared/nnbar/billy/ccb-testbeam/data/`.

### Launching
```bash
# local fleet (example): N sessions, W workers each, scoped to this project
csup station testbeam --sessions=6 --workers=1 --host=billy --apply
csup status testbeam
# LUNARC fleet (after `ssh lunarc` socket is up and data is mirrored)
csup station testbeam --sessions=4 --workers=1 --host=lunarc --apply
```

## Rules for workers (enforced by the template)
1. **Reproduce before extending** — match the report number from raw ROOT first (state tolerance).
2. **Both methods** — traditional baseline AND ML, with a fair head-to-head benchmark.
3. **Atomic** — one cut/fit/feature per step, each validated.
4. **Pin provenance** — input checksum + git commit + config in every report.
5. **Small tickets** — finishable in one session; split if not; append follow-ups.
6. **Never commit data** — `data/` is gitignored; reference by checksum + `DATA.md`.

## Phase gate
Phase 1+ tickets stay `factory:open` but workers must check that **S00 is `done`** (the
reproduction gate) before starting any dependent study. The orchestrator seeds Phase 0 first.

## Reporting loop
Orchestrator periodically: `tn-ticket list`, read new `reports/`, update
`reports/SUMMARY.md` (a scoreboard: per-study reproduction pass/fail + ML-vs-traditional
verdict), and cut the next wave of tickets from `STUDIES.md`.
