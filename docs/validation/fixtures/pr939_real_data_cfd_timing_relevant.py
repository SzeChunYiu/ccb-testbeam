def make_figures(df, eval_rows, off_peak, tag):
    fig, ax = plt.subplots(1, 1, figsize=(7, 4))
    for col, c in [
        (f"t_cfd{int(round(CFD_FRACTIONS[0]*100)):02d}", "C0"),
        ("t_cfd20", "C2"),
    ]:
        if col not in df.columns:
            continue
        tof = {
            s: (1 if s == "B4" else 2 if s == "B6" else 3)
            * SPACING_CM
            * TOF_PER_CM_NS
            for s in df["stave"].unique()
        }
        d = df.copy()
        d["tcorr"] = (
            d[col]
            - d["stave"].map(tof)
            - d["stave"].map(
                {k: v * SAMPLE_PERIOD_NS for k, v in off_peak.items()}
            )
        )
        wide = d.pivot(index="event_id", columns="stave", values="tcorr").dropna()
        if CLEAN_PAIR[0] in wide and CLEAN_PAIR[1] in wide:
            v = (wide[CLEAN_PAIR[0]] - wide[CLEAN_PAIR[1]]).to_numpy()
            ax.hist(
                v,
                bins=80,
                range=(-10, 10),
                alpha=0.5,
                label=(
                    f"{col} {'-'.join(CLEAN_PAIR)} "
                    f"s68={s02.sigma68(v):.2f}ns"
                ),
                color=c,
            )
