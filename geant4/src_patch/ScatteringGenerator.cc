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
// * any work based  on the software)  you  agree to acknowledge its *
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
#include "G4Exception.hh"
#include "G4GenericMessenger.hh"
#include "G4ParticleTable.hh"
#include "G4PrimaryVertex.hh"
#include "G4PhysicalConstants.hh"
#include "G4SystemOfUnits.hh"
#include "Randomize.hh"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>


ScatteringGenerator::ScatteringGenerator():
	fIncEnergy(150.*MeV),
	fTgtThickness(2.3*mm),
	fBeamspot(10*mm),
	fDEdxFile("dedx_p_in_CD2.txt"),
	fCSFile("null"),
	fLoadedDEdxFile(""),
	fLoadedCSFile(""),
	haveWeights(false),
	fSourceState(SourceState::UNINITIALIZED)
{
	DefineCommands();
}

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

ScatteringGenerator::~ScatteringGenerator()
{ 
	delete fMessenger;
}


//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

G4String ScatteringGenerator::GetSourceReadinessMode() const
{
	switch(fSourceState){
		case SourceState::UNINITIALIZED: return "UNINITIALIZED";
		case SourceState::UNCONFIGURED_UNIFORM: return "UNCONFIGURED_UNIFORM";
		case SourceState::CONFIGURED_READY: return "CONFIGURED_READY";
		case SourceState::FATAL: return "FATAL";
	}
	return "FATAL";
}

void ScatteringGenerator::FatalSourceError(const G4String& code, const G4String& message)
{
	fSourceState = SourceState::FATAL;
	G4Exception("ScatteringGenerator", code.c_str(), FatalException, message.c_str());
	// FatalException is expected not to return. Keep a process-level non-success
	// fallback so a custom exception handler cannot accidentally authorise a run.
	std::abort();
}

void ScatteringGenerator::EnsureSourceReady()
{
	if(fSourceState == SourceState::FATAL){
		FatalSourceError("CCB_SOURCE_ALREADY_FATAL", "Source readiness was previously marked FATAL.");
	}

	if(fSourceState != SourceState::UNINITIALIZED){
		if(fDEdxFile != fLoadedDEdxFile || fCSFile != fLoadedCSFile){
			FatalSourceError(
				"CCB_SOURCE_RECONFIGURED",
				"dEdxFile/CSFile changed after source readiness was established; create a new generator instance before generating more events."
			);
		}
		return;
	}

	LoadFiles();
	if(fSourceState != SourceState::UNCONFIGURED_UNIFORM &&
	   fSourceState != SourceState::CONFIGURED_READY){
		FatalSourceError("CCB_SOURCE_NOT_READY", "Source loading returned without a valid terminal readiness state.");
	}
}

void ScatteringGenerator::GeneratePrimaryVertex(G4Event* event)
{
	// Readiness is per generator instance and independent of global event ID.
	// It is checked before consuming event RNG or computing any event observable.
	EnsureSourceReady();

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

	// CM ejectile angle sampled from the declared source model when configured.
	// Uniform sampling is permitted only in explicit CSFile=null readiness state.
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

	// Randomly generate phi across the full physical azimuthal range.
	//   source_phi_measure = uniform_full_2pi_v1
	// The azimuthal measure is uniform over [0,2*pi) with no detector-surrogate
	// pre-acceptance: phi3, and hence the coplanar recoil phi4, cover the whole
	// 2*pi physical range. The 50/50 flip selects which of the two coplanar
	// particles carries the +pi branch; both remain on the full circle.
	G4double phi3 = 2*pi*G4UniformRand();
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
	if(fSourceState != SourceState::UNINITIALIZED){
		return;
	}

	G4cout << "Reading energy loss values from " << fDEdxFile << G4endl;
	LoadELossTable();
	haveWeights=false;

	if(fCSFile=="null"){
		ang.clear();
		sigma.clear();
		cdfTheta.clear();
		cdfVal.clear();
		cdfPdf.clear();
		fLoadedDEdxFile = fDEdxFile;
		fLoadedCSFile = fCSFile;
		fSourceState = SourceState::UNCONFIGURED_UNIFORM;
		G4cout << "ScatteringGenerator: source readiness=UNCONFIGURED_UNIFORM (CSFile=null)." << G4endl;
		return;
	}
	
	G4cout << "Reading differential cross sections from " << fCSFile << G4endl;
	LoadCrossSection();
	BuildSigmaCDF();
	fLoadedDEdxFile = fDEdxFile;
	fLoadedCSFile = fCSFile;
	fSourceState = SourceState::CONFIGURED_READY;
	G4cout << "ScatteringGenerator: source readiness=CONFIGURED_READY." << G4endl;
}

