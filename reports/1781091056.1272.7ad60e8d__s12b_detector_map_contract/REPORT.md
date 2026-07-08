# S12b: GEANT4 detector-map contract for HRD channel to Sci_bar layer mapping

## Abstract

Ticket `1781091056.1272.7ad60e8d` asks whether the analysis labels B2/B4/B6/B8 can be promoted from the S12a natural even-layer convention to a documented GEANT4 detector-map contract. The answer is **yes, for the analysed B-stack convention used by S12a**: the GEANT4 truth tree writes `Sci_bar_LayerID` from the sensitive-volume copy number, writes `Sci_bar_LayerID1` as the parent stack copy number, and the Krakow truth sample contains a stable stack `LayerID1=1` with analysed layers 0/2/4/6 at the expected 4 cm adjacent analysed-layer spacing. The carried-forward S12a benchmark winner remains **gradient_boosted_trees** with held-out MAE 0.000947 ns.

## 1. Reproduction gate

S12b reruns the S12a raw-ROOT selector over `h101/HRDv` files in `data/root/root`, using median samples 0..3 baseline subtraction and `A > 1000 ADC` on B2/B4/B6/B8. This directly reproduces the numerical gate needed for the ticket while preserving the same waveform definition as S12a.

| quantity                           |   expected |   reproduced_from_raw_root |   s12a_result_reproduced |   delta |   raw_files_present | selector_script                          | selector_config                            | pass   |
|:-----------------------------------|-----------:|---------------------------:|-------------------------:|--------:|--------------------:|:-----------------------------------------|:-------------------------------------------|:-------|
| S00 selected B-stave pulse records |     640737 |                     640737 |                   640737 |       0 |                  53 | scripts/s12a_0000000012_1_truthtiming.py | configs/s12a_0000000012_1_truthtiming.yaml | True   |

The reproduced count is computed in this S12b run from raw ROOT files; the S12a result column is retained only as an upstream consistency check.

## 2. Contract definition

The contract is

\[
f(c)=2k,\quad c\in\{B2,B4,B6,B8\},\quad k\in\{0,1,2,3\},
\]

with `Sci_bar_LayerID1 = 1` selecting the B-stack in the Krakow truth output and `Sci_bar_LayerID` selecting the scintillator bar/layer copy number inside that stack. In table form:

| hrd_channel   |   sci_bar_layer_id |   n_truth_hits_in_s12a_pairs |   median_x_cm |   median_y_cm |   median_z_cm | x_ci95_cm                                 | z_ci95_cm                               |   median_edep |
|:--------------|-------------------:|-----------------------------:|--------------:|--------------:|--------------:|:------------------------------------------|:----------------------------------------|--------------:|
| B2            |                  0 |                        92523 |      -66.2813 |    0.0119452  |       86.5384 | [-85.03570849561413, -49.00456688103519]  | [71.88580865547263, 100.03642170557116] |       12.152  |
| B4            |                  2 |                        92524 |      -68.7158 |    0.0116182  |       89.7124 | [-88.15423519959037, -50.801390218410354] | [74.52542142606893, 103.70866231899845] |       14.251  |
| B6            |                  4 |                        84413 |      -71.0463 |    0.011153   |       92.9677 | [-90.57834184068177, -53.231227979533465] | [77.70757461055506, 106.88633786178002] |       18.7969 |
| B8            |                  6 |                        59734 |      -69.2637 |    0.00402647 |       99.4364 | [-88.84743537977955, -55.5061749390642]   | [84.13597980957589, 110.18502736152382] |       21.7259 |

## 3. Source-code and ROOT-schema evidence

The GEANT4 hit code stores copy numbers as layer identifiers:

```cpp
  67:   G4int copyNo = touchable->GetCopyNumber();
  68:   G4int copyNo1 = -1;
  69:   if(touchable->GetHistoryDepth()>1) copyNo1 = touchable->GetCopyNumber(1);
  70:   G4int copyNo2 = -1;
  71:   if(touchable->GetHistoryDepth()>2) copyNo2 = touchable->GetCopyNumber(2);
  72: 
  73:   // G4int replicat1 = touchable->GetReplicaNumber(1);
  74:   // G4int replicat = touchable->GetReplicaNumber(0);
  75: 
  76:   int CurrentTrack = track->GetTrackID();
  77: 
  78:   auto it_layer = mapTrackID_Hits.find(copyNo);
  79:   if(it_layer == mapTrackID_Hits.end())
  80:     {
  81:       int IdHit        = fHitsCollection->GetSize();
  82:       SingleHit* newHit = new SingleHit(fHCID);
  83: 
  84:       newHit->Pdg         = track->GetDefinition()->GetPDGEncoding();
  85:       newHit->TrackID     = track->GetTrackID();
  86:       newHit->Edep        = energ_depos;
  87:       newHit->Time        = preStepPoint->GetGlobalTime();
  88:       newHit->TrackLength = track->GetTrackLength();
  89:       newHit->HitPosX     = localPosition.x();
  90:       newHit->HitPosY     = localPosition.y();
  91:       newHit->HitPosZ     = localPosition.z();
  92:   	  newHit->GlobalPosX  = worldPosition.x();
  93:       newHit->GlobalPosY  = worldPosition.y();
  94:       newHit->GlobalPosZ  = worldPosition.z();
  95:       newHit->MomX        = track->GetMomentum().x();
  96:       newHit->MomY        = track->GetMomentum().y();
  97:       newHit->MomZ        = track->GetMomentum().z();
  98:       newHit->LayerID     = copyNo;
  99:       newHit->LayerID1    = copyNo1;
 100:       newHit->LayerID2    = copyNo2;
 101: 
```

