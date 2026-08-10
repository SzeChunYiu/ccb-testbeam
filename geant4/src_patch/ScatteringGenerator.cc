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

#include "G4String.hh"


#include "G4Event.hh"
#include "G4GenericMessenger.hh"
#include "G4ParticleTable.hh"
#include "G4PrimaryVertex.hh"
#include "G4PhysicalConstants.hh"
#include "G4SystemOfUnits.hh"
#include <algorithm>
#include <cmath>
#include <fstream>
#include <sstream>
#include <vector>

#include "Randomize.hh"
#include <cmath>


ScatteringGenerator::ScatteringGenerator():
	fIncEnergy(150.*MeV),
	fTgtThickness(2.3*mm),
	fBeamspot(10*mm),
	fDEdxFile("dedx_p_in_CD2.txt"),
	fCSFile("null"),
	fSourceState(SourceState::UNINITIALIZED)
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
	EnsureSourceReady();
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
	// MV3 scattering-model residual (CL-021). Configured sources are validated
	// per-instance; explicit uniform mode is the fCSFile=="null" state.
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

void ScatteringGenerator::EnsureFilesLoaded()
{
	// Idempotent: only the first call performs the transactional load; later calls
	// (e.g. from per-event EnsureSourceReady) observe the already-published state.
	if(fSourceState != SourceState::UNINITIALIZED){ return; }

	// Configuration identity guard: if the requested source paths changed since
	// this instance last validated, fail closed rather than silently mixing tables.
	if((fDEdxFile != fLoadedDEdxFile) || (fCSFile != fLoadedCSFile)){
		fSourceState = SourceState::FATAL;
		FatalSourceError("CCB_SOURCE_RECONFIGURED",
		                  "Scattering source configuration changed after load; refusing to re-read.",
		                  "ScatteringGenerator::EnsureFilesLoaded");
	}

	std::vector<G4double> nextEne, nextDEdx, nextAng, nextSigma;
	std::vector<G4double> nextTheta, nextVal, nextPdf;

	bool dEdxOK = LoadELossTable(nextEne, nextDEdx);
	bool csOK = true;
	if(fCSFile != "null"){
		csOK = LoadCrossSection(nextAng, nextSigma);
	} 

	if(dEdxOK && csOK && fCSFile != "null"){
		csOK = BuildSigmaCDF(nextAng, nextSigma, nextTheta, nextVal, nextPdf);
	}

	if(fCSFile == "null"){
		// Explicit uniform mode: no cross-section source is configured.
		if(dEdxOK){
			Ene.swap(nextEne); dEdx.swap(nextDEdx);
			fLoadedDEdxFile = fDEdxFile;
			fLoadedCSFile = "null";
			fSourceState = SourceState::UNCONFIGURED_UNIFORM;
		} else {
			fSourceState = SourceState::FATAL;
		}
		return;
	}

	// Configured source: every element must validate, else fail closed.
	if(dEdxOK && csOK){
		Ene.swap(nextEne); dEdx.swap(nextDEdx);
		ang.swap(nextAng); sigma.swap(nextSigma);
		cdfTheta.swap(nextTheta); cdfVal.swap(nextVal); cdfPdf.swap(nextPdf);
		fLoadedDEdxFile = fDEdxFile;
		fLoadedCSFile = fCSFile;
		fSourceState = SourceState::CONFIGURED_READY;
	} else {
		fSourceState = SourceState::FATAL;
	}
}

void ScatteringGenerator::EnsureSourceReady()
{
	// Idempotent entry point into the readiness state machine.
	if(fSourceState == SourceState::UNINITIALIZED){ EnsureFilesLoaded(); }
	if(fSourceState == SourceState::FATAL){
		FatalSourceError("CCB_CS_SAMPLE_NOT_READY",
		                  "Configured scattering source failed validation; event generation is disabled.",
		                  "ScatteringGenerator::EnsureSourceReady");
	}
}

void ScatteringGenerator::FatalSourceError(const G4String& code,
                                           const G4String& message,
                                           const char* origin)
{
	G4Exception(origin, code, FatalException, message);
	std::abort();
}

