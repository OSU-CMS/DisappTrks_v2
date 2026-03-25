void fullCutflow() {
    TFile* f = TFile::Open("trackCutPlots.root");

    // Must match mypath order and only include modules that book a cutflow histogram
    const std::vector<std::string> modules = {
        "QualityCut",
        "TagAndProbe",
        "TrackLeptonPairFilter",
        "TrackElectronFiducialFilter",
        "TrackMuonFiducialFilter",
        "TrackEcalDeadChannelFilter",
        "JvmAppliedEventFilter",
        "TrackMuonDeltaRFilter",
        "TrackTauDeltaRFilter",
        "TrackLayerFilter",
    };

    printf("%-45s %12s %12s %12s\n", "Cut", "Events", "Cumul. Eff", "Indiv. Eff");
    printf("%s\n", std::string(85, '-').c_str());

    double total    = -1.0;
    double previous = -1.0;

    for (const auto& module : modules) {
        TH1D* cutflow = (TH1D*)f->Get((module + "/cutflow").c_str());
        if (!cutflow) {
            printf("WARNING: no cutflow histogram found for module '%s'\n", module.c_str());
            continue;
        }

        // The first bin of the first module sets the total for cumulative efficiency
        if (total < 0) total = cutflow->GetBinContent(1);

        for (int i = 1; i <= cutflow->GetNbinsX(); ++i) {
            const double current = cutflow->GetBinContent(i);

            // Skip empty bins — can happen if a module's later bins are unfilled
            if (current == 0) continue;

            // Skip the "Total" bin of subsequent modules — it duplicates
            // the "Passed" bin of the previous module
            if (i == 1 && module != modules.front()) {
                previous = current;
                continue;
            }

            if (previous < 0) previous = current;

            const double cumulEff = 100.0 * current / total;
            const double indivEff = previous > 0 ? 100.0 * current / previous : 0.0;

            const std::string label = std::string(cutflow->GetXaxis()->GetBinLabel(i));
            printf("%-45s %12.1f %11.3f%% %11.3f%%\n",
                   label.c_str(), current, cumulEff, indivEff);

            previous = current;
        }
    }

    f->Close();
}
