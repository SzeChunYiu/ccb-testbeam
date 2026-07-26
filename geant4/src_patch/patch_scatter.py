#!/usr/bin/env python3
"""Patch ScatteringGenerator to sample theta_cm FROM the p+CD2 cross-section
distribution (inverse-CDF) instead of uniform-in-[0,pi]. CL-021 fix."""
import sys
SRC = "/projects/hep/fs10/shared/nnbar/billy/hg4_src_scatter"
HH  = SRC + "/include/ScatteringGenerator.hh"
CC  = SRC + "/src/ScatteringGenerator.cc"

def patch(path, pairs):
    with open(path) as f: s = f.read()
    for i,(old,new) in enumerate(pairs):
        n = s.count(old)
        if n != 1:
            sys.exit("FAIL %s pair#%d count=%d for %r" % (path, i, n, old[:70]))
        s = s.replace(old, new, 1)
    with open(path,"w") as f: f.write(s)
    print("OK %s: %d replacements" % (path, len(pairs)))

T = "\t"
hh_pairs = [
    (T+"G4double EvalWeight(G4double);",
     T+"G4double EvalWeight(G4double);\n"
     +T+"G4double SampleThetaCM();\n"
     +T+"void BuildSigmaCDF();"),
    (T+"std::vector<G4double> ang, sigma;",
     T+"std::vector<G4double> ang, sigma;\n"
     +T+"std::vector<G4double> cdfTheta, cdfVal; // inverse-CDF for CS-weighted CM sampling"),
]
patch(HH, hh_pairs)

BUILD_CDF = """void ScatteringGenerator::BuildSigmaCDF()
{
\t// Build inverse-CDF to sample theta_cm from p(theta) ~ sigma(theta)*sin(theta).
\t// sin(theta) is the solid-angle Jacobian (dOmega = sin dtheta dphi); the table
\t// holds d(sigma)/dOmega per steradian, so the angle PDF weights by sin(theta).
\t//
\t// Coverage: the table spans only [ang_front, ang_back] (~26.5-169.8 deg). Outside
\t// that window the boundary value is held constant -- no fabricated forward peak
\t// below ang_front (conservative; documented as a possible under-peaking source).
\t// Endpoints theta=0 and theta=pi carry zero probability (sin=0).
\tcdfTheta.clear();
\tcdfVal.clear();
\tif(ang.size() < 2 || sigma.size() < 2){ return; }

\tstd::vector<G4double> nodes, pdf;
\tnodes.push_back(0.0);
\tpdf.push_back(sigma.front() * std::sin(0.0));
\tfor(size_t k = 0; k < ang.size(); k++){
\t\tnodes.push_back(ang[k]);
\t\tpdf.push_back(sigma[k] * std::sin(ang[k]));
\t}
\tnodes.push_back(pi);
\tpdf.push_back(sigma.back() * std::sin(pi));

\tcdfTheta = nodes;
\tcdfVal.assign(nodes.size(), 0.0);
\tfor(size_t i = 1; i < nodes.size(); i++){
\t\tG4double dx  = nodes[i] - nodes[i-1];
\t\tG4double avg = 0.5 * (pdf[i] + pdf[i-1]);
\t\tcdfVal[i] = cdfVal[i-1] + avg * dx;
\t}
\tG4double norm = cdfVal.back();
\tif(!(norm > 0.0)){
\t\tG4cerr << "ScatteringGenerator::BuildSigmaCDF: non-positive CDF norm (" << norm << "); CS sampling disabled." << G4endl;
\t\tcdfTheta.clear(); cdfVal.clear();
\t\treturn;
\t}
\tfor(size_t i = 0; i < cdfVal.size(); i++) cdfVal[i] /= norm;
\tG4cout << "ScatteringGenerator: inverse-CDF ready over [0,pi] from " << ang.size()
\t       << " CS pts (data range [" << (ang.front()/pi)*180. << ","
\t       << (ang.back()/pi)*180. << "] deg; constant-extrapolated outside)." << G4endl;
}

G4double ScatteringGenerator::SampleThetaCM()
{
\t// Draw theta_cm from p(theta) ~ sigma(theta)*sin(theta) via inverse-CDF.
\t// Falls back to uniform in [0,pi] when no CDF is built (no CS file loaded).
\tif(cdfTheta.empty() || cdfVal.empty()){ return pi * G4UniformRand(); }

\tG4double u = G4UniformRand();
\tstd::vector<G4double>::iterator it = std::lower_bound(cdfVal.begin(), cdfVal.end(), u);
\tsize_t i = (size_t)std::distance(cdfVal.begin(), it);
\tif(i == 0)               return cdfTheta.front();
\tif(i >= cdfTheta.size()) return cdfTheta.back();
\tG4double c0 = cdfVal[i-1], c1 = cdfVal[i];
\tG4double frac = (c1 > c0) ? (u - c0) / (c1 - c0) : 0.0;
\treturn cdfTheta[i-1] + frac * (cdfTheta[i] - cdfTheta[i-1]);
}

G4double ScatteringGenerator::EvalELoss(G4double in)"""

cc_pairs = [
    (T+"// Random ejectile angle in cm system\n"+T+"G4double theta3cm=pi*G4UniformRand();",
     T+"// CM ejectile angle -- sampled FROM the p+CD2 differential cross-section\n"
     +T+"// distribution p(theta) ~ sigma(theta)*sin(theta) (inverse-CDF), fixing the\n"
     +T+"// MV3 scattering-model residual (CL-021). Falls back to uniform when no CS.\n"
     +T+"G4double theta3cm = SampleThetaCM();"),
    (T+"particle1->SetKineticEnergy(Ekin3);\n"+T+"if(haveWeights) particle1->SetWeight(EvalWeight(theta3));",
     T+"particle1->SetKineticEnergy(Ekin3);\n"
     +T+"// Direct CS-weighted sampling -> event weight is unity (SampleThetaCM already\n"
     +T+"// draws from p(theta)~sigma*sin(theta); EvalWeight would double-count). The\n"
     +T+"// GAP-01 importance-weighting path is retired (analysis is unweighted)."),
    (T+"particle2->SetKineticEnergy(Ekin4);\n"+T+"if(haveWeights) particle2->SetWeight(EvalWeight(theta3));",
     T+"particle2->SetKineticEnergy(Ekin4);\n"
     +T+"// (event weight unity -- see note above)"),
    (T+"LoadCrossSection();\n"+T+"haveWeights=true;",
     T+"LoadCrossSection();\n"+T+"BuildSigmaCDF();\n"+T+"haveWeights=true;"),
    ("G4double ScatteringGenerator::EvalELoss(G4double in)", BUILD_CDF),
]
patch(CC, cc_pairs)
print("DONE")