bool ScatteringGenerator::LoadELossTable(
	std::vector<G4double>& outEne,
	std::vector<G4double>& outDEdx)
{
	std::ifstream infile(fDEdxFile);
	if(!infile.is_open()){
		FatalSourceError("CCB_DEDX_OPEN_FAILED",
		                  "Cannot open energy-loss table.",
		                  "ScatteringGenerator::LoadELossTable");
	}

	std::vector<G4double> nextEne, nextDEdx;
	std::string line;
	while(std::getline(infile, line)){
		if(line.empty() || line[0] == '#'){ continue; }
		G4double tmpE, tmpDEdx;
		std::istringstream row(line);
		if(!(row >> tmpE >> tmpDEdx)){
			FatalSourceError("CCB_DEDX_PARSE",
			                  "Energy-loss table parse failure.",
			                  "ScatteringGenerator::LoadELossTable");
		}
		if(!std::isfinite(tmpE) || !std::isfinite(tmpDEdx) || tmpE < 0.0 || tmpDEdx < 0.0){
			FatalSourceError("CCB_DEDX_NONFINITE",
			                  "Energy-loss table non-finite/negative node.",
			                  "ScatteringGenerator::LoadELossTable");
		}
		// Convert: MeV/u to MeV, um to mm
		tmpE *= 938.28 / 931.5;
		tmpDEdx *= 1000.0;
		if(!nextEne.empty() && !(tmpE > nextEne.back())){
			FatalSourceError("CCB_DEDX_MONOTONIC",
			                  "Energy-loss table energies not strictly increasing.",
			                  "ScatteringGenerator::LoadELossTable");
		}
		nextEne.push_back(tmpE);
		nextDEdx.push_back(tmpDEdx);
	}
	if(nextEne.empty()){
		FatalSourceError("CCB_DEDX_EMPTY",
		                  "Energy-loss table is empty.",
		                  "ScatteringGenerator::LoadELossTable");
	}
	// Publish to output only after full validation.
	outEne.swap(nextEne);
	outDEdx.swap(nextDEdx);
	return true;
}

bool ScatteringGenerator::LoadCrossSection(
	std::vector<G4double>& outAng,
	std::vector<G4double>& outSigma)
{
	std::ifstream infile(fCSFile);
	if(!infile.is_open()){
		FatalSourceError("CCB_CS_OPEN_FAILED",
		                  "Cannot open cross-section table.",
		                  "ScatteringGenerator::LoadCrossSection");
	}

	std::vector<G4double> nextAng, nextSigma;
	std::string line;
	while(std::getline(infile, line)){
		if(line.empty() || line[0] == '#'){ continue; }
		G4double tmpA, tmpCS, tmpUnc;
		std::istringstream row(line);
		if(!(row >> tmpA >> tmpCS)){
			FatalSourceError("CCB_CS_PARSE",
			                  "Cross-section table parse failure.",
			                  "ScatteringGenerator::LoadCrossSection");
		}
		if(!std::isfinite(tmpA) || !std::isfinite(tmpCS) || tmpA < 0.0 || tmpCS < 0.0){
			FatalSourceError("CCB_CS_NONFINITE",
			                  "Cross-section table non-finite/negative node.",
			                  "ScatteringGenerator::LoadCrossSection");
		}
		tmpA *= pi / 180.; // deg to rad
		if(!nextAng.empty() && !(tmpA > nextAng.back())){
			FatalSourceError("CCB_CS_MONOTONIC",
			                  "Cross-section table angles not strictly increasing.",
			                  "ScatteringGenerator::LoadCrossSection");
		}
		nextAng.push_back(tmpA);
		nextSigma.push_back(tmpCS);
	}
	if(nextAng.size() < 2){
		FatalSourceError("CCB_CS_TOOFEW",
		                  "Cross-section table needs at least two rows.",
		                  "ScatteringGenerator::LoadCrossSection");
	}
	// Publish to output only after full validation.
	outAng.swap(nextAng);
	outSigma.swap(nextSigma);
	return true;
}

