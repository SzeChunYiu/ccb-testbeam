//
// ********************************************************************
// * License and Disclaimer                                           *
// *                                                                  *
// * The  Geant4 software  is  copyright of the Copyright Holders  of *
// * the Geant4 Collaboration.  It is provided  under  the terms  and *
// * conditions of the Geant4 Software License,  included in the file *
// * LICENSE and available at  http://cern.ch/geant4/license .  These *
// * include a list of copyright holders.                             *
// *                                                                  *
// * Neither the authors of this software system, nor their employing *
// * institutes,nor the agencies providing financial support for this *
// * work  make  any representation or  warranty, express or implied, *
// * regarding  this  software system or assume any liability for its *
// * use.  Please see the license in the file  LICENSE  and URL above *
// * for the full disclaimer and the limitation of liability.         *
// *                                                                  *
// * This  code  implementation is the result of  the  scientific and *
// * technical work of the GEANEkin4 collaboration.                      *
// * By using,  copying,  modifying or  distributing the software (or *
// * any work based  on the software)  you  agree  to acknowledge its *
// * use  in  resulting  scientific  publications,  and indicate your *
// * acceptance of all terms of the Geant4 Software license.          *
// ********************************************************************
//
/// \file ScatteringGenerator.cc
/// \brief Implementation of the ScatteringGenerator1 class
//
// 
//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......
//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

#include "ScatteringGenerator.hh"

#include "G4Event.hh"
#include "G4GenericMessenger.hh"
#include "G4ParticleTable.hh"
#include "G4PrimaryVertex.hh"
#include "G4PhysicalConstants.hh"
#include "G4SystemOfUnits.hh"
#include "Randomize.hh"
#include <cmath>

#include "G4Threading.hh"
#include "G4AutoLock.hh"

namespace {G4Mutex ScatteringGeneratorMutex = G4MUTEX_INITIALIZER;}


ScatteringGenerator::ScatteringGenerator():
	fIncEnergy(150.*MeV),
	fTgtThickness(2.3*mm),
	fBeamspot(10*mm),
	fDEdxFile("dedx_p_in_CD2.txt"),
	fCSFile("null")
{
	DefineCommands();
	//LoadELossTable();
}

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

ScatteringGenerator::~ScatteringGenerator()
{ 
	delete fMessenger;
}


//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

