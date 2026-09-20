"""Generate the light/dark sample pair committed beside docs/research/altair-export.md.

Not project code — this is the worked example the research note refers to, kept
runnable so the recommendation can be re-checked:

    uv run --with altair --with vl-convert-python --with polars \
        docs/research/assets/make_samples.py
"""

import altair as alt
import polars as pl

OUT = "docs/research/assets"
WIDTH, HEIGHT = 640, 400

# GitHub's own rendered-content colours, light and dark (primer).
LIGHT = {"bg": "#ffffff", "fg": "#1f2328", "muted": "#59636e", "grid": "#d1d9e0", "line": "#0969da"}
DARK = {"bg": "#0d1117", "fg": "#f0f6fc", "muted": "#9198a1", "grid": "#21262d", "line": "#4493f8"}


def theme(c: dict[str, str]) -> alt.theme.ThemeConfig:
    return {
        "config": {
            "background": c["bg"],
            "font": "sans-serif",
            "title": {"color": c["fg"], "fontSize": 15, "anchor": "start", "subtitleColor": c["muted"]},
            "axis": {
                "labelColor": c["muted"],
                "titleColor": c["fg"],
                "gridColor": c["grid"],
                "domainColor": c["grid"],
                "tickColor": c["grid"],
            },
            "legend": {"labelColor": c["muted"], "titleColor": c["fg"]},
            "view": {"stroke": "transparent"},
        }
    }


def calibration_chart(colors: dict[str, str]) -> alt.LayerChart:
    # Stand-in numbers; the real one comes from the backtest.
    bins = pl.DataFrame(
        {
            "predicted": [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95],
            "observed": [0.04, 0.17, 0.22, 0.38, 0.44, 0.52, 0.69, 0.71, 0.88, 0.93],
        }
    )
    diagonal = (
        alt.Chart(pl.DataFrame({"x": [0.0, 1.0], "y": [0.0, 1.0]}))
        .mark_line(strokeDash=[4, 4], color=colors["muted"], strokeWidth=1)
        .encode(x="x:Q", y="y:Q")
    )
    curve = (
        alt.Chart(bins)
        .mark_line(point=alt.OverlayMarkDef(filled=True, size=45), color=colors["line"], strokeWidth=2)
        .encode(
            x=alt.X("predicted:Q", title="Predicted probability", scale=alt.Scale(domain=[0, 1])),
            y=alt.Y("observed:Q", title="Observed frequency", scale=alt.Scale(domain=[0, 1])),
        )
    )
    return (diagonal + curve).properties(
        width=WIDTH,
        height=HEIGHT,
        title=alt.TitleParams("Calibration", subtitle="Sample export — vl-convert-python 1.9.0, scale_factor=2"),
    )


def main() -> None:
    for name, colors in (("light", LIGHT), ("dark", DARK)):
        alt.theme.register(f"gh-{name}", enable=False)(lambda c=colors: theme(c))
        with alt.theme.enable(f"gh-{name}"):
            calibration_chart(colors).save(f"{OUT}/calibration-{name}.png", scale_factor=2)
        print(f"wrote {OUT}/calibration-{name}.png")


if __name__ == "__main__":
    main()
