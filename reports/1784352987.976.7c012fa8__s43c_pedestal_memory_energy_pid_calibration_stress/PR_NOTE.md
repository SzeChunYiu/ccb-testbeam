# S43c Pedestal-Memory Energy PID Calibration Stress Test

Local worker `testbeam-laptop-1` claimed ticket `1784352987.976.7c012fa8` and produced the full artifact set in the worker checkout under:

`reports/1784352987.976.7c012fa8__s43c_pedestal_memory_energy_pid_calibration_stress/`

Key result:

- Raw ROOT reproduction: 640737 selected B-stave pulses, delta 0.
- Split: train and held-out sets are disjoint by source run.
- Methods: strong traditional `ar1_charge_ratio_likelihood_traditional`, `ridge`, `gradient_boosted_trees`, `mlp`, `1d_cnn`, `tiny_sequence_transformer`, and new `pedestal_memory_fusion_new`.
- Winner: `pedestal_memory_fusion_new`.
- Follow-up ticket appended: `1784353448.932.155f1053`, `S43d: externally labeled pedestal-memory PID closure`.

The normal `git push` path from the worker failed because both local `gh` tokens are invalid and SSH push is not authorized. This PR note preserves the queue linkage while the full local commit `fe264b5` remains available in the worker checkout for push once credentials are repaired.
