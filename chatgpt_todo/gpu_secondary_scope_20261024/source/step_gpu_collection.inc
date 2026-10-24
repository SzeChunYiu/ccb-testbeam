    if (cfg_.gpu_optical) {
      const G4TrackVector* sec = step->GetSecondary();
      if (sec) {
        for (G4Track* t : *sec) {
          if (!t || t->GetDefinition() != G4OpticalPhoton::OpticalPhoton())
            continue;
          const G4ThreeVector& p = t->GetPosition();
          const G4ThreeVector& m = t->GetMomentumDirection();
          const G4ThreeVector& l = t->GetPolarization();
          const double energy = t->GetKineticEnergy();
          const double wl_nm = (energy > 0.0)
              ? ((h_Planck * c_light / energy) / nm) : 0.0;
          const double t_ns = t->GetGlobalTime() / ns;
          d.gpu_photons.push_back(static_cast<float>(p.x() / mm));
          d.gpu_photons.push_back(static_cast<float>(p.y() / mm));
          d.gpu_photons.push_back(static_cast<float>(p.z() / mm));
          d.gpu_photons.push_back(static_cast<float>(t_ns));
          d.gpu_photons.push_back(static_cast<float>(m.x()));
          d.gpu_photons.push_back(static_cast<float>(m.y()));
          d.gpu_photons.push_back(static_cast<float>(m.z()));
          d.gpu_photons.push_back(0.0f);
          d.gpu_photons.push_back(static_cast<float>(l.x()));
          d.gpu_photons.push_back(static_cast<float>(l.y()));
          d.gpu_photons.push_back(static_cast<float>(l.z()));
          d.gpu_photons.push_back(static_cast<float>(wl_nm));
          d.gpu_photons.push_back(0.0f);  // q3.x orient/boundary/flag
          d.gpu_photons.push_back(0.0f);  // q3.y identity
          d.gpu_photons.push_back(0.0f);  // q3.z index
          d.gpu_photons.push_back(0.0f);  // q3.w flagmask (input photon)
          ++d.n_gpu_photons;
        }
      }
    }