void ScatteringGenerator::LoadELossTable()
{
	std::ifstream infile(fDEdxFile.c_str());
	if(!infile.is_open()){
		FatalSourceError("CCB_DEDX_OPEN", "Cannot open required stopping-power table: " + fDEdxFile);
	}

	std::vector<G4double> nextEne;
	std::vector<G4double> nextDEdx;
	std::string line;
	size_t lineNo = 0;
	while(std::getline(infile, line)){
		lineNo++;
		size_t comment = line.find('#');
		if(comment != std::string::npos) line.erase(comment);
		if(line.find_first_not_of(" \t\r\n") == std::string::npos) continue;

		std::istringstream row(line);
		G4double tmpE = 0.0, tmpDEdx = 0.0;
		if(!(row >> tmpE >> tmpDEdx)){
			std::ostringstream msg;
			msg << "Malformed stopping-table row " << lineNo << " in " << fDEdxFile;
			FatalSourceError("CCB_DEDX_PARSE", msg.str().c_str());
		}
		if(!std::isfinite(tmpE) || !std::isfinite(tmpDEdx) || !(tmpE > 0.0) || tmpDEdx < 0.0){
			std::ostringstream msg;
			msg << "Invalid stopping-table values at row " << lineNo << " in " << fDEdxFile;
			FatalSourceError("CCB_DEDX_DOMAIN", msg.str().c_str());
		}

		G4double convertedE = tmpE*938.28/931.5; // MeV/u to MeV
		G4double convertedDEdx = tmpDEdx*1000.; // um to mm
		if(!nextEne.empty() && !(convertedE > nextEne.back())){
			std::ostringstream msg;
			msg << "Stopping-table energies must be strictly increasing; row " << lineNo;
			FatalSourceError("CCB_DEDX_ORDER", msg.str().c_str());
		}
		nextEne.push_back(convertedE);
		nextDEdx.push_back(convertedDEdx);
	}
	if(nextEne.size() < 2 || nextDEdx.size() != nextEne.size()){
		FatalSourceError("CCB_DEDX_CARDINALITY", "Stopping-power table requires at least two valid rows.");
	}

	Ene.swap(nextEne);
	dEdx.swap(nextDEdx);
}

void ScatteringGenerator::LoadCrossSection()
{
	std::ifstream infile(fCSFile.c_str());
	if(!infile.is_open()){
		FatalSourceError("CCB_CS_OPEN", "Cannot open configured cross-section table: " + fCSFile);
	}

	std::vector<G4double> nextAng;
	std::vector<G4double> nextSigma;
	std::string line;
	size_t lineNo = 0;
	while(std::getline(infile, line)){
		lineNo++;
		size_t comment = line.find('#');
		if(comment != std::string::npos) line.erase(comment);
		if(line.find_first_not_of(" \t\r\n") == std::string::npos) continue;

		std::istringstream row(line);
		G4double tmpA = 0.0, tmpCS = 0.0;
		if(!(row >> tmpA >> tmpCS)){
			std::ostringstream msg;
			msg << "Malformed cross-section row " << lineNo << " in " << fCSFile;
			FatalSourceError("CCB_CS_PARSE", msg.str().c_str());
		}
		if(!std::isfinite(tmpA) || !std::isfinite(tmpCS) || !(tmpA > 0.0) || !(tmpA < 180.0) || tmpCS < 0.0){
			std::ostringstream msg;
			msg << "Invalid cross-section values at row " << lineNo << " in " << fCSFile;
			FatalSourceError("CCB_CS_DOMAIN", msg.str().c_str());
		}

		G4double convertedA = tmpA*pi/180.; // deg to rad
		if(!nextAng.empty() && !(convertedA > nextAng.back())){
			std::ostringstream msg;
			msg << "Cross-section angles must be strictly increasing; row " << lineNo;
			FatalSourceError("CCB_CS_ORDER", msg.str().c_str());
		}
		nextAng.push_back(convertedA);
		nextSigma.push_back(tmpCS);
	}
	if(nextAng.size() < 2 || nextSigma.size() != nextAng.size()){
		FatalSourceError("CCB_CS_CARDINALITY", "Configured cross-section table requires at least two valid rows.");
	}

	ang.swap(nextAng);
	sigma.swap(nextSigma);
}