bool ScatteringGenerator::BuildSigmaCDF(
	const std::vector<G4double>& inAng,
	const std::vector<G4double>& inSigma,
	std::vector<G4double>& outTheta,
	std::vector<G4double>& outCdf,
	std::vector<G4double>& outPdf)
{
	// Source-model IDs are intentionally literal so generator provenance can bind
	// the numerical law rather than the generic phrase "inverse CDF".
	//   cross_section_interpolation_mode = linear_node_pdf_exact_inverse_v1
	//   cross_section_support_mode = measured_table_support_truncate_v1
	//
	// The Table-VI nodes define p(theta)=sigma(theta)*sin(theta). Between measured
	// angles p(theta) is linearly interpolated; outside measured support the nominal
	// reference distribution has zero probability. This truncation is an explicit
	// source-model choice, not evidence that the physical cross section vanishes.
	std::vector<G4double> nextTheta, nextCdf, nextPdf;
	if(inAng.size() < 2 || inSigma.size() != inAng.size()){ return false; }

	// Positive common density scaling cannot change a normalized source law. Scale
	// cross sections before multiplying/integrating so alternate units cannot cause
	// overflow/underflow in the CDF state.
	G4double densityScale = 0.0;
	for(size_t k = 0; k < inAng.size(); k++){
		if(!std::isfinite(inAng[k]) || !std::isfinite(inSigma[k]) || inSigma[k] < 0.0){
			return false;
		}
		if(k > 0 && !(inAng[k] > inAng[k-1])){
			return false;
		}
		if(inSigma[k] > densityScale) densityScale = inSigma[k];
	}
	if(!(densityScale > 0.0)){
		return false;
	}

	nextTheta = inAng;
	nextPdf.reserve(inAng.size());
	for(size_t k = 0; k < inAng.size(); k++){
		G4double p = (inSigma[k] / densityScale) * std::sin(inAng[k]);
		if(!std::isfinite(p) || p < 0.0){
			return false;
		}
		nextPdf.push_back(p);
	}

	nextCdf.assign(nextTheta.size(), 0.0);
	for(size_t i = 1; i < nextTheta.size(); i++){
		G4double dx  = nextTheta[i] - nextTheta[i-1];
		G4double avg = 0.5 * (nextPdf[i] + nextPdf[i-1]);
		nextCdf[i] = nextCdf[i-1] + avg * dx;
	}
	G4double norm = nextCdf.back();
	if(!std::isfinite(norm) || !(norm > 0.0)){
		return false;
	}
	for(size_t i = 0; i < nextCdf.size(); i++) nextCdf[i] /= norm;
	// Publish to outputs only after full validation.
	outTheta.swap(nextTheta);
	outCdf.swap(nextCdf);
	outPdf.swap(nextPdf);
	G4cout << "ScatteringGenerator: inverse-CDF ready over measured support ["
	       << (inAng.front()/pi)*180. << "," << (inAng.back()/pi)*180. << "] deg from "
	       << inAng.size() << " CS pts; interpolation=linear_node_pdf_exact_inverse_v1; "
	       << "support=measured_table_support_truncate_v1." << G4endl;
	return true;
}
G4double ScatteringGenerator::SampleThetaCM()
{
	EnsureSourceReady();
	if(fSourceState == SourceState::FATAL){
		FatalSourceError("CCB_CS_SAMPLE_NOT_READY",
		                  "Scattering source is in FATAL state; cannot sample theta_cm.",
		                  "ScatteringGenerator::SampleThetaCM");
	}
	if(fSourceState == SourceState::UNCONFIGURED_UNIFORM){ return pi * G4UniformRand(); }

	// Draw theta_cm from the linearly interpolated p(theta)=sigma(theta)*sin(theta)
	// on measured support. BuildSigmaCDF stores exact trapezoid interval masses;
	// this function uses the analytic quadratic interval-mass inverse, rather than
	// interpolating theta linearly in cumulative probability.
	if(cdfTheta.empty() || cdfVal.empty() || cdfPdf.empty()){
		FatalSourceError("CCB_CS_CDF_STATE",
		                  "CDF state is empty; configured source is in FATAL state.",
		                  "ScatteringGenerator::SampleThetaCM");
	}
	if(cdfTheta.size() != cdfVal.size() || cdfTheta.size() != cdfPdf.size()){
		FatalSourceError("CCB_CS_CDF_STATE",
		                  "CDF state inconsistent; configured source is in FATAL state.",
		                  "ScatteringGenerator::SampleThetaCM");
	}

	G4double u = G4UniformRand();
	std::vector<G4double>::iterator it = std::lower_bound(cdfVal.begin(), cdfVal.end(), u);
	size_t i = (size_t)std::distance(cdfVal.begin(), it);
	if(i == 0)               return cdfTheta.front();
	if(i >= cdfTheta.size()) return cdfTheta.back();

	G4double c0 = cdfVal[i-1], c1 = cdfVal[i];
	if(!(c1 > c0)) return cdfTheta[i-1];
	G4double frac = (u - c0) / (c1 - c0);
	if(frac <= 0.0) return cdfTheta[i-1];
	if(frac >= 1.0) return cdfTheta[i];

	G4double left = cdfTheta[i-1];
	G4double right = cdfTheta[i];
	G4double width = right - left;
	G4double a = cdfPdf[i-1];
	G4double b = cdfPdf[i];
	G4double intervalMass = 0.5 * (a + b) * width;
	G4double targetMass = frac * intervalMass;
	G4double slope = (b - a) / width;
	G4double discriminant = a*a + 2.0*slope*targetMass;
	if(discriminant < 0.0 && discriminant > -1e-14) discriminant = 0.0;
	if(discriminant < 0.0){
		G4cerr << "ScatteringGenerator::SampleThetaCM: negative inverse-CDF discriminant; using interval midpoint." << G4endl;
		return 0.5 * (left + right);
	}
	G4double root = std::sqrt(discriminant);
	G4double denominator = a + root;
	G4double x = 0.0;
	if(denominator > 0.0){
		// Stable conjugate form of the quadratic solution:
		// x = 2*y / (a + sqrt(a^2 + 2*k*y)).
		x = 2.0 * targetMass / denominator;
	}
	else if(b > 0.0){
		x = width * std::sqrt(frac);
	}
	if(x < 0.0) x = 0.0;
	if(x > width) x = width;
	return left + x;
}

G4double ScatteringGenerator::EvalELoss(G4double in)
{
	if(in<=0.){ return 0; }
	if(Ene.size() < 2 || dEdx.size() != Ene.size()){
		FatalSourceError("CCB_DEDX_STATE",
		                  "Energy-loss table missing or inconsistent; cannot compute stopping.",
		                  "ScatteringGenerator::EvalELoss");
	}

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
	CSFileCmd.SetGuidance("File containing differential cross sections.\n");
	CSFileCmd.SetParameterName("CSFile", true);
	CSFileCmd.SetDefaultValue("null");
}
//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......
