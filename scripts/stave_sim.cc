// Single-stave GEANT4 simulation for CCB test-beam
// Issue #796: 50cm x 5.18cm x 2.0cm polystyrene scintillator
// Two Y-11 WLS fibres (1.8mm diam, 2cm apart), TiO2 coating
// One-end readout. Proton/deuteron beam at multiple energies.

#include "G4RunManager.hh"
#include "G4NistManager.hh"
#include "G4Box.hh"
#include "G4Tubs.hh"
#include "G4LogicalVolume.hh"
#include "G4PVPlacement.hh"
#include "G4SystemOfUnits.hh"
#include "G4ParticleGun.hh"
#include "G4ParticleTable.hh"
#include "G4Proton.hh"
#include "G4Deuteron.hh"
#include "G4VModularPhysicsList.hh"
#include "G4EmStandardPhysics.hh"
#include "G4OpticalPhysics.hh"
#include "G4Step.hh"
#include "G4Track.hh"
#include "G4Event.hh"
#include "G4Run.hh"
#include "G4SDManager.hh"
#include "G4VSensitiveDetector.hh"
#include "G4UserRunAction.hh"
#include "G4UserEventAction.hh"
#include "G4VUserDetectorConstruction.hh"
#include "G4VUserActionInitialization.hh"

#include <fstream>
#include <vector>
#include <cmath>

// ── Output record ──
struct EventRecord {
    int event;
    std::string particle;
    double ke_MeV;
    double edep_scint_MeV;
    double edep_wls1_MeV;
    double edep_wls2_MeV;
    int photons_wls1;
    int photons_wls2;
    double track_len_cm;
    double entry_x, entry_y, entry_z;
    double exit_x, exit_y, exit_z;
};
static std::vector<EventRecord> g_records;

// ── Sensitive Detector ──
class ScintSD : public G4VSensitiveDetector {
public:
    ScintSD(const G4String& name) : G4VSensitiveDetector(name) {}
    void Initialize(G4HCofThisEvent*) override {
        edep_scint = edep_wls1 = edep_wls2 = 0;
        photons_wls1 = photons_wls2 = 0;
        track_len = 0; has_entry = false;
    }
    G4bool ProcessHits(G4Step* step, G4TouchableHistory*) override {
        G4double edep = step->GetTotalEnergyDeposit();
        if (edep <= 0) return true;
        G4String vol = step->GetPreStepPoint()->GetPhysicalVolume()->GetName();
        G4int pdg = step->GetTrack()->GetParticleDefinition()->GetPDGEncoding();
        track_len += step->GetStepLength();
        if (!has_entry) { entry = step->GetPreStepPoint()->GetPosition(); has_entry = true; }
        exit = step->GetPostStepPoint()->GetPosition();
        if (vol == "Scintillator") edep_scint += edep;
        else if (vol == "WLS1_Core") { edep_wls1 += edep; if (pdg==0) photons_wls1++; }
        else if (vol == "WLS2_Core") { edep_wls2 += edep; if (pdg==0) photons_wls2++; }
        return true;
    }
    void EndOfEvent(G4HCofThisEvent*) override {}
    G4double edep_scint=0, edep_wls1=0, edep_wls2=0;
    int photons_wls1=0, photons_wls2=0;
    G4double track_len=0;
    G4ThreeVector entry, exit;
    bool has_entry=false;
};

