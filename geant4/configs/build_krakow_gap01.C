// build_krakow_gap01.C
// Fixes GAP-01 (MV3 stopping-depth material budget) by adding configurable
// inter-stave dead material between scintillator bars + an optional upstream
// absorber, modifying the existing CCB/Krakau test-beam TGeoManager in place.
//
// USAGE:
//   root -b -q 'build_krakow_gap01.C("in.root","out.root")'
//
// ENV-OVERRIDABLE PARAMETERS (all with justified defaults):
//   GAP01_DEAD_THK_CM     default 0.162  (FR-4 PCB equivalent, ~0.30 g/cm^2 per gap;
//                            MV3b/MV3c-revised per-pair estimate 0.1-0.5 g/cm^2)
//   GAP01_DEAD_DENSITY    default 1.85   (FR-4 bulk density g/cm^3)
//   GAP01_ABS_THK_CM      default 0.0    (upstream absorber thickness; 0 = off.
//                            Scan to find the value that brings chi2/ndf down.)
//   GAP01_ABS_MATERIAL    default "Al"   (use any material already in the geometry)

#include "TGeoManager.h"
#include "TGeoVolume.h"
#include "TGeoMaterial.h"
#include "TGeoMedium.h"
#include "TGeoTube.h"
#include "TGeoBBox.h"
#include "TGeoMatrix.h"
#include "TFile.h"
#include "TSystem.h"
#include "TEnv.h"
#include <iostream>
#include <cstdlib>
#include <cmath>
#include <string>

static double envD(const char* k, double def) {
  const char* v = gSystem->Getenv(k);
  return v ? std::strtod(v, nullptr) : def;
}

