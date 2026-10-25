  // Optical transport cost guards (#1623). A photon still bouncing long after
  // the SiPM acquisition window ([-20, 250] ns in the response model, which
  // discards later arrivals anyway) cannot contribute to the ADC, but it does
  // still increment the raw arrival counters -- so every kill is COUNTED and
  // reported rather than silently applied. Both limits are off by default.
  if (cfg_.optical_max_time_ns > 0.0 &&
      track->GetGlobalTime() / ns > cfg_.optical_max_time_ns) {
    ++d.n_optical_killed_time;
    track->SetTrackStatus(fStopAndKill);
    return;
  }
  if (cfg_.optical_max_steps > 0 &&
      track->GetCurrentStepNumber() > cfg_.optical_max_steps) {
    ++d.n_optical_killed_steps;
    track->SetTrackStatus(fStopAndKill);
    return;
  }

