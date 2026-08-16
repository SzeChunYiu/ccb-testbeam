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
// * technical work of the GEANT4 collaboration.                      *
// * By using,  copying,  modifying or  distributing the software (or *
// * any work based  on the software)  you  agree to acknowledge its *
// * use  in  resulting  scientific  publications,  and indicate your *
// * acceptance of all terms of the Geant4 Software license.          *
// ********************************************************************
//
/// \file ScatteringGenerator.hh
/// \brief Definition of the ScatteringGenerator class
//
// 
//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......
//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

#ifndef ScatteringGenerator_h
#define ScatteringGenerator_h 1

#include "G4VPrimaryGenerator.hh"
#include "G4ParticleDefinition.hh"
#include "G4PrimaryParticle.hh"

#include <vector>

class G4Event;
class G4GenericMessenger;

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

class ScatteringGenerator : public G4VPrimaryGenerator
{
  public:
    ScatteringGenerator();    
   ~ScatteringGenerator();

  public:
    void GeneratePrimaryVertex(G4Event*);
	G4ThreeVector GetParticlePosition(){return position;}
	G4ParticleDefinition* GetParticleDefinition1(){return partdef1;}
	G4ParticleDefinition* GetParticleDefinition2(){return partdef2;}
	G4ThreeVector GetParticleMomentumDirection1(){return particle1->GetMomentumDirection();}
	G4ThreeVector GetParticleMomentumDirection2(){return particle2->GetMomentumDirection();}
	G4double GetParticleEnergy1(){return particle1->GetKineticEnergy();}
	G4double GetParticleEnergy2(){return particle2->GetKineticEnergy();}
	G4String GetSourceReadinessMode() const;
  private:
	enum class SourceState {
		UNINITIALIZED,
		UNCONFIGURED_UNIFORM,
		CONFIGURED_READY,
		FATAL
	};
	void DefineCommands();
	void EnsureSourceReady();
	void FatalSourceError(const G4String&, const G4String&);
	void LoadFiles();
	void LoadELossTable();
	void LoadCrossSection();
	G4double EvalELoss(G4double);
	G4double EvalWeight(G4double);
	G4double SampleThetaCM();
	void BuildSigmaCDF();
	G4double BeamEnergy(G4double);
    G4GenericMessenger* fMessenger;
	G4ThreeVector position; 
	G4ParticleDefinition *partdef1, *partdef2;
	G4PrimaryParticle *particle1, *particle2;
	G4double fIncEnergy;
	G4double fTgtThickness;
	G4double fBeamspot;
	G4String fDEdxFile, fCSFile;
	G4String fLoadedDEdxFile, fLoadedCSFile;
	G4bool haveWeights;
	SourceState fSourceState;
	std::vector<G4double> Ene, dEdx;
	std::vector<G4double> ang, sigma;
	std::vector<G4double> cdfTheta, cdfVal, cdfPdf; // exact inverse-CDF node state
};

//....oooOO0OOooo........oooOO0OOooo........oooOO0OOooo........oooOO0OOooo......

#endif