void ScatteringGenerator::BuildSigmaCDF()
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
	if(ang.size() < 2 || sigma.size() != ang.size()){
		FatalSourceError("CCB_CS_CDF_INPUT", "Configured cross-section arrays are not valid for CDF construction.");
	}

	// Positive common density scaling cannot change a normalized source law. Scale
	// cross sections before multiplying/integrating so alternate units cannot cause
	// overflow/underflow in the CDF state.
	G4double densityScale = 0.0;
	for(size_t k = 0; k < ang.size(); k++){
		if(!std::isfinite(ang[k]) || !std::isfinite(sigma[k]) || sigma[k] < 0.0){
			FatalSourceError("CCB_CS_CDF_NODE", "Configured source contains a non-finite or negative CDF node.");
		}
		if(k > 0 && !(ang[k] > ang[k-1])){
			FatalSourceError("CCB_CS_CDF_ORDER", "Configured source angles are not strictly increasing.");
		}
		if(sigma[k] > densityScale) densityScale = sigma[k];
	}
	if(!(densityScale > 0.0)){
		FatalSourceError("CCB_CS_ZERO_DENSITY", "Configured source has zero total density.");
	}

	std::vector<G4double> nextTheta = ang;
	std::vector<G4double> nextPdf;
	nextPdf.reserve(ang.size());
	for(size_t k = 0; k < ang.size(); k++){
		G4double p = (sigma[k] / densityScale) * std::sin(ang[k]);
		if(!std::isfinite(p) || p < 0.0){
			FatalSourceError("CCB_CS_NODE_PDF", "Configured source produced an invalid node PDF.");
		}
		nextPdf.push_back(p);
	}

	std::vector<G4double> nextVal(nextTheta.size(), 0.0);
	for(size_t i = 1; i < nextTheta.size(); i++){
		G4double dx  = nextTheta[i] - nextTheta[i-1];
		G4double avg = 0.5 * (nextPdf[i] + nextPdf[i-1]);
		nextVal[i] = nextVal[i-1] + avg * dx;
	}
	G4double norm = nextVal.back();
	if(!std::isfinite(norm) || !(norm > 0.0)){
		FatalSourceError("CCB_CS_CDF_NORM", "Configured source produced an invalid CDF normalization.");
	}
	for(size_t i = 0; i < nextVal.size(); i++) nextVal[i] /= norm;

	cdfTheta.swap(nextTheta);
	cdfPdf.swap(nextPdf);
	cdfVal.swap(nextVal);
	G4cout << "ScatteringGenerator: inverse-CDF ready over measured support ["
	       << (ang.front()/pi)*180. << "," << (ang.back()/pi)*180. << "] deg from "
	       << ang.size() << " CS pts; interpolation=linear_node_pdf_exact_inverse_v1; "
	       << "support=measured_table_support_truncate_v1." << G4endl;
	G4cout << "ScatteringGenerator: uncertainty_contract=not_propagated_issue_1179; "
	       << "propagation_note=Cross-section statistical and systematic uncertainty propagation is "
	       << "not yet implemented. The nominal reference uses sigma (column 2) only. "
	       << "Tracked as issue #1179 in the campaign ledger."
	       << G4endl;
}

G4double ScatteringGenerator::SampleThetaCM()
{
	if(fSourceState == SourceState::UNCONFIGURED_UNIFORM){
		return pi * G4UniformRand();
	}
	if(fSourceState != SourceState::CONFIGURED_READY){
		FatalSourceError("CCB_CS_SAMPLE_NOT_READY", "SampleThetaCM called without CONFIGURED_READY or explicit uniform state.");
	}
	if(cdfTheta.empty() || cdfVal.empty() || cdfPdf.empty() ||
	   cdfTheta.size() != cdfVal.size() || cdfTheta.size() != cdfPdf.size()){
		FatalSourceError("CCB_CS_CDF_STATE", "Configured source CDF state is empty or inconsistent.");
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
	if(!(intervalMass > 0.0)) return left;
	G4double targetMass = frac * intervalMass;
	G4double slope = (b - a) / width;
	G4double discriminant = a*a + 2.0*slope*targetMass;
	if(discriminant < 0.0 && discriminant > -1e-14) discriminant = 0.0;
	if(discriminant < 0.0){
		FatalSourceError("CCB_CS_INVERSE_DISCRIMINANT", "Configured source inverse-CDF discriminant is negative.");
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
		FatalSourceError("CCB_DEDX_STATE", "EvalELoss called without a validated stopping-power table.");
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
	CSFileCmd.SetGuidance("File containing differential cross sections..\n");
	CSFileCmd.SetParameterName("CSFile", true);
	CSFileCmd.SetDefaultValue("null");
}
//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......
