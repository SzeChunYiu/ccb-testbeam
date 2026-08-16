# ARU-MC-WEIGHT-CARRIER-001 — schema supplement

This supplement records repository-resident evidence found after the initial carrier audit.

## Content-addressed diagnostic schema

`reports/0000000004.1.g4truth/truth_schema.csv` records the `PrimaryWeight` branch as:

- C++ typename: `std::vector<double>`
- Uproot interpretation: `AsJagged(AsDtype('>f8'), header_bytes=10)`

The companion S17a report binds the patched smoke ROOT to SHA-256

`74387a04571cf92724fb97974b1214579996ed33cff0b128e6a96eb21fc3164a`

with tree `hibeam` and 100,000 entries. It reports 100,000 proton and 100,000 deuteron primary truth rows. The run is explicitly **not production physics**: the unsupported `CSFile` macro line was removed, the event count was reduced to 100k and the scattering angle was sampled without the intended p-d cross-section table.

## What this eliminates

It eliminates a campaign-general statement that the raw ROOT `PrimaryWeight` representation is intrinsically a scalar branch. At least one content-addressed repository-supported generator output stores it as a jagged vector branch.

It does **not** establish:

- event-wise `PrimaryWeight` vector cardinality;
- equality of sibling primary weights;
- that element 0 is the beam/event carrier;
- the physical target/proposal measure for production campaigns;
- that a legacy nonunit weight should be applied to current direct-sampled campaigns.

Therefore the v2 policy/auditor must distinguish two contracts:

1. **raw branch representation** (possibly vector/per-primary, campaign-specific), and
2. **derived event-measure weight vector** (exactly one validated weight per generator event/statistical unit).

A producer may reach contract (2) only through a source-bound, versioned adapter. For a replicated-primary adapter, all sibling values must be demonstrated equal and primary-row permutation must leave the derived event weight unchanged. For scalar mode, cardinality one is enforced. For direct-sampled unit mode, generator provenance must establish unity weighting.

## Repository actions

This evidence was added to reopened #880 and to the review history of active PR #1169. No production MC number or detector claim was regenerated from this smoke-run schema.