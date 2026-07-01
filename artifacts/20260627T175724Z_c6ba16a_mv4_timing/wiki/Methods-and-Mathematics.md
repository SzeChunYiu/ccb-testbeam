# Methods and mathematical definitions

## Populations and estimands

The current artifact-summary scope covers MV1, MV2, MV3, and MV9 frozen outputs for run `20260627T175724Z_c6ba16a_mv4_timing`. MV4-MV8 and systematic arrays are blocked pending calibrated digitized MC.

## Core formulas

## Claim support discipline

External references define standard methods and notation; project claims require project evidence. The wiki therefore pairs literature reference IDs with frozen validation artifacts, claim-ledger rows, and QA gates before promoting any release claim.

For a binary particle-identification score `s(x)` and threshold `t`, efficiency and purity are recorded conceptually as

```math
\epsilon(t) = \frac{N_{\mathrm{true\,signal}}(s(x) \ge t)}{N_{\mathrm{true\,signal}}}, \qquad
P(t) = \frac{N_{\mathrm{true\,signal}}(s(x) \ge t)}{N_{\mathrm{selected}}(s(x) \ge t)}.
```

For energy/range closure summaries, the robust 68% residual scale is represented as

```math
R_{68} = \frac{1}{2}\left(Q_{84}[r] - Q_{16}[r]\right), \qquad r = \frac{E_{\mathrm{reco}} - E_{\mathrm{truth}}}{E_{\mathrm{truth}}}.
```

For stopping-depth support, sample counts are reported as frozen artifact supports and are not final physics cross sections:

```math
N_{\mathrm{Sample\,I}},\; N_{\mathrm{Sample\,II}}.
```

## Leakage and provenance guardrails

Truth labels, event identifiers, and future information are not publication features. Current wiki pages are generated from frozen summary artifacts and do not rerun ROOT scans, GEANT4, digitization, or training.