The ROOT writer creates and fills the corresponding `Sci_bar_*` columns:

```cpp
  90: 			{
  91: 				allHits.push_back(new MultiHits);
  92: 				analysisManager->CreateNtupleIColumn(nameDet[iDet]+"_TrackID", allHits[iDet]->TrackID);
  93: 				analysisManager->CreateNtupleIColumn(nameDet[iDet]+"_LayerID", allHits[iDet]->LayerID);
  94: 				analysisManager->CreateNtupleIColumn(nameDet[iDet]+"_LayerID1", allHits[iDet]->LayerID1);
  95: 				analysisManager->CreateNtupleIColumn(nameDet[iDet]+"_LayerID2", allHits[iDet]->LayerID2);
  96: 				analysisManager->CreateNtupleIColumn(nameDet[iDet]+"_PDG", allHits[iDet]->Pdg);
  97: 				analysisManager->CreateNtupleDColumn(nameDet[iDet]+"_EDep", allHits[iDet]->Edep);
  98: 				analysisManager->CreateNtupleDColumn(nameDet[iDet]+"_Time", allHits[iDet]->Time);
  99: 				analysisManager->CreateNtupleDColumn(nameDet[iDet]+"_TrackLength", allHits[iDet]->TrackLength);
 100: 				analysisManager->CreateNtupleDColumn(nameDet[iDet]+"_Position_X", allHits[iDet]->HitPosX);
 101: 				analysisManager->CreateNtupleDColumn(nameDet[iDet]+"_Position_Y", allHits[iDet]->HitPosY);
 102: 				analysisManager->CreateNtupleDColumn(nameDet[iDet]+"_Position_Z", allHits[iDet]->HitPosZ);
 103: 				analysisManager->CreateNtupleDColumn(nameDet[iDet]+"_GlobalPosition_X", allHits[iDet]->GlobalPosX);
 104: 				analysisManager->CreateNtupleDColumn(nameDet[iDet]+"_GlobalPosition_Y", allHits[iDet]->GlobalPosY);
 105: 				analysisManager->CreateNtupleDColumn(nameDet[iDet]+"_GlobalPosition_Z", allHits[iDet]->GlobalPosZ);
 106: 				analysisManager->CreateNtupleDColumn(nameDet[iDet]+"_Momentum_X", allHits[iDet]->MomX);
 107: 				analysisManager->CreateNtupleDColumn(nameDet[iDet]+"_Momentum_Y", allHits[iDet]->MomY);
```

```cpp
 306: 				if(TempHit->Edep>0){
 307: 					allHits[idCol]->TrackID.push_back( TempHit->TrackID);
 308: 					allHits[idCol]->LayerID.push_back( TempHit->LayerID);
 309: 					allHits[idCol]->LayerID1.push_back( TempHit->LayerID1);
 310: 					allHits[idCol]->LayerID2.push_back( TempHit->LayerID2);
 311: 					allHits[idCol]->HitPosX.push_back( TempHit->HitPosX / cm);
 312: 					allHits[idCol]->HitPosY.push_back( TempHit->HitPosY / cm);
 313: 					allHits[idCol]->HitPosZ.push_back( TempHit->HitPosZ / cm);
 314: 					allHits[idCol]->GlobalPosX.push_back( TempHit->GlobalPosX / cm);
```

The local truth file schema contains `Sci_bar_LayerID`, `Sci_bar_LayerID1`, `Sci_bar_LayerID2`, positions, times, momenta, and energy deposition. The configured detector list is `TARGET,ProtoTPC,Sci_bar`; `krakow_nBars1=8` and `krakow_nBars2=4` are recorded in the geometry configuration.

## 4. Coordinate and spacing audit

For adjacent analysed pairs \((0,2),(2,4),(4,6)\), S12a measured event-wise three-dimensional separations. S12b interprets the same table as a contract check: every adjacent HRD pair must be within 0.05 cm of 4 cm median centre-to-centre spacing, and channel order must be monotonic in `Sci_bar_LayerID`.

| hrd_pair   | sci_bar_pair   |   median_distance_cm | distance_ci95                           |   distance_minus_4cm_cm | within_spacing_contract   |
|:-----------|:---------------|---------------------:|:----------------------------------------|------------------------:|:--------------------------|
| B2-B4      | 0-2            |              4.02587 | [4.025592185765055, 4.026173034590801]  |               0.0258652 | True                      |
| B4-B6      | 2-4            |              4.02626 | [4.026023979652145, 4.026538598954171]  |               0.0262573 | True                      |
| B6-B8      | 4-6            |              4.02499 | [4.024740771890063, 4.0253059164913845] |               0.0249908 | True                      |

