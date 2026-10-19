#!/usr/bin/env python3
"""Independent invariant-vector oracle & bounded C++ arithmetic-domain regression.

Compares a Geant4-source expression transcription, not the Geant4 program.
External 190MeV material/table/ROOT physics not validated.
"""
from __future__ import annotations
import itertools, json, math, subprocess, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
BIN=ROOT/'kinematics_scalar'
MP,MD=938.2720813,1875.61294257
THETA_DEG=[26.49,31.1,35.69,40.24,44.75,49.22,53.64,58.01,62.32,66.58,70.77,74.9,78.75,84.73,90.73,96.74,102.76,108.8,114.85,120.91,126.99,133.08,139.17,145.28,151.4,157.52,162.62,169.78]
T_GRID=[1.,10.,60.,100.,190.,250.]
PHI_GRID=[0.,math.pi/7,2*math.pi/7,math.pi/2,3*math.pi/4,math.pi,11*math.pi/7,15*math.pi/8]

def source_angles(T,th):
    """Literal scalar math, no Geant4 invocation. Use compiled C++ for 0/0 witness."""
    P=math.sqrt(T*T+2*T*MP); et=T+MP+MD
    beta=P/et; gamma=1/math.sqrt(1-beta**2)
    W=math.sqrt(et*et-P*P); Q=W-MP-MD
    tc3=(Q/2)*(Q+2*MD)/W;tc4=(Q/2)*(Q+2*MP)/W
    pc3=math.sqrt(tc3*tc3+2*tc3*MP);pc4=math.sqrt(tc4*tc4+2*tc4*MD)
    pcm=math.sqrt((tc3+MP)**2-MP**2)
    tan3=math.sin(th)/(gamma*(math.cos(th)+beta/(pc3/(tc3+MP))))
    tan4=math.sin(math.pi-th)/(gamma*(math.cos(math.pi-th)+beta/(pc4/(tc4+MD))))
    th3=math.atan2(tan3,1); th3=th3+math.pi if th3<0 else th3
    th4=math.atan2(tan4,1)
    t3=(gamma-1)*MP+gamma*tc3+gamma*beta*pcm*math.cos(th)
    t4=(gamma-1)*MD+gamma*tc4+gamma*beta*pcm*math.cos(math.pi-th)
    return th3,th4,t3,t4

def oracle(T,th,phi,flip):
    """Independent Mandelstam invariant + Lorentz-boost of four-vector."""
    P=math.sqrt(T*(T+2*MP)); et=T+MP+MD
    s=et*et-P*P;W=math.sqrt(s)
    k=math.sqrt((s-(MP+MD)**2)*(s-(MP-MD)**2))/(2*W)
    e3=(s+MP**2-MD**2)/(2*W);e4=(s+MD**2-MP**2)/(2*W)
    beta=P/et;gamma=et/W
    # flip True: proton azimuth +pi; otherwise deuteron azimuth +pi
    a=phi+(math.pi if flip else 0.)
    p3=(k*math.sin(th)*math.cos(a),k*math.sin(th)*math.sin(a),gamma*(k*math.cos(th)+beta*e3))
    p4=(-p3[0],-p3[1],gamma*(-k*math.cos(th)+beta*e4))
    en3=gamma*(e3+beta*k*math.cos(th));en4=gamma*(e4-beta*k*math.cos(th))
    return p3,p4,en3-MP,en4-MD,P

def source_vec(T,th,phi,flip):
    th3,th4,t3,t4=source_angles(T,th)
    az3=phi+(math.pi if flip else 0.)
    az4=phi+(0. if flip else math.pi)
    p3=math.sqrt(t3*(t3+2*MP));p4=math.sqrt(t4*(t4+2*MD))
    v3=(p3*math.sin(th3)*math.cos(az3),p3*math.sin(th3)*math.sin(az3),p3*math.cos(th3))
    v4=(p4*math.sin(th4)*math.cos(az4),p4*math.sin(th4)*math.sin(az4),p4*math.cos(th4))
    return v3,v4,t3,t4

def metrics():
    max_vec=max_t=max_balance=0.0;n=0
    for T,degree,phi,flip in itertools.product(T_GRID,THETA_DEG,PHI_GRID,(False,True)):
        th=math.radians(degree)
        pv,dv,t3,t4=source_vec(T,th,phi,flip)
        po,do,et3,et4,pin=oracle(T,th,phi,flip)
        max_vec=max(max_vec,*(abs(x-y) for x,y in zip(pv+dv,po+do)))
        max_t=max(max_t,abs(t3-et3),abs(t4-et4))
        max_balance=max(max_balance,abs(t3+t4-T),abs(pv[0]+dv[0]),abs(pv[1]+dv[1]),abs(pv[2]+dv[2]-pin))
        n+=1
    return {'vector_grid_points':n,'kinetic_energy_MeV':T_GRID,'source_node_angles_degrees':len(THETA_DEG), 'azimuth_angles':len(PHI_GRID),'coplanarity_branches':2,
     'max_source_vs_invariant_momentum_component_MeV_per_c':max_vec,'max_source_vs_invariant_kinetic_energy_MeV':max_t,'max_energy_or_momentum_balance_numerical_value':max_balance,
     'finite_domain_result':'CONDITIONAL_ALGEBRA_CONSISTENT_NOT_COMPILED_GEANT4'}