// ── Detector Construction ──
class StaveDetCon : public G4VUserDetectorConstruction {
public:
    ScintSD* sd = nullptr;
    G4VPhysicalVolume* Construct() override {
        G4NistManager* nist = G4NistManager::Instance();
        G4Material* air = nist->FindOrBuildMaterial("G4_AIR");

        // Polystyrene
        auto* ps = new G4Material("Polystyrene", 1.032*g/cm3, 2);
        ps->AddElement(nist->FindOrBuildElement("C"), 8);
        ps->AddElement(nist->FindOrBuildElement("H"), 8);
        auto* ps_mpt = new G4MaterialPropertiesTable();
        G4double e[2] = {2.*eV, 4.*eV};
        G4double sc[2] = {0.8, 0.8}, scl[2] = {0.2, 0.2};
        ps_mpt->AddProperty("SCINTILLATIONCOMPONENT1", e, sc, 2);
        ps_mpt->AddProperty("SCINTILLATIONCOMPONENT2", e, scl, 2);
        ps_mpt->AddConstProperty("SCINTILLATIONYIELD", 10000./MeV);
        ps_mpt->AddConstProperty("SCINTILLATIONTIMECONSTANT1", 2.1*ns);
        ps_mpt->AddConstProperty("SCINTILLATIONTIMECONSTANT2", 14.*ns);
        ps_mpt->AddConstProperty("SCINTILLATIONYIELD1", 0.8);
        ps_mpt->AddConstProperty("SCINTILLATIONYIELD2", 0.2);
        G4double ri[2] = {1.58, 1.58};
        ps_mpt->AddProperty("RINDEX", e, ri, 2);
        G4double absl[2] = {3.8*m, 3.8*m};
        ps_mpt->AddProperty("ABSLENGTH", e, absl, 2);
        ps->SetMaterialPropertiesTable(ps_mpt);

        // WLS core (Kuraray Y-11)
        auto* wls = new G4Material("WLS_Core", 1.19*g/cm3, 2);
        wls->AddElement(nist->FindOrBuildElement("C"), 9);
        wls->AddElement(nist->FindOrBuildElement("H"), 10);
        auto* wls_mpt = new G4MaterialPropertiesTable();
        G4double wls_abs[2] = {0.3*mm, 10.*m};
        wls_mpt->AddProperty("ABSLENGTH", e, wls_abs, 2);
        G4double wls_ri[2] = {1.59, 1.59};
        wls_mpt->AddProperty("RINDEX", e, wls_ri, 2);
        G4double wls_emit[2] = {0.95, 0.01};
        wls_mpt->AddProperty("WLSCOMPONENT", e, wls_emit, 2);
        wls_mpt->AddConstProperty("WLSTIMECONSTANT", 6.0*ns);
        wls->SetMaterialPropertiesTable(wls_mpt);

        // World
        auto* worldS = new G4Box("World", 30*cm, 5*cm, 5*cm);
        auto* worldLV = new G4LogicalVolume(worldS, air, "World");
        auto* worldPV = new G4PVPlacement(0, G4ThreeVector(), worldLV, "World", 0, false, 0);

        // Scintillator: 50cm x 5.18cm x 2.0cm
        auto* scintiS = new G4Box("Scintillator", 25*cm, 2.59*cm, 1.0*cm);
        auto* scintiLV = new G4LogicalVolume(scintiS, ps, "Scintillator");
        new G4PVPlacement(0, G4ThreeVector(0,0,0), scintiLV, "Scintillator", worldLV, false, 0);

        // WLS1 at y=-1cm (read out at x=+25cm end)
        auto* wls1S = new G4Tubs("WLS1_Core", 0, 0.9*mm, 25*cm, 0, 360*deg);
        auto* wls1LV = new G4LogicalVolume(wls1S, wls, "WLS1_Core");
        new G4PVPlacement(0, G4ThreeVector(0,-1.0*cm,0), wls1LV, "WLS1_Core", scintiLV, false, 1);

        // WLS2 at y=+1cm (not read out)
        auto* wls2S = new G4Tubs("WLS2_Core", 0, 0.9*mm, 25*cm, 0, 360*deg);
        auto* wls2LV = new G4LogicalVolume(wls2S, wls, "WLS2_Core");
        new G4PVPlacement(0, G4ThreeVector(0,+1.0*cm,0), wls2LV, "WLS2_Core", scintiLV, false, 2);

        // SD
        auto* sdman = G4SDManager::GetSDMpointer();
        sd = new ScintSD("ScintSD");
        sdman->AddNewDetector(sd);
        scintiLV->SetSensitiveDetector(sd);
        wls1LV->SetSensitiveDetector(sd);
        wls2LV->SetSensitiveDetector(sd);

        return worldPV;
    }
};

// ── Run Action ──
class StaveRunAction : public G4UserRunAction {
public:
    StaveRunAction(const std::string& f) : fn(f) {}
    void BeginOfRunAction(const G4Run*) override { g_records.clear(); }
    void EndOfRunAction(const G4Run*) override {
        std::ofstream out(fn);
        out << "# Single-stave GEANT4 simulation\n";
        out << "# 50cm x 5.18cm x 2.0cm polystyrene, 2x Y-11 WLS 1.8mm, 2cm apart\n";
        out << "# Only WLS1 read out at x=+25cm end\n";
        out << "event particle ke_MeV edep_scint_MeV edep_wls1_MeV edep_wls2_MeV photons_wls1 photons_wls2 track_len_cm entry_x entry_y entry_z exit_x exit_y exit_z\n";
        for (auto& r : g_records) {
            out << r.event << " " << r.particle << " " << r.ke_MeV << " "
                << r.edep_scint_MeV << " " << r.edep_wls1_MeV << " " << r.edep_wls2_MeV << " "
                << r.photons_wls1 << " " << r.photons_wls2 << " " << r.track_len_cm << " "
                << r.entry_x << " " << r.entry_y << " " << r.entry_z << " "
                << r.exit_x << " " << r.exit_y << " " << r.exit_z << "\n";
        }
        out.close();
        std::cout << "Wrote " << g_records.size() << " events to " << fn << std::endl;
    }
private:
    std::string fn;
};