Contract verdict: **PASS**.

## 5. Benchmark panel carried forward

S12b has no new supervised target beyond deciding the detector-map contract. To keep the ticket-family gate comparable and avoid retraining an identical target, the benchmark table below is the S12a run-block split truth-timing bakeoff, carried forward unchanged. The strong traditional method is the calibrated relativistic kinematic TOF; learned methods include ridge, gradient-boosted trees, MLP, 1D-CNN, and a physics-residual MLP new architecture. CIs are held-out simulation-block bootstraps, with simulation blocks serving as run-like independent splits because the GEANT4 truth tree has no physical run branch.

| method                   | family                   |     n |      mae_ns | mae_ns_ci95                                    |   res68_abs_ns |      bias_ns |   p95_abs_ns |
|:-------------------------|:-------------------------|------:|------------:|:-----------------------------------------------|---------------:|-------------:|-------------:|
| gradient_boosted_trees   | ml_tree                  | 70094 | 0.000946615 | [0.000936312505211481, 0.0009586629266376646]  |    0.000893039 |  1.95767e-06 |   0.00301816 |
| physics_residual_mlp     | neural_physics_residual  | 70094 | 0.00156456  | [0.0015383069285486114, 0.0015918071456208598] |    0.00160352  | -0.000105609 |   0.00423272 |
| 1d_cnn                   | neural_sequence          | 70094 | 0.00230602  | [0.00228049924751229, 0.0023294419672071232]   |    0.00231405  | -0.000126777 |   0.00625045 |
| mlp                      | neural_tabular           | 70094 | 0.00256821  | [0.0025518917092577803, 0.002585249761089114]  |    0.00240329  | -0.00178195  |   0.00858867 |
| ridge                    | ml_linear                | 70094 | 0.00266398  | [0.0026304683194175384, 0.0026975794375888418] |    0.00276155  | -1.60768e-05 |   0.00730302 |
| calibrated_kinematic_tof | traditional_calibrated   | 70094 | 0.00903904  | [0.009001358825495447, 0.009086096983406032]   |    0.0102613   | -4.01269e-05 |   0.0190093  |
| truth_kinematic_tof      | traditional_relativistic | 70094 | 0.0174689   | [0.01731861109599224, 0.01763678219295567]     |    0.00370018  |  0.0174603   |   0.0379372  |
| nominal_4cm_notes        | traditional_fixed_note   | 70094 | 0.0339078   | [0.0338016120917753, 0.034018516679225626]     |    0.0363526   |  7.00172e-05 |   0.103254   |
| 4cm_190mev_tof           | traditional_fixed_energy | 70094 | 0.0716852   | [0.0714589341592719, 0.07198060621973172]      |    0.0363526   | -0.0716852   |   0.175009   |
| nominal_2cm_notes        | traditional_fixed_note   | 70094 | 0.15593     | [0.1556984363030909, 0.15620868631234056]      |    0.0363526   | -0.15593     |   0.259254   |
| 4cm_40mev_tof            | traditional_fixed_energy | 70094 | 0.159563    | [0.15924978235371792, 0.15978412729426755]     |    0.0363526   |  0.159492    |   0.209655   |

The strict held-out MAE winner named in `result.json` is **gradient_boosted_trees**.

## 6. Systematics and caveats

- The contract is for the analysed B-stack convention used in S12a, not a hardware-cabling proof from DAQ channel maps.
- `Sci_bar_LayerID1=1` is validated from the GEANT4 truth output and source-code copy-number path; if the geometry builder changes copy-number ordering, this contract must be rerun.
- The external `TGeoManager` ROOT geometry file is present, but uproot cannot fully deserialize this older TGeo payload in this environment; therefore the authoritative geometry evidence used here is the GEANT4 source code plus the produced truth-tree positions.
- Raw electronics offsets and HRD cabling labels are outside this GEANT4-only contract. They require detector logbook or DAQ-channel metadata.
- The S12a ML benchmark uses contiguous simulation blocks as run surrogates because the GEANT4 file has no physical run branch.

## 7. Conclusion

The S12b audit confirms the contract `B2->0`, `B4->2`, `B6->4`, `B8->6` for the GEANT4 Sci_bar B-stack truth mapping used by S12a. This resolves the S12a caveat that the even-layer mapping was only natural: it is now documented as a source-backed analysis contract with a 4 cm adjacent analysed-layer spacing. No novel follow-up ticket was appended.

## 8. Reproducibility

Command:

```bash
/home/billy/anaconda3/bin/python scripts/s12b_1781091056_1272_7ad60e8d_detector_map_contract.py --config configs/s12b_1781091056_1272_7ad60e8d_detector_map_contract.yaml
```

Artifacts: `result.json`, `contract_table.csv`, `layer_coordinate_summary.csv`, `benchmark_metrics.csv`, `raw_reproduction_gate.csv`, `manifest.json`, and this `REPORT.md`.
