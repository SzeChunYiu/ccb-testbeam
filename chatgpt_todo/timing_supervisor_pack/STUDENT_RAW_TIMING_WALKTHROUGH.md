# Raw-waveform timing from zero: student walkthrough

This beginner course is split into two readable parts:

1. [`STUDENT_TIMING_PLOTS_00_18.md`](STUDENT_TIMING_PLOTS_00_18.md) — vocabulary, data contracts, pulse identity, baseline, component selection, CFD construction, unique-event cut flow, timestamps, correction stages, and full/core residual views.
2. [`STUDENT_TIMING_PLOTS_19_29_AND_RUNNING.md`](STUDENT_TIMING_PLOTS_19_29_AND_RUNNING.md) — CFD fraction selection, timewalk, noise/slope, sampling phase, run stability, all-pair/covariance inference, injection recovery, the deliberate 0.1 ns look-alike, commands, and the publication checklist.

The machine-readable question/pass/fail contract is `student_plot_atlas.csv`. The executable entry point is `student_timing_walkthrough.py`; start with:

```bash
python chatgpt_todo/timing_supervisor_pack/student_timing_walkthrough.py self-test
python chatgpt_todo/timing_supervisor_pack/student_timing_walkthrough.py demo \
  --events 10000 \
  --out chatgpt_todo/timing_supervisor_pack/student_demo
```

The raw-data lane is deliberately fail-closed. A narrow residual is not a stave resolution until frame shape, pulse identity, held-out stability, covariance/identifiability, and injection/recovery gates all pass.
