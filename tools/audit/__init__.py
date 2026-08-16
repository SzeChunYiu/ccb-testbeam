"""CCB test-beam repository-wide scientific audit harness.

Static + data-level auditors that surface publication-blocking (P0) scientific
integrity risks as *candidates for human triage*. Nothing here mutates the repo
or the physics; every tool is read-only and deterministic.

Modules
-------
audit_repository      Repo-wide static AST/regex auditor (findings + inventory).
validate_event_keys   Prove composite-key one_to_one join cardinality.
validate_pulse_schema Validate a selected-pulse table against the pulse schema.
audit_mc_weight_usage Check a ROOT tree for an MC weight branch + report ESS.
run_repo_audit        Thin inventory wrapper over audit_repository (never gates).
"""