void ScatteringGenerator::GeneratePrimaryVertex(G4Event* event)
{
	// Define setup geometry
	const G4double det_size = 5*cm;
	const G4double det_distance = 1*m;
	G4double phi_max = atan2(det_size/2.,det_distance);	// we will only generate particles in covered phi range.
		
	// Set random interaction point in target
	G4double r0=fBeamspot*sqrt(G4UniformRand());
	G4double ph0=2*pi*G4UniformRand();
	G4double x0=r0*cos(ph0);
	G4double y0=r0*sin(ph0);
	G4double z0=fTgtThickness*G4UniformRand()-fTgtThickness/2;
	
	position.setRhoPhiZ(r0,ph0,z0);
	//position.set(x0,y0,z0);

	// Calculate reaction kinematics
	// Particle types
	partdef1 = G4ParticleTable::GetParticleTable()->FindParticle("proton");
	partdef2 = G4ParticleTable::GetParticleTable()->FindParticle("deuteron");
	
	// Particle mass and beam energy
	G4double m1 = partdef1->GetPDGMass();
	G4double m2 = partdef2->GetPDGMass();
	G4double m3 = m1;
	G4double m4 = m2; 
	if(event->GetEventID()==0) LoadFiles();
	G4double Ekin = BeamEnergy(z0+fTgtThickness/2.);
	
	// Incoming energy, momentum, etc
	G4double E1 = Ekin+m1;
	G4double E2 = m2;
	G4double p1 = sqrt(Ekin*Ekin+2*Ekin*m1);
	G4double p2 = 0;
	G4double beta = (p1+p2)/(E1+E2);
	G4double gamma = 1/(sqrt(1-beta*beta));
	G4double Ecm = sqrt(pow((E1+E2),2)-pow((p1+p2),2));
	G4double Ekincm = Ecm-m1-m2;

	// Outgoing energies etc in center-of-mass
	G4double Ekin3cm = (Ekincm/2)*(Ekincm+2*m4)/Ecm;
	G4double Ekin4cm = (Ekincm/2)*(Ekincm+2*m3)/Ecm;
	G4double E3cm = Ekin3cm+m3;
	G4double E4cm = Ekin4cm+m4;
	G4double p3cm = sqrt(Ekin3cm*Ekin3cm+2*Ekin3cm*m3);
	G4double p4cm = sqrt(Ekin4cm*Ekin4cm+2*Ekin4cm*m4);
	G4double beta3cm = p3cm/E3cm;
	G4double beta4cm = p4cm/E4cm;
	G4double pcm= sqrt(E3cm*E3cm-m3*m3);

	// CM ejectile angle -- sampled FROM the p+CD2 differential cross-section
	// distribution p(theta) ~ sigma(theta)*sin(theta) (inverse-CDF), fixing the
	// MV3 scattering-model residual (CL-021). Falls back to uniform when no CS.
	G4double theta3cm = SampleThetaCM();
	// Ejectile
	G4double tantheta3 = sin(theta3cm)/(gamma*(cos(theta3cm)+beta/beta3cm));
	G4double theta3 = atan2(tantheta3,1);
	theta3 = (theta3<0) ? theta3+pi : theta3;
	G4double Ekin3 = (gamma-1)*m3+gamma*Ekin3cm+gamma*beta*pcm*cos(theta3cm);
	// Recoil
	G4double tantheta4 = sin(pi-theta3cm)/(gamma*(cos(pi-theta3cm)+beta/beta4cm));
	G4double theta4 = atan2(tantheta4,1);
	//theta4 = (theta4<0) ? theta4-pi : theta4;
	G4double Ekin4 = (gamma-1)*m4+gamma*Ekin4cm+gamma*beta*pcm*cos(pi-theta3cm);

	// Randomly generate phi within covered angular range
	G4double phi3 = 2*phi_max*G4UniformRand()-phi_max;
	G4double phi4 = phi3;
	G4double fiftyfifty = G4UniformRand();
	if(fiftyfifty<0.5){ phi3+=pi; }
	else{ phi4+=pi; }

	//particle 1 at vertex A
	G4ThreeVector mom1, mom2;
	mom1.setRThetaPhi(1,theta3,phi3);
	mom2.setRThetaPhi(1,theta4,phi4);
	
	// Create particles with energy and momentum from kinematics
	particle1 = new G4PrimaryParticle(partdef1);
	particle1->SetMomentumDirection(mom1);    
	particle1->SetKineticEnergy(Ekin3);
	// Direct CS-weighted sampling -> event weight is unity (SampleThetaCM already
	// draws from p(theta)~sigma*sin(theta); EvalWeight would double-count). The
	// GAP-01 importance-weighting path is retired (analysis is unweighted).
	
	particle2 = new G4PrimaryParticle(partdef2);
	particle2->SetMomentumDirection(mom2);    
	particle2->SetKineticEnergy(Ekin4);
	// (event weight unity -- see note above)
	
	G4double time = 0*s;
	
	G4PrimaryVertex* vertex = new G4PrimaryVertex(position, time);
	vertex->SetPrimary(particle1);
	vertex->SetPrimary(particle2);
	event->AddPrimaryVertex(vertex);
}

void ScatteringGenerator::LoadFiles()
{
	G4cout << "Reading energy loss values from " << fDEdxFile << G4endl;
	LoadELossTable();
	haveWeights=false;
	if(fCSFile=="null") return;
	
	G4cout << "Reading differential cross sections from " << fCSFile << G4endl;
	LoadCrossSection();
	BuildSigmaCDF();
	haveWeights=true;
}

void ScatteringGenerator::LoadELossTable()
{
	std::ifstream infile;
	char line[100];

	infile.open(fDEdxFile); 
	if(!infile.is_open()){
		printf("Cannot open the file %s!!\n",fDEdxFile.c_str());
		exit(0);
	}

	while(infile.getline(line,100)){
		G4double tmpE, tmpDEdx;
		sscanf(line,"%lf\t%lf\n",&tmpE,&tmpDEdx);
		Ene.push_back(tmpE*938.28/931.5); // MeV/u to MeV
		dEdx.push_back(tmpDEdx*1000.); // um to mm
	}    
	infile.close();
}

void ScatteringGenerator::LoadCrossSection()
{
	std::ifstream infile;
	char line[100];

	infile.open(fCSFile); 
	if(!infile.is_open()){
		printf("Cannot open the file %s!!\n",fCSFile.c_str());
		exit(0);
	}

	while(infile.getline(line,100)){
		G4double tmpA, tmpCS;
		sscanf(line,"%lf\t%lf\t%*f\n",&tmpA,&tmpCS);
		ang.push_back(tmpA*pi/180.); // deg to rad
		sigma.push_back(tmpCS);
	}    
	infile.close();
}

