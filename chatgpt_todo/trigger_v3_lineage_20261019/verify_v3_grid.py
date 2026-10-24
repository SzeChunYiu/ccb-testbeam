#!/usr/bin/env python3
"""Fail-closed consistency of pinned PR1542 4x5 source projections; NOT ROOT validation."""
from __future__ import annotations
import json

N = 1_000_000
# (threshold_MeV,window_ns,both,proxy_only,hardware_only,neither,hardware_scan,proxy_scan)
ROWS = (
 (0.5,5,165,221,196,999418,361,386),
 (0.5,10,165,222,196,999417,361,387),
 (0.5,15,165,389,196,999250,361,554),
 (0.5,20,165,392,196,999247,361,557),
 (0.5,30,165,392,196,999247,361,557),
 (1,5,165,221,195,999419,360,386),
 (1,10,165,222,195,999418,360,387),
 (1,15,165,389,195,999251,360,554),
 (1,20,165,392,195,999248,360,557),
 (1,30,165,392,195,999248,360,557),
 (2,5,164,222,195,999419,359,386),
 (2,10,164,223,195,999418,359,387),
 (2,15,164,390,195,999251,359,554),
 (2,20,164,393,195,999248,359,557),
 (2,30,164,393,195,999248,359,557),
 (5,5,163,223,192,999422,355,386),
 (5,10,163,224,192,999421,355,387),
 (5,15,163,391,192,999254,355,554),
 (5,20,163,394,192,999251,355,557),
 (5,30,163,394,192,999251,355,557),
)

def verify(rows=ROWS):
    expected={(t,w) for t in (0.5,1,2,5) for w in (5,10,15,20,30)}
    seen={}
    for row in rows:
        if type(row) not in (tuple,list) or len(row)!=8:
            raise ValueError('malformed projection row')
        t,w,b,p,h,n,hs,ps=row
        if any(type(x) is not int or x<0 for x in (b,p,h,n,hs,ps)):
            raise ValueError('invalid count')
        if (t,w) not in expected or (t,w) in seen:
            raise ValueError('duplicate/unexpected grid coordinate')
        if b+p+h+n!=N or b+h!=hs or b+p!=ps:
            raise ValueError('source joint/scan marginal mismatch')
        seen[t,w]=row
    if set(seen)!=expected:
        raise ValueError('missing grid cell')
    for t in (0.5,1,2,5):
        for column in (2,6,7):
            values=[seen[t,w][column] for w in (5,10,15,20,30)]
            if values!=sorted(values):
                raise ValueError('fixed-threshold window monotonicity failure')
    ref=seen[1,15]
    if ref[2:]!=(165,389,195,999251,360,554):
        raise ValueError('pinned reference changed; fresh audit required')
    return {'schema':'ccb-v3-frozen-grid-consistency/1',
            'status':'PINNED_PROJECTION_CONSISTENT_NOT_EXPERIMENT_VALIDATED',
            'scientific_release':'NOT_AUTHORIZED','grid_cells':len(seen),
            'v3_joint':{'both':165,'proxy_only':389,'hardware_only':195,'neither':999251},
            'v3_proxy_retention':165/554,'v3_hardware_outside_proxy':195/360,
            'v2_geometry':'RETRACTED_ANTIPODAL_R30',
            'limits':'manually copied fields from pinned unmerged PR1542 source; no original ROOT, full Geant4 or hardware'}

if __name__=='__main__':
    print(json.dumps(verify(),indent=2))
