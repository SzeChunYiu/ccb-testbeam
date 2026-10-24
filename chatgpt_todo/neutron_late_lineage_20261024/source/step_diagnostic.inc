    // #1091 ladder diagnostics: every neutron step (any volume) plus every
    // late scintillator deposit (neutron-delayed by construction — all prompt
    // non-optical activity ends within the acquisition timescale).
    if (cfg_.neutron_diagnostics) {
      const double t_ns = pre->GetGlobalTime() / ns;
      const bool in_scint = vol && vol->GetName() == "Scintillator";
      const int pdg = track->GetDefinition()->GetPDGEncoding();
      if (pdg == 2112) {
        NeutronStepRecord r;
        r.kind = 0; r.t_ns = t_ns;
        r.edep_MeV = step->GetTotalEnergyDeposit() / MeV;
        r.ke_MeV = pre->GetKineticEnergy() / MeV;
        r.in_scint = in_scint ? 1 : 0;
        r.pdg = pdg;
        d.neutron_steps.push_back(r);
      } else if (in_scint && t_ns > kLateDepositThresholdNS) {
        NeutronStepRecord r;
        r.kind = 1; r.t_ns = t_ns;
        r.edep_MeV = step->GetTotalEnergyDeposit() / MeV;
        r.ke_MeV = pre->GetKineticEnergy() / MeV;
        r.in_scint = 1;
        r.pdg = pdg;
        d.neutron_steps.push_back(r);
      }
    }
