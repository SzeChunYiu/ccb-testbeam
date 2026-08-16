# MC-side ΔE–E closure — the MC goes *down* (A-002 complete)

Completes the ΔE–E study by building the **MC side** with the resolved layer→stave
mapping (#869) and `PrimaryWeight` applied (A-003). Pairs with the data-side
composite-key rerun in `../deltaE_a002/`.

## Mapping (per #869): B2/B4/B6/B8 = MC B-arm LayerID 1,3,5,7
`deltaE_mc = edep(B2)=LayerID1`; `E_mc = edep(B4+B6+B8)=LayerID3+5+7`, weighted by
`PrimaryWeight`.

| mapping | n events | ΔE w-median [MeV] | E w-median [MeV] | **corr(ΔE, E)** |
|---|--:|--:|--:|--:|
| **B2/B4/B6/B8 = LayerID 1,3,5,7 (#869)** | 118,751 | 12.4 | 51.1 | **−0.47** |
| alt LayerID 0,2,4,6 | 130,750 | 11.6 | 45.6 | −0.28 |

## Key result — the MC ΔE–E is anti-correlated (goes DOWN)
`corr(ΔE, E) = −0.47`: as E rises, ΔE falls — the **expected stopping/Bethe-Bloch
signature**. The physically-motivated mapping (1,3,5,7, with B2 as the shallowest
instrumented ΔE stave) gives the **stronger** anti-correlation, consistent with
the every-other convention.

## This resolves the "ΔE–E goes up not down" puzzle
The MC (correct) goes **down**. So a data ΔE–E that goes **up** is not physics —
it is the data-side artifact quantified in `../deltaE_a002/`: the prior outputs
joined on `eventno` alone, corrupting **~38% of events** across runs. The
composite key `(source_file_id, run, evt)` fixes the data side; the MC here shows
the target behaviour.

## Caveats
- The exact physical offset (1,3,5,7 vs 0,2,4,6) is not fit-to-data (the audit
  forbids that); both are reported. Locking it needs the DAQ/survey drawings
  (#869). Either offset gives an anti-correlated (downward) ΔE–E.
- MC is `edep` in **MeV**; the data side is **ADC**. A quantitative data/MC
  overlay needs the digitized-MC chain (gain 92 ADC/MeV + response) — the shape
  (downward correlation) already matches; the absolute overlay is the remaining
  digitization step.

`scripts/single_stave/deltaE_E_mc.py`, `result.json`, `DE-MC-01_deltaE_E_mc.png`.
