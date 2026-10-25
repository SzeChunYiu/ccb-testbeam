// Scalar expression transcription from geant4/src_patch/ScatteringGenerator.cc
// main@a61427813344e29047ca9eb9b764182eb29e4c83, blob a04da519551a7d505b4bce50b20d0b5424f0f40d.
// No Geant4 linkage: detects arithmetic domains; cannot assert transport behavior.
#include <cmath>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

struct Result { double theta3, theta4, t3, t4, p3cm, p4cm, beta3, beta4; };
Result scalar(double Ekin,double m1,double m2,double theta3cm) {
    double m3=m1, m4=m2;
    double E1=Ekin+m1, E2=m2;
    double p1=std::sqrt(Ekin*Ekin+2*Ekin*m1), p2=0;
    double beta=(p1+p2)/(E1+E2);
    double gamma=1/std::sqrt(1-beta*beta);
    double Ecm=std::sqrt(std::pow(E1+E2,2)-std::pow(p1+p2,2));
    double Ekincm=Ecm-m1-m2;
    double Ekin3cm=(Ekincm/2)*(Ekincm+2*m4)/Ecm;
    double Ekin4cm=(Ekincm/2)*(Ekincm+2*m3)/Ecm;
    double E3cm=Ekin3cm+m3, E4cm=Ekin4cm+m4;
    double p3cm=std::sqrt(Ekin3cm*Ekin3cm+2*Ekin3cm*m3);
    double p4cm=std::sqrt(Ekin4cm*Ekin4cm+2*Ekin4cm*m4);
    double beta3cm=p3cm/E3cm, beta4cm=p4cm/E4cm;
    double pcm=std::sqrt(E3cm*E3cm-m3*m3);
    double tantheta3=std::sin(theta3cm)/(gamma*(std::cos(theta3cm)+beta/beta3cm));
    double theta3=std::atan2(tantheta3,1);
    theta3=theta3<0?theta3+std::acos(-1):theta3;
    double tantheta4=std::sin(std::acos(-1)-theta3cm)/(gamma*(std::cos(std::acos(-1)-theta3cm)+beta/beta4cm));
    double theta4=std::atan2(tantheta4,1);
    double Ekin3=(gamma-1)*m3+gamma*Ekin3cm+gamma*beta*pcm*std::cos(theta3cm);
    double Ekin4=(gamma-1)*m4+gamma*Ekin4cm+gamma*beta*pcm*std::cos(std::acos(-1)-theta3cm);
    return {theta3,theta4,Ekin3,Ekin4,p3cm,p4cm,beta3cm,beta4cm};
}
int main(int argc, char** argv) {
    if(argc!=3) return 2;
    double T=std::stod(argv[1]),theta=std::stod(argv[2]);
    auto r=scalar(T,938.2720813,1875.61294257,theta);
    std::cout<<std::setprecision(17)<<r.theta3<<" "<<r.theta4<<" "<<r.t3<<" "<<r.t4<<" "<<r.beta3<<" "<<r.beta4<<"\n";
    return 0;
}
