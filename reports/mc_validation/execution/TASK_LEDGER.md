# MC validation execution task ledger

| Task ID | Status | Evidence |
|---------|--------|----------|
| E001 | IN_PROGRESS | Pipeline orchestrator implementation |
| E002 | NOT_STARTED | Full LUNARC production submit |

Updated by `scripts/mc_validation/run_pipeline.py` workflow.

## Lane 10 Wave C (`fix/lane10-waveC`)

Refs #1218 #986 #1091 #1062. Does not close those issues.

- Close-intent schema + hostile fixture matrix + CI gate (#1218)
- PR template + `run_close_intent_gates.py` ledger workflow (#1218 completion gate)
- GEOMETRY_DIGEST_V2 named-field digest excluding Birks/optics (#986)
- Neutron tracking-time cut recorded as implicit QGSP_BIC default (#1091)
- Timing same-sample method-selection authorising gate (#1062)
- `run_pipeline` smoke/collect DAG-ready (`dag_ready`, on-LUNARC slurm helpers)
