#!/usr/bin/env python3
"""Patch ScatteringGenerator to direct-sample the source-bound p+d CM law.

The patched generator uses ``linear_node_pdf_exact_inverse_v1`` on the explicit
``measured_table_support_truncate_v1`` reference support. This patch mirrors the
tracked ``ScatteringGenerator.cc/.hh`` implementation so an external Geant4
checkout cannot silently retain the superseded linear-theta inverse.
"""
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
     +T+"std::vector<G4double> cdfTheta, cdfVal, cdfPdf; // exact inverse-CDF node state"),
]
patch(HH, hh_pairs)

BUILD_CDF = """void ScatteringGenerator::BuildSigmaCDF()
{
\t// Source-model IDs are intentionally literal so generator provenance can bind
\t// the numerical law rather than the generic phrase \"inverse CDF\".
\t//   cross_section_interpolation_mode = linear_node_pdf_exact_inverse_v1
\t//   cross_section_support_mode = measured_table_support_truncate_v1
\t//
\t// The table nodes define p(theta)=sigma(theta)*sin(theta). Between measured
\t// angles p(theta) is linearly interpolated; outside measured support the nominal
\t// reference distribution has zero probability. This truncation is an explicit
\t// source-model choice, not evidence that the physical cross section vanishes.
\tcdfTheta.clear();
\tcdfVal.clear();
\tcdfPdf.clear();
\tif(ang.size() < 2 || sigma.size() != ang.size()){ return; }

\t// Positive common density scaling cannot change a normalized source law.
\tG4double densityScale = 0.0;
\tfor(size_t k = 0; k < ang.size(); k++){
\t\tif(!std::isfinite(ang[k]) || !std::isfinite(sigma[k]) || sigma[k] < 0.0){
\t\t\tG4cerr << \"ScatteringGenerator::BuildSigmaCDF: non-finite/negative source node; CS sampling disabled.\" << G4endl;
\t\t\tcdfTheta.clear(); cdfVal.clear(); cdfPdf.clear();
\t\t\treturn;
\t\t}
\t\tif(k > 0 && !(ang[k] > ang[k-1])){
\t\t\tG4cerr << \"ScatteringGenerator::BuildSigmaCDF: angles are not strictly increasing; CS sampling disabled.\" << G4endl;
\t\t\tcdfTheta.clear(); cdfVal.clear(); cdfPdf.clear();
\t\t\treturn;
\t\t}
\t\tif(sigma[k] > densityScale) densityScale = sigma[k];
\t}
\tif(!(densityScale > 0.0)){
\t\tG4cerr << \"ScatteringGenerator::BuildSigmaCDF: zero source density; CS sampling disabled.\" << G4endl;
\t\treturn;
\t}

\tcdfTheta = ang;
\tcdfPdf.reserve(ang.size());
\tfor(size_t k = 0; k < ang.size(); k++){
\t\tG4double p = (sigma[k] / densityScale) * std::sin(ang[k]);
\t\tif(!std::isfinite(p) || p < 0.0){
\t\t\tG4cerr << \"ScatteringGenerator::BuildSigmaCDF: invalid node PDF; CS sampling disabled.\" << G4endl;
\t\t\tcdfTheta.clear(); cdfVal.clear(); cdfPdf.clear();
\t\t\treturn;
\t\t}
\t\tcdfPdf.push_back(p);
\t}

\tcdfVal.assign(cdfTheta.size(), 0.0);
\tfor(size_t i = 1; i < cdfTheta.size(); i++){
\t\tG4double dx  = cdfTheta[i] - cdfTheta[i-1];
\t\tG4double avg = 0.5 * (cdfPdf[i] + cdfPdf[i-1]);
\t\tcdfVal[i] = cdfVal[i-1] + avg * dx;
\t}
\tG4double norm = cdfVal.back();
\tif(!std::isfinite(norm) || !(norm > 0.0)){
\t\tG4cerr << \"ScatteringGenerator::BuildSigmaCDF: invalid CDF norm (\" << norm << \" ); CS sampling disabled.\" << G4endl;
\t\tcdfTheta.clear(); cdfVal.clear(); cdfPdf.clear();
\t\treturn;
\t}
\tfor(size_t i = 0; i < cdfVal.size(); i++) cdfVal[i] /= norm;
\tG4cout << \"ScatteringGenerator: inverse-CDF ready over measured support [\"
\t       << (ang.front()/pi)*180. << \",\" << (ang.back()/pi)*180. << \"] deg from \"
\t       << ang.size() << \" CS pts; interpolation=linear_node_pdf_exact_inverse_v1; \"
\t       << \"support=measured_table_support_truncate_v1.\" << G4endl;
}

G4double ScatteringGenerator::SampleThetaCM()
{
\t// Draw theta_cm from the linearly interpolated p(theta)=sigma(theta)*sin(theta)
\t// on measured support. BuildSigmaCDF stores exact trapezoid interval masses;
\t// this function uses the analytic quadratic interval-mass inverse, rather than
\t// interpolating theta linearly in cumulative probability.
\tif(cdfTheta.empty() || cdfVal.empty() || cdfPdf.empty()){ return pi * G4UniformRand(); }
\tif(cdfTheta.size() != cdfVal.size() || cdfTheta.size() != cdfPdf.size()){
\t\tG4cerr << \"ScatteringGenerator::SampleThetaCM: inconsistent CDF state; using uniform fallback.\" << G4endl;
\t\treturn pi * G4UniformRand();
\t}

\tG4double u = G4UniformRand();
\tstd::vector<G4double>::iterator it = std::lower_bound(cdfVal.begin(), cdfVal.end(), u);
\tsize_t i = (size_t)std::distance(cdfVal.begin(), it);
\tif(i == 0)               return cdfTheta.front();
\tif(i >= cdfTheta.size()) return cdfTheta.back();

\tG4double c0 = cdfVal[i-1], c1 = cdfVal[i];
\tif(!(c1 > c0)) return cdfTheta[i-1];
\tG4double frac = (u - c0) / (c1 - c0);
\tif(frac <= 0.0) return cdfTheta[i-1];
\tif(frac >= 1.0) return cdfTheta[i];

\tG4double left = cdfTheta[i-1];
\tG4double right = cdfTheta[i];
\tG4double width = right - left;
\tG4double a = cdfPdf[i-1];
\tG4double b = cdfPdf[i];
\tG4double intervalMass = 0.5 * (a + b) * width;
\tG4double targetMass = frac * intervalMass;
\tG4double slope = (b - a) / width;
\tG4double discriminant = a*a + 2.0*slope*targetMass;
\tif(discriminant < 0.0 && discriminant > -1e-14) discriminant = 0.0;
\tif(discriminant < 0.0){
\t\tG4cerr << \"ScatteringGenerator::SampleThetaCM: negative inverse-CDF discriminant; using interval midpoint.\" << G4endl;
\t\treturn 0.5 * (left + right);
\t}
\tG4double root = std::sqrt(discriminant);
\tG4double denominator = a + root;
\tG4double x = 0.0;
\tif(denominator > 0.0){
\t\t// Stable conjugate form of the quadratic solution:
\t\t// x = 2*y / (a + sqrt(a^2 + 2*k*y)).
\t\tx = 2.0 * targetMass / denominator;
\t}
\telse if(b > 0.0){
\t\tx = width * std::sqrt(frac);
\t}
\tif(x < 0.0) x = 0.0;
\tif(x > width) x = width;
\treturn left + x;
}

G4double ScatteringGenerator::EvalELoss(G4double in)"""

cc_pairs = [
    ('#include "ScatteringGenerator.hh"',
     '#include "ScatteringGenerator.hh"\n\n#include <cmath>'),
    (T+"// Random ejectile angle in cm system\n"+T+"G4double theta3cm=pi*G4UniformRand();",
     T+"// CM ejectile angle -- sampled from the declared central-value source model:\n"
     +T+"// linear_node_pdf_exact_inverse_v1 on measured_table_support_truncate_v1.\n"
     +T+"// Falls back to uniform when no cross-section file is configured.\n"
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