void build_krakow_gap01(const char* inFile  = "krakow_109_8-38deg_4-71deg.root",
                        const char* outFile = "krakow_gap01.root")
{
  // ---- parameters (env-overridable) ----
  double deadThk    = envD("GAP01_DEAD_THK_CM", 0.162);  // cm per inter-stave gap
  double deadRho    = envD("GAP01_DEAD_DENSITY", 1.85);   // g/cm^3 (FR-4)
  double absThk     = envD("GAP01_ABS_THK_CM",  0.0);     // cm upstream absorber
  const char* absMed= gSystem->Getenv("GAP01_ABS_MATERIAL");
  if(!absMed) absMed = "Al";

  // ---- original geometry constants (from inspection of the .root file) ----
  const double barHX = 25.0, barHY = 2.5, barHZ = 1.0; // Sci_bar half-dims (cm)
  // Stack1: 8 bars centres z = -7,-5,...,7  (2 cm pitch)
  // Stack2: 4 bars centres z = -3,-1,1,3   (2 cm pitch)
  const int n1 = 8, n2 = 4;

  // ---- load existing geometry ----
  TFile* fin = TFile::Open(inFile);
  if(!fin || fin->IsZombie()){ std::cerr<<"E> cannot open "<<inFile<<"\n"; return; }
  TGeoManager* geo = (TGeoManager*)fin->Get("geometry");
  if(!geo){ std::cerr<<"E> no TGeoManager 'geometry' in file\n"; return; }
  gGeoManager = geo;
  geo->cd();

  std::cout<<"GAP01 build: in="<<inFile<<" out="<<outFile<<"\n";
  std::cout<<"  deadThk="<<deadThk<<" cm  deadRho="<<deadRho<<" g/cm3"
           <<"  (areal="<<deadThk*deadRho<<" g/cm2 per gap)\n";
  std::cout<<"  absThk="<<absThk<<" cm  absMed="<<absMed<<"\n";

  // ---- add DeadMat material + medium ----
  // CCB_DeadMat: FR-4-like structural material (PCB substrate + connectors).
  // Modelled as an effective material with Z_eff~8 A_eff~16 (SiO2/epoxy typical),
  // configurable density.  This is a STOPPING-POWER-EQUIVALENT proxy: exact FR-4
  // composition (woven SiO2 cloth + epoxy + Cu traces) would need per-element
  // definition, but for CSDA proton range the areal density is the driver.
  TGeoMaterial* matDead = new TGeoMaterial("CCB_DeadMat", 16.0, 8.0, deadRho);
  Int_t nmedOld = geo->GetListOfMedia()->GetEntries();
  TGeoMedium* medDead = new TGeoMedium("CCB_DeadMat", nmedOld, matDead);

  // ---- shrink Sci_bar shape to create inter-stave gaps ----
  // All bars share one TGeoVolume "Sci_bar".  Reducing its half-Z by deadThk/2
  // creates a gap of width deadThk at every bar boundary.
  double newBarHZ = barHZ - deadThk / 2.0;
  if(newBarHZ <= 0){ std::cerr<<"E> deadThk too large, bar would vanish\n"; return; }
  TGeoVolume* sciBar = geo->GetVolume("Sci_bar");
  sciBar->SetShape(new TGeoBBox(barHX, barHY, newBarHZ));
  std::cout<<"  Sci_bar half-Z: "<<barHZ<<" -> "<<newBarHZ<<" cm\n";

  // ---- DeadMat slab volume ----
  TGeoBBox* deadShape = new TGeoBBox(barHX, barHY, deadThk / 2.0);
  TGeoVolume* deadVol1 = new TGeoVolume("DeadLayer", deadShape, medDead);
  TGeoVolume* deadVol2 = new TGeoVolume("DeadLayer", deadShape, medDead);

  // ---- insert dead layers between bars in Sci_stack1 (7 gaps) ----
  TGeoVolume* s1 = geo->GetVolume("Sci_stack1");
  for(int i = 0; i < n1 - 1; i++){
    double z = -6.0 + i * 2.0; // midpoints: -6,-4,-2,0,2,4,6
    s1->AddNode(deadVol1, i, new TGeoTranslation(0, 0, z));
  }

  // ---- insert dead layers between bars in Sci_stack2 (3 gaps) ----
  TGeoVolume* s2 = geo->GetVolume("Sci_stack2");
  for(int i = 0; i < n2 - 1; i++){
    double z = -2.0 + i * 2.0; // midpoints: -2,0,2
    s2->AddNode(deadVol2, i, new TGeoTranslation(0, 0, z));
  }

  std::cout<<"  Added DeadLayer: "<<(n1-1)<<" in stack1, "<<(n2-1)<<" in stack2\n";
  double areal1 = (n1-1) * deadThk * deadRho;
  double areal2 = (n2-1) * deadThk * deadRho;
  std::cout<<"  Total dead material areal: stack1="<<areal1<<" g/cm2, stack2="<<areal2<<" g/cm2\n";

  // ---- optional upstream absorber slabs before each arm ----
  if(absThk > 0.0){
    TGeoMedium* medAbs = geo->GetMedium(absMed);
    if(!medAbs){ std::cerr<<"W> absorber medium '"<<absMed<<"' not found, skipping\n"; }
    else{
      TGeoBBox* absShape = new TGeoBBox(barHX, barHY, absThk / 2.0);
      TGeoVolume* absVol = new TGeoVolume("UpstreamAbsorber", absShape, medAbs);
      TGeoVolume* mother = geo->GetTopVolume();
      // Place before each stack entrance face (distance = 109 - absThk/2 along arm dir)
      // Rotation uses RotateY to match the stack orientation (NOT Euler angles).
      // Stack1: angle -38 deg from z-axis in xz-plane
      double d1 = 109.0 - absThk/2.0;
      double a1 = -38.0 * M_PI / 180.0;
      double x1 = d1 * sin(a1), z1 = d1 * cos(a1);
      TGeoRotation* rotA1 = new TGeoRotation(); rotA1->RotateY(-38.0);
      mother->AddNode(absVol, 1, new TGeoCombiTrans(x1, 0, z1, rotA1));
      // Stack2: angle 71.5 deg from z-axis in xz-plane
      double d2 = 109.0 - absThk/2.0;
      double a2 = 71.5 * M_PI / 180.0;
      double x2 = d2 * sin(a2), z2 = d2 * cos(a2);
      TGeoRotation* rotA2 = new TGeoRotation(); rotA2->RotateY(71.5);
      mother->AddNode(absVol, 2, new TGeoCombiTrans(x2, 0, z2, rotA2));
      std::cout<<"  Added UpstreamAbsorber ("<<absMed<<", "<<absThk<<" cm) before each arm\n";
      double absAreal = absThk * (medAbs->GetMaterial()->GetDensity());
      std::cout<<"    absorber areal density = "<<absAreal<<" g/cm2\n";
    }
  }

  // ---- export ----
  geo->Export(outFile);
  std::cout<<"GAP01 geometry written to "<<outFile<<"\n";

  // ---- summary of total added material budget ----
  std::cout<<"\n=== GAP-01 MATERIAL BUDGET SUMMARY ===\n";
  std::cout<<"Inter-stave dead material (FR-4, "<<deadRho<<" g/cm3):\n";
  std::cout<<"  B-arm (4 bars, 3 gaps): "<<areal2<<" g/cm2 added\n";
  std::cout<<"  A-arm (8 bars, 7 gaps): "<<areal1<<" g/cm2 added\n";
  if(absThk > 0.0){
    TGeoMedium* medAbs = geo->GetMedium(absMed);
    if(medAbs)
      std::cout<<"Upstream absorber ("<<absMed<<"): "<<absThk*medAbs->GetMaterial()->GetDensity()<<" g/cm2 per arm\n";
  }
  std::cout<<"NOTE: existing geometry already contains CD2 target (0.23 g/cm2),\n";
  std::cout<<"  Mylar window (0.014 g/cm2), Al beam pipe (1.35 g/cm2 wall),\n";
  std::cout<<"  and 2x trigger scintillators (~2.06 g/cm2 if both paddles crossed).\n";
  std::cout<<"  Source: MV3c geometry-source audit + docs/01_setup_and_detector.md\n";
}
