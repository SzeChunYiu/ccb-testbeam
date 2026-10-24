"""Independent numerical physics/statistics fixtures; not a Geant4 transport run."""
from pathlib import Path
import json, numpy as np
from scipy.integrate import quad
from scipy.stats import beta, norm
BASE=Path(__file__).resolve().parent
(BASE/'evidence').mkdir(exist_ok=True)
# Numerical transcription of the repository table; NOT verified against Table VI of the paper.
table=np.array([
[26.49,6.005,.011],[31.1,4.383,.007],[35.69,3.123,.009],[40.24,2.363,.005],[44.75,1.71,.008],[49.22,1.388,.004],[53.64,1.037,.006],[58.01,.78,.004],[62.32,.624,.005],[66.58,.523,.003],[70.77,.429,.003],[74.9,.341,.002],[78.75,.273,.002],[84.73,.222,.001],[90.73,.18,.001],[96.74,.164,.001],[102.76,.137,.001],[108.8,.129,.001],[114.85,.129,.001],[120.91,.126,.001],[126.99,.146,.001],[133.08,.156,.001],[139.17,.18,.001],[145.28,.201,.001],[151.4,.264,.001],[157.52,.305,.002],[162.62,.351,.003],[169.78,.446,.002]])
theta=np.deg2rad(table[:,0]);sigma=table[:,1];pdf=sigma*np.sin(theta);width=np.diff(theta)
mass=.5*(pdf[:-1]+pdf[1:])*width;cdf=np.r_[0,np.cumsum(mass)];Z=cdf[-1];cdf/=Z
# Equivalent inversion of the documented piecewise-linear node density.
rng=np.random.default_rng(1628);u=rng.random(200000);idx=np.searchsorted(cdf,u,side='right')-1
frac=(u-cdf[idx])/(cdf[idx+1]-cdf[idx]);slope=(pdf[idx+1]-pdf[idx])/width[idx]
y=frac*mass[idx];x=2*y/(pdf[idx]+np.sqrt(pdf[idx]**2+2*slope*y));samples=theta[idx]+x
recovered=cdf[idx]+(pdf[idx]*x+.5*slope*x*x)/Z
# Independent quadrature of a different, defensible interpolation model: linear sigma * sin(theta).
qmass=np.array([quad(lambda t,a=a,b=b,sa=sa,sb=sb:(sa+(sb-sa)*(t-a)/(b-a))*np.sin(t),a,b,epsabs=1e-12)[0] for a,b,sa,sb in zip(theta[:-1],theta[1:],sigma[:-1],sigma[1:])]);qZ=qmass.sum();qCDF=np.r_[0,qmass.cumsum()]/qZ
cdfout={'nodes':len(theta),'draws':len(u),'max_inverse_roundtrip_error':float(np.max(np.abs(recovered-u))),'draws_outside_declared_support':int(((samples<theta[0])|(samples>theta[-1])).sum()),'support_degrees':[float(table[0,0]),float(table[-1,0])],'piecewise_pdf_integral_mb_over_sr_rad':float(Z),'linear_sigma_times_sin_integral_mb_over_sr_rad':float(qZ),'relative_normalization_difference':float(qZ/Z-1),'max_CDF_difference_at_table_nodes':float(np.max(abs(qCDF-cdf))),'scope':'Numerical translation of declared law versus independent quadrature; not compiled Geant4 source execution or experimental source uncertainty.'}
assert cdfout['max_inverse_roundtrip_error']<1e-12 and cdfout['draws_outside_declared_support']==0
# Test the published source algebra against a distinct invariant-mass/boost implementation.
mp=938.2720813;md=1875.61294257 # explicit numerical fixture masses [MeV/c^2], not fitted constants
errs=[]
for T in [1.,10.,60.,100.,190.,250.]:
 th=np.linspace(1e-5,np.pi-1e-5,2001);Pin=np.sqrt(T*T+2*T*mp);Etot=T+mp+md;ss=Etot**2-Pin**2;W=np.sqrt(ss);b=Pin/Etot;g=1/np.sqrt(1-b*b)
 q=W-mp-md;T3c=.5*q*(q+2*md)/W;T4c=.5*q*(q+2*mp)/W;p=np.sqrt((mp+T3c)**2-mp**2)
 # Formula transcribed from ScatteringGenerator.cc.
 T3=(g-1)*mp+g*T3c+g*b*p*np.cos(th);T4=(g-1)*md+g*T4c-g*b*p*np.cos(th)
 # Independent Kallen invariant and boosted four vectors.
 pc=np.sqrt((ss-(mp+md)**2)*(ss-(mp-md)**2))/(2*W);E3c=(ss+mp**2-md**2)/(2*W);E4c=(ss+md**2-mp**2)/(2*W)
 p3z=g*(pc*np.cos(th)+b*E3c);p4z=g*(-pc*np.cos(th)+b*E4c);p3t=pc*np.sin(th);p4t=-p3t
 E3=np.sqrt(mp**2+p3z**2+p3t**2);E4=np.sqrt(md**2+p4z**2+p4t**2)
 errs.append({'T_MeV':T,'angles':len(th),'max_source_vs_invariant_T_MeV':float(max(np.max(abs(T3-(E3-mp))),np.max(abs(T4-(E4-md))))),'max_energy_balance_MeV':float(np.max(abs(T3+T4-T))),'max_longitudinal_momentum_balance_MeV_c':float(np.max(abs(p3z+p4z-Pin))),'max_transverse_momentum_balance_MeV_c':float(np.max(abs(p3t+p4t)))})