// ── Event Action ──
class StaveEventAction : public G4UserEventAction {
public:
    StaveEventAction(StaveDetCon* d) : det(d) {}
    void BeginOfEventAction(const G4Event*) override {
        if (det->sd) det->sd->Initialize(nullptr);
    }
    void EndOfEventAction(const G4Event* evt) override {
        if (!det->sd) return;
        EventRecord r;
        r.event = evt->GetEventID();
        r.edep_scint_MeV = det->sd->edep_scint/MeV;
        r.edep_wls1_MeV = det->sd->edep_wls1/MeV;
        r.edep_wls2_MeV = det->sd->edep_wls2/MeV;
        r.photons_wls1 = det->sd->photons_wls1;
        r.photons_wls2 = det->sd->photons_wls2;
        r.track_len_cm = det->sd->track_len/cm;
        r.entry_x = det->sd->entry.x()/cm; r.entry_y = det->sd->entry.y()/cm; r.entry_z = det->sd->entry.z()/cm;
        r.exit_x = det->sd->exit.x()/cm; r.exit_y = det->sd->exit.y()/cm; r.exit_z = det->sd->exit.z()/cm;
        r.particle = fPartName; r.ke_MeV = fKE/MeV;
        g_records.push_back(r);
    }
    void SetBeam(const G4String& p, G4double ke) { fPartName = p; fKE = ke; }
private:
    StaveDetCon* det;
    G4String fPartName;
    G4double fKE;
};

// ── Action Initialization ──
class StaveActionInit : public G4VUserActionInitialization {
public:
    StaveActionInit(StaveDetCon* d, const std::string& f) : det(d), fn(f) {}
    void Build() const override {
        SetUserAction(new StaveRunAction(fn));
        SetUserAction(new StaveEventAction(det));
    }
    void BuildForMaster() const override {
        SetUserAction(new StaveRunAction(fn));
    }
private:
    StaveDetCon* det;
    std::string fn;
};

// ── Physics ──
class StavePhys : public G4VModularPhysicsList {
public:
    StavePhys() {
        RegisterPhysics(new G4EmStandardPhysics());
        auto* opt = new G4OpticalPhysics();
        opt->SetVerboseLevel(0);
        RegisterPhysics(opt);
    }
};

// ── Main ──
int main(int argc, char** argv) {
    G4String outFile = "stave_sim_output.dat";
    G4String particle = "proton";
    int nEvents = 10000;

    for (int i=1; i<argc; i++) {
        G4String a = argv[i];
        if (a=="-o" && i+1<argc) outFile = argv[++i];
        else if (a=="-p" && i+1<argc) particle = argv[++i];
        else if (a=="-n" && i+1<argc) nEvents = std::atoi(argv[++i]);
    }

    std::cout << "=== CCB Single-Stave GEANT4 ===\n"
              << "Output: " << outFile << "\nParticle: " << particle << "\nEvents: " << nEvents << std::endl;

    auto* rm = new G4RunManager();
    auto* det = new StaveDetCon();
    rm->SetUserInitialization(det);
    rm->SetUserInitialization(new StavePhys());
    rm->SetUserInitialization(new StaveActionInit(det, outFile));
    rm->Initialize();

    auto* gun = new G4ParticleGun(1);
    if (particle=="proton") gun->SetParticleDefinition(G4Proton::Proton());
    else if (particle=="deuteron") gun->SetParticleDefinition(G4Deuteron::Deuteron());
    else gun->SetParticleDefinition(G4ParticleTable::GetParticleTable()->FindParticle(particle));
    gun->SetParticlePosition(G4ThreeVector(-25.1*cm, 0, 0));
    gun->SetParticleMomentumDirection(G4ThreeVector(1, 0, 0));

    // Typical energies entering B2
    std::vector<double> energies;
    if (particle=="proton") energies = {50, 75, 100, 120, 140, 160, 180};
    else energies = {30, 50, 70, 90, 110, 130};

    int npe = nEvents / energies.size();
    for (double ke : energies) {
        gun->SetParticleEnergy(ke*MeV);
        const auto* ea = dynamic_cast<const StaveEventAction*>(rm->GetUserEventAction());
        if (ea) const_cast<StaveEventAction*>(ea)->SetBeam(particle, ke*MeV);
        std::cout << particle << " " << ke << " MeV: " << npe << " events..." << std::endl;
        rm->BeamOn(npe);
    }

    delete rm;
    std::cout << "Done." << std::endl;
    return 0;
}
