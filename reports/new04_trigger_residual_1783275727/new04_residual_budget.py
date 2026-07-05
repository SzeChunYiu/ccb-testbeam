import json
# ---- Inputs (all traced to repo reports/docs) ----
# Coincidence window: "within 15 ns" (docs/01_setup_and_detector.md:27)
tau_window_ns = 15.0                 # the quoted window half/interpretation
Dt_full_ns    = 2*tau_window_ns      # resolving full width per task formula R_acc=R_A*R_B*(2*tau)
Dt_lo_ns      = tau_window_ns        # low variant: treat 15 ns as full window

# Beam / occupancy rate at 20 nA (Sample-I current). CORRECTED value:
# R_max = mu_max/tau_eff = 0.380/124.8ns = 3.045 MHz, ONE-SIDED UPPER BOUND
# (docs/06_pileup.md, docs/SYSTEMATIC_UNCERTAINTIES.md; the 4.22 MHz@90ns is retracted).
mu_max   = 0.380
tau_eff_ns = 124.8
R_max_Hz = mu_max/(tau_eff_ns*1e-9)  # ~3.045e6
R_B_Hz   = R_max_Hz                   # first B paddle sees ~ every B particle -> R_B ~ R_max (lower bound on paddle singles)

# MC ideal-trigger per-pd-event fractions (mv3_v5 REPORT):
f_A = 0.0365   # A-paddle fired
f_B = 0.111    # B-paddle fired
f_coinc = 0.0362  # two-arm coincidence  (A subset of B)
R_A_Hz = (f_A/f_B)*R_B_Hz            # ~0.33*R_B

# B-stave stopping profiles (fraction NON-B2 = 1 - B2):
nonB2_MCideal   = 1-0.997   # 0.003  ideal coincidence trigger (over-pure)
nonB2_dataSI    = 1-0.933   # 0.067  data Sample I
nonB2_dataSII   = 1-0.695   # 0.305  data Sample II  (= B-trigger-only = B-singles population)
nonB2_dataAll   = 1-0.876   # 0.124  all data
nonB2_MCuntrig  = 1-0.459   # 0.541  MC untriggered

resid_pts = (nonB2_dataSI - nonB2_MCideal)*100   # 6.4 points

def budget(Dt_ns, phi_rand):
    Dt=Dt_ns*1e-9
    # accidental-to-true ratio ~ R_B*Dt   (because R_true ~ R_A_from_pd and A subset B)
    ratio = R_A_Hz*R_B_Hz*Dt / (f_coinc/ (f_A) * R_A_Hz)  # = R_B*Dt*(f_A/f_coinc)
    f_acc = ratio/(1+ratio)
    contrib_pts = f_acc*phi_rand*100
    return f_acc, contrib_pts

print(f"R_max=R_B = {R_B_Hz/1e6:.3f} MHz (UPPER bound)")
print(f"R_A       = {R_A_Hz/1e6:.3f} MHz")
print(f"Residual to explain = {resid_pts:.1f} points (nonB2: {nonB2_MCideal*100:.1f}% -> {nonB2_dataSI*100:.1f}%)")
print()
rows=[]
for Dt,label in [(Dt_full_ns,"Dt=2tau=30ns"),(Dt_lo_ns,"Dt=tau=15ns")]:
    for phi,plab in [(nonB2_dataSII,"SII 0.305"),(nonB2_MCuntrig,"untrig 0.541")]:
        f_acc,c=budget(Dt,phi)
        rows.append((label,plab,f_acc,c))
        print(f"{label:14s} phi_rand={plab:14s} f_acc={f_acc*100:5.2f}%  ->  {c:4.2f} pts")

# Paddle-fidelity: deep-proton A-firing above truth 0.06%
# N_coinc(MC event/incl)=33176 ; deep-proton B events (untrig deepest B6/B8) ~ fire first B paddle
N_coinc=33176; N_deep_Bfired=84388
print("\nPaddle-fidelity (deep-proton A-firing p_deep vs truth 0.06%):")
for p in [0.0006,0.005,0.010,0.015]:
    admitted=N_deep_Bfired*p
    f=admitted/(N_coinc+admitted)
    print(f"  p_deep={p*100:4.2f}% -> {f*100:4.2f}% of Sample I are deep-proton -> {f*100:4.2f} pts non-B2")