void ScatteringGenerator::BuildSigmaCDF()
{
	// Build inverse-CDF to sample theta_cm from p(theta) ~ sigma(theta)*sin(theta).
	// sin(theta) is the solid-angle Jacobian (dOmega = sin dtheta dphi); the table
	// holds d(sigma)/dOmega per steradian, so the angle PDF weights by sin(theta).
	//
	// Coverage: the table spans only [ang_front, ang_back] (~26.5-169.8 deg). Outside
	// that window the boundary value is held constant -- no fabricated forward peak
	// below ang_front (conservative; documented as a possible under-peaking source).
	// Endpoints theta=0 and theta=pi carry zero probability (sin=0).
	cdfTheta.clear();
	cdfVal.clear();
	if(ang.size() < 2 || sigma.size() < 2){ return; }

	std::vector<G4double> nodes, pdf;
	nodes.push_back(0.0);
	pdf.push_back(sigma.front() * std::sin(0.0));
	for(size_t k = 0; k < ang.size(); k++){
		nodes.push_back(ang[k]);
		pdf.push_back(sigma[k] * std::sin(ang[k]));
	}
	nodes.push_back(pi);
	pdf.push_back(sigma.back() * std::sin(pi));

	cdfTheta = nodes;
	pdfNode  = pdf;
	cdfVal.assign(nodes.size(), 0.0);
	cdfIntervalMass.assign(nodes.size(), 0.0);
	for(size_t i = 1; i < nodes.size(); i++){
		G4double dx  = nodes[i] - nodes[i-1];
		G4double avg = 0.5 * (pdf[i] + pdf[i-1]);
		cdfVal[i] = cdfVal[i-1] + avg * dx;
		cdfIntervalMass[i] = avg * dx;
	}
	G4double norm = cdfVal.back();
	if(!(norm > 0.0)){
		G4cerr << "ScatteringGenerator::BuildSigmaCDF: non-positive CDF norm (" << norm << "); CS sampling disabled." << G4endl;
		cdfTheta.clear(); cdfVal.clear();
		return;
	}
	for(size_t i = 0; i < cdfVal.size(); i++) cdfVal[i] /= norm;
	G4cout << "ScatteringGenerator: inverse-CDF ready over [0,pi] from " << ang.size()
	       << " CS pts (data range [" << (ang.front()/pi)*180. << ","
	       << (ang.back()/pi)*180. << "] deg; constant-extrapolated outside)." << G4endl;
}

G4double ScatteringGenerator::SampleThetaCM()
{
	// Draw theta_cm from p(theta) ~ sigma(theta)*sin(theta) via inverse-CDF.
	// Falls back to uniform in [0,pi] when no CDF is built (no CS file loaded).
	if(cdfTheta.empty() || cdfVal.empty() || cdfIntervalMass.empty()){ return pi * G4UniformRand(); }

	G4double u = G4UniformRand();
	std::vector<G4double>::iterator it = std::lower_bound(cdfVal.begin(), cdfVal.end(), u);
	size_t i = (size_t)std::distance(cdfVal.begin(), it);
	if(i == 0)               return cdfTheta.front();
	if(i >= cdfTheta.size()) return cdfTheta.back();

	// Within interval [theta_{i-1}, theta_i] of width h, the node densities
	// g0 = pdfNode[i-1], g1 = pdfNode[i] define a linear density
	//   g(x) = g0 + m*x,  m = (g1 - g0)/h.
	// The partial mass from interval start to offset x is the quadratic
	//   M(x) = g0*x + 0.5*m*x^2.
	// A uniform r in [0,1] maps to the x with M(x) = r*A_i, where A_i is the
	// total trapezoid interval mass. Solving the quadratic for x in [0,h]:
	//   x = (-g0 + sqrt(g0^2 + 2*m*r*A_i)) / m   for m != 0
	//   x = r*h                                  for m ~ 0 (stable, recovers linear).
	// This yields the exact inverse of the piecewise-linear node density, so the
	// sampled density reproduces the declared pdf (sigma*sin(theta)) node-for-node
	// instead of a piecewise-constant approximation (prior linear-in-theta defect).
	G4double h  = cdfTheta[i] - cdfTheta[i-1];
	if(!(h > 0.0)) return cdfTheta[i-1];
	G4double g0 = pdfNode[i-1];
	G4double g1 = pdfNode[i];
	G4double Ai = cdfIntervalMass[i];
	if(!(Ai > 0.0)) return cdfTheta[i-1];
	G4double r = (u - cdfVal[i-1]) / (cdfVal[i] - cdfVal[i-1]);
	G4double m = (g1 - g0) / h;
	G4double x;
	if(std::fabs(m) < 1e-12){
		x = r * h; // degenerate flat interval: linear recovery
	}else{
		G4double disc = g0*g0 + 2.0*m*r*Ai;
		if(disc < 0.0) disc = 0.0;
		x = (-g0 + std::sqrt(disc)) / m;
	}
	if(x < 0.0) x = 0.0;
	if(x > h)   x = h;
	return cdfTheta[i-1] + x;
}

