# AUD-FIG-002 validation-record hash correction

This append-only correction supersedes one metadata value in
`2026-07-26T092835Z_AUD-FIG-002_SNAPSHOT_PROVENANCE.md` without modifying that
immutable record.

The earlier archive listed the SHA-256 of
`docs/validation/figure_registry_snapshot_provenance_validation.json` as:

`818555ab3491e1d156678fbd11b58797c4ad629e0f36792cc395c7d741eeeab0`

A byte-for-byte recheck of the committed JSON content gives the correct SHA-256:

`e42ddb438a3c97a9ef9c5fadef61e1a3563c41599a179a15b28e517eff45f9be`

The committed Git blob is:

`80dff731ac06cfcfd35e20623cee521ada778018`

The JSON parses successfully and its scientific/audit content is unchanged:
`status=FLAWED`, `finding_count=3`. No scientific result or audit conclusion is
changed by this correction.