# Data anchor: S10 current-dependent downstream excess
print("\nDATA anchor (S10): downstream topology 2nA 2.31% -> 20nA 3.34%")
print("  current-driven excess = 1.03 pts [0.64,1.42]; total 20nA downstream = 3.34 pts")

summary={
 "residual_points_to_explain": round(resid_pts,2),
 "framing": "Sample-I non-B2: MC ideal 0.3% vs data 6.7% = 6.4 pts (equiv B2 99.7->93.3)",
 "inputs":{
   "coincidence_window_ns":15.0,"window_source":"docs/01_setup_and_detector.md:27",
   "R_max_MHz_upper":round(R_B_Hz/1e6,3),"R_max_note":"mu_max0.380/tau_eff124.8ns; ONE-SIDED UPPER bound; 4.22MHz@90ns retracted",
   "R_A_MHz":round(R_A_Hz/1e6,3),"R_A_note":"from MC A:B fired ratio 0.0365/0.111",
   "MC_ideal_nonB2":nonB2_MCideal,"data_SI_nonB2":nonB2_dataSI,
   "data_SII_nonB2":nonB2_dataSII,"data_all_nonB2":nonB2_dataAll,"MC_untrig_nonB2":nonB2_MCuntrig,
   "MC_deep_proton_Afire_truth":0.0006,"MC_coinc_A_over_B_subset":True,
 },
 "accidentals":{
   "formula":"f_acc/(1-f_acc) ~= R_B*Dt (since R_true~R_A_from_pd, A subset B)",
   "f_acc_range_pct":[round(budget(Dt_lo_ns,nonB2_dataSII)[0]*100,2),round(budget(Dt_full_ns,nonB2_dataSII)[0]*100,2)],
   "f_acc_note":"UPPER bound (R_max is upper bound); 4.4% (15ns) - 8.4% (30ns)",
   "contrib_pts_SIIprofile":[round(budget(Dt_lo_ns,nonB2_dataSII)[1],2),round(budget(Dt_full_ns,nonB2_dataSII)[1],2)],
   "contrib_pts_untrigprofile":[round(budget(Dt_lo_ns,nonB2_MCuntrig)[1],2),round(budget(Dt_full_ns,nonB2_MCuntrig)[1],2)],
   "central_pts":2.0,
 },
 "paddle_fidelity":{
   "mechanism":"deep-proton conjugate-deuteron secondaries/straggling/real-threshold fire A above truth 0.06%",
   "contrib_pts_if_pdeep_0.5to1.5pct":[1.3,3.7],"central_pts":1.5,"constraint":"poorly bounded without data",
 },
 "data_anchor_S10":{
   "current_excess_pts":1.03,"current_excess_CI":[0.64,1.42],
   "total_20nA_downstream_pts":3.34,
   "interpretation":"independent DATA evidence rate-driven deep-stave contamination ~1-3 pts; brackets accidental estimate",
 },
 "budget_points":{
   "total":round(resid_pts,2),
   "accidentals_central":2.0,"accidentals_range":[1.3,2.6],
   "paddle_fidelity_central":1.5,"paddle_fidelity_range":[0.5,3.0],
   "unexplained_central":round(resid_pts-2.0-1.5,2),"unexplained_range":[0.0,4.0],
 },
 "verdict":"Accidentals are real & first-principles but MODEST (~2 pts, UPPER-bounded by R_max<=3.05MHz corrected); they do NOT alone close the 6.4-pt residual. Paddle/selection fidelity (deep-proton A-firing above the idealized 0.06% truth) is the larger, poorly-constrained term. No forced closure: ~2-3 pts remain genuinely unexplained. S10 data current-excess (~1 pt) independently confirms rate-driven contamination at the right scale.",
}
json.dump(summary,open("new04_summary.json","w"),indent=2)
print("\nwrote new04_summary.json")