G4double ScatteringGenerator::EvalELoss(G4double in)
{
	if(in<=0.){ return 0; }

	G4double dxin=0., dx=0., dy=0., de=0.;
	
	std::vector<G4double>::iterator lb = lower_bound(Ene.begin(), Ene.end(), in); 	
	G4int i = std::distance(Ene.begin(), lb);
	
	if(lb==Ene.begin()){
		de = dEdx[0]*in/Ene[0];
	}
	else if(lb==Ene.end()){
		dxin = in-Ene.back();
		dx = Ene.back()-Ene[Ene.size()-2];
		dy = dEdx.back()-dEdx[dEdx.size()-2];
		de = dEdx.back()+dy*dxin/dx;
	}
	else{
		dxin = in-Ene[i-1];
		dx = Ene[i]-Ene[i-1];
		dy = dEdx[i]-dEdx[i-1];
		de = dEdx[i-1]+dy*dxin/dx;
	}
	return de;
}

G4double ScatteringGenerator::EvalWeight(G4double angle)
{
	if(angle<=0.){ return 0; }

	G4double dxin=0., dx=0., dy=0., weight=0.;
	
	std::vector<G4double>::iterator lb = lower_bound(ang.begin(), ang.end(), angle); 	
	G4int i = std::distance(ang.begin(), lb);
	
	if(angle<ang[0]){
		dxin = angle-ang[0];
		dx = ang[0]-ang[1];
		dy = sigma[0]-sigma[1];
		weight = sigma[0]+dy*dxin/dx;
	}
	else if(angle>ang.back()){
		dxin = angle-ang.back();
		dx = ang.back()-ang[ang.size()-2];
		dy = sigma.back()-sigma[sigma.size()-2];
		weight = sigma.back()+dy*dxin/dx;
	}
	else{
		dxin = angle-ang[i-1];
		dx = ang[i]-ang[i-1];
		dy = sigma[i]-sigma[i-1];
		weight = sigma[i-1]+dy*dxin/dx;
	}
	return weight;
}

G4double ScatteringGenerator::BeamEnergy(G4double z)//initial energy and thickness are given as arguments 
{
	G4double dx =z/100.; //in mm
	G4double de = 0; //energy loss
	G4double e = fIncEnergy; //initial energy
	for (int i=0; i<100; i++){
	  	de = (dx * EvalELoss(e));//energy loss in dx
		if(de>e){
		   	e=0.;	
			break;
		}
		e-=de; // energy remaining after dx
	}
	return e;
}

void ScatteringGenerator::DefineCommands()
{
	// Define /B5/generator command directory using generic messenger class
	fMessenger = new G4GenericMessenger(this, "/ElGen/", "Elastic scattering particle generator");

	auto& energyCmd = fMessenger->DeclarePropertyWithUnit("E", "MeV", fIncEnergy);
	energyCmd.SetGuidance("Incoming energy in MeV.\n");
	energyCmd.SetParameterName("E", true);
	energyCmd.SetRange("E>=0.");
	energyCmd.SetDefaultValue("150.");

	auto& thicknessCmd = fMessenger->DeclarePropertyWithUnit("TargetThickness", "mm", fTgtThickness);
	thicknessCmd.SetGuidance("Target thickness in mm.\n");
	thicknessCmd.SetParameterName("TargetThickness", true);
	thicknessCmd.SetRange("TargetThickness>=0.");
	thicknessCmd.SetDefaultValue("2.3");

	auto& beamspotCmd = fMessenger->DeclarePropertyWithUnit("Beamspot", "mm", fBeamspot);
	beamspotCmd.SetGuidance("Beam spot radius in mm.\n");
	beamspotCmd.SetParameterName("Beamspot", true);
	beamspotCmd.SetRange("Beamspot>=0.");
	beamspotCmd.SetDefaultValue("10.");

	auto& dEdxFileCmd = fMessenger->DeclareProperty("dEdxFile", fDEdxFile);
	dEdxFileCmd.SetGuidance("File containing energy loss table for beam in target.\n");
	dEdxFileCmd.SetParameterName("dEdxFile", true);
	dEdxFileCmd.SetDefaultValue("dedx_p_in_CD2.txt");

	auto& CSFileCmd = fMessenger->DeclareProperty("CSFile", fCSFile);
	CSFileCmd.SetGuidance("File containing differential cross sections..\n");
	CSFileCmd.SetParameterName("CSFile", true);
	CSFileCmd.SetDefaultValue("null");
}
//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......