assert max(x['max_source_vs_invariant_T_MeV'] for x in errs)<1e-8
# Correct 8x18 -> first128 words -> WRONG 8x16 boundary artifact, even with pedestal-only channels.
raw=np.repeat((7000+np.array([0,2000,0,2000,0,2000,0,2000]))[:,None],18,axis=1)
wrong=raw.ravel()[:128].reshape(8,16);steps=[np.flatnonzero(np.diff(wrong[ch])).tolist() for ch in range(8)]
rawout={'source_words':int(raw.size),'truncated_words':int(wrong.size),'original_channels_peak_minus_baseline':[0]*8,'wrong_channel_peak_minus_median_first4':(wrong.max(1)-np.median(wrong[:,:4],axis=1)).tolist(),'step_after_zero_based_sample':steps,'scope':'known-answer synthetic baseline-only fixture; no real waveform processed'}
# Replicated Monte Carlo coverage of Gaussian cluster means. Compare naive event SEM to known model SE.
# This coverage experiment is an independent counterexample, not the repository bootstrap execution.
rng=np.random.default_rng(20261018);R=20000;G=20;n=200;sg=.1;se=.01
# Sufficient stats permit exact draw of independent event-noise group means and within-group sum of squares.
gmeans=rng.normal(0,np.sqrt(sg**2+se**2/n),(R,G));means=gmeans.mean(1)
within=se**2*rng.chisquare(G*(n-1),R);between=n*np.sum((gmeans-means[:,None])**2,axis=1)
naive_se=np.sqrt((within+between)/(G*n-1)/(G*n));true_se=np.sqrt(sg**2/G+se**2/(G*n));z=norm.ppf(.84)
count_naive=int(np.count_nonzero(abs(means)<=z*naive_se));count_true=int(np.count_nonzero(abs(means)<=z*true_se))
def cp(k,N):return [float(beta.ppf(.025,k,N-k+1)) if k else 0.,float(beta.ppf(.975,k+1,N-k)) if k<N else 1.]
coverage={'repetitions':R,'groups':G,'events_per_group':n,'group_sd':sg,'event_sd':se,'nominal_central_coverage':.68,'event_iid_normal_interval_coverage':count_naive/R,'event_iid_coverage_MC_CP95':cp(count_naive,R),'correct_known_variance_coverage':count_true/R,'correct_coverage_MC_CP95':cp(count_true,R),'scope':'exact Gaussian sufficient-statistic Monte Carlo; evaluates iid normal SEM, NOT literal A09 bootstrap coverage, and NOT beam/transport simulation.'}
# Conditional zero-count intervals for recorded trigger summary; species counts independently recomputed.
trigger={'deuteron_proxy_count':550,'deuteron_denominator':1487,'recomputed_deuteron_efficiency':550/1487,'proton_proxy_count':4,'proton_denominator':5598,'recomputed_proton_efficiency':4/5598,'total_proxy_species_counts':554,'CP95_twosided_upper_0_of_554':float(beta.ppf(.975,1,554)),'CP95_onesided_upper_0_of_1000000':float(beta.ppf(.95,1,1000000)),'scope':'arithmetic on PR1544 stored JSON, not verified raw MC; do not assume species populations independent/disjoint without event identities.'}
out={'scope':'INDEPENDENT_SYNTHETIC_AND_NUMERICAL_CHECKS_NO_DETECTOR_CLEARANCE','source_main':'a61427813344e29047ca9eb9b764182eb29e4c83','source_generator_blob':'a04da519551a7d505b4bce50b20d0b5424f0f40d','source_table_blob':'7c0ed5a5b692f58d7b183f60805ee64630a74a76','angular_source':cdfout,'elastic_kinematics':errs,'waveform_truncation':rawout,'coverage_experiment':coverage,'trigger_record_arithmetic':trigger,'optical_energy_test_warning':'Geant4 generated optical photons must not be added to event transport energy balance (official Developer Guide section Optical Photons).','DAQ_rate_warning':'V1742 vendor 110/181 us conversion deadtime implies conditional per-busy-domain ceiling about 9091/5525 triggers/s; this is NOT a CCB hardware identification or detector rate measurement.'}
(BASE/'evidence/physics_crosschecks.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n');print(json.dumps(out,indent=2))