def compiled(T,theta):
    proc=subprocess.run([str(BIN),str(T),str(theta)],check=True,capture_output=True,text=True)
    return list(map(float,proc.stdout.split()))

def synthetic_stopping(initial=190.,thickness_mm=2.3,rate=100.):
    """Simulates exactly 100 original Euler iterations but NOT real CD2."""
    step=thickness_mm/100; e=initial
    for i in range(100):
        de=step*rate
        if de>e:
            return {'stopped':True,'kinetic_MeV':0.,'stopped_on_step':i+1,'toy_positive_stopping_MeV_per_mm':rate}
        e-=de
    return {'stopped':False,'kinetic_MeV':e}

class Tests(unittest.TestCase):
    def test_vector_boost_domain(self):
        m=metrics(); self.assertEqual(m['vector_grid_points'],2688)
        self.assertLess(m['max_source_vs_invariant_momentum_component_MeV_per_c'],1e-8)
        self.assertLess(m['max_source_vs_invariant_kinetic_energy_MeV'],1e-8)
    def test_zero_energy_cpp_nonfinite(self):
        result=compiled(0.0,math.pi/2)
        self.assertFalse(math.isfinite(result[0]))
        self.assertFalse(math.isfinite(result[1]))
        self.assertAlmostEqual(result[2],0.,delta=1e-10)
        self.assertAlmostEqual(result[3],0.,delta=1e-10)
        self.assertEqual(result[4:], [0.,0.])
    def test_near_zero_energy_finite_not_certified(self):
        arr=compiled(1e-5,math.pi/2)
        self.assertTrue(all(math.isfinite(x) for x in arr))
    def test_stopping_synthetic_reachable(self):
        obj=synthetic_stopping()
        self.assertTrue(obj['stopped'])
        self.assertEqual(obj['kinetic_MeV'],0.)
        self.assertFalse(math.isfinite(compiled(obj['kinetic_MeV'],math.pi/2)[0]))
    def test_normal_cpp_angles_finite(self):
        arr=compiled(190.,math.radians(84.73))
        self.assertTrue(all(math.isfinite(x) for x in arr))
        th3,th4,t3,t4=source_angles(190.,math.radians(84.73))
        for x,y in zip(arr[:4],(th3,th4,t3,t4)):
            self.assertAlmostEqual(x,y,delta=1e-9)

if __name__=='__main__':
    s=unittest.defaultTestLoader.loadTestsFromTestCase(Tests)
    res=unittest.TextTestRunner(verbosity=2).run(s)
    if not res.wasSuccessful():sys.exit(1)
    report={'schema':'ccb-generator-domain/1','source_main_revision':'a61427813344e29047ca9eb9b764182eb29e4c83','source_scattering_generator_blob':'a04da519551a7d505b4bce50b20d0b5424f0f40d',
      'source_header_blob':'3492d2b61fcc7320070837cff241089f40e4882d',
      'source_crosssection_blob':'7c0ed5a5b692f58d7b183f60805ee64630a74a76',
      'source_configuration_accepts_zero_incident_energy':True,
      'compiled_cpp_Ekin_zero_theta3_theta4':compiled(0.0,math.pi/2)[:2],
      'compiled_cpp_Ekin_zero_betas':compiled(0.0,math.pi/2)[4:],
      'synthetic_positive_stopping_to_zero':synthetic_stopping(),
      'independent_vector_kinematics':metrics(),
      'source_file_scope':'copied scalar expressions; no compiled Geant4 app/ROOT/hardware or runtime stopping table',
      'real_190MeV_run_affected':'NOT_ESTABLISHED','scientific_release':'NOT_AUTHORIZED'}
    # JSON spec disallows NaN; encode nonfinite as named strings.
    report['compiled_cpp_Ekin_zero_theta3_theta4']=['NaN' if math.isnan(x) else str(x) for x in report['compiled_cpp_Ekin_zero_theta3_theta4']]
    (ROOT/'RESULT.json').write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':'SYNTHETIC_AND_SCALAR_SOURCE_CHECK_PASS_REAL_PHYSICS_BLOCKED','details':report},sort_keys=True))
