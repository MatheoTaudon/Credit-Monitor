"""
utils/plots.py — Constructeurs de graphiques Plotly purs.

API publique :
- build_sector_chart      : Scatter par GICS Sector + courbe NS (accueil, filtres)
- build_portfolio_chart   : Bubble scatter ∝ poids + courbe NS (sales_monitor)
- build_comparables_chart : Univers grisé + NS + bond référence + comparables (comparables)

Règles :
- Zéro import Streamlit — toutes les fonctions sont pures
- Retournent go.Figure — les modules font st.plotly_chart(fig)
- Importe uniquement utils.nelson_siegel, utils.style, utils.display
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from utils.nelson_siegel import fit_nelson_siegel, generate_curve_points
from utils.style import COLORS, FONT, get_plotly_template, get_scatter_colors
from utils.display import Y_LABELS


def build_sector_chart(
    df_plot: pd.DataFrame,
    x_col: str,
    y_col: str,
    x_label: str,
    theme: str,
    *,
    height: int = 520,
    margin: dict | None = None,
    title: str = "",
    add_ns: bool = True,
    ns_annotation: dict | None = None,
    legend_y: float = -0.18,
) -> go.Figure:
    """Scatter coloré par GICS Sector + courbe Nelson-Siegel optionnelle.

    Args:
        df_plot       : DataFrame filtré et sans NaN sur x_col/y_col.
        x_col         : Nom de la colonne X (ex: "Tenor", "Tenor to Call").
        y_col         : Nom de la colonne Y (ex: "Z-Sprd", "YTM").
        x_label       : Label affiché sur l'axe X (ex: "Maturité to Call").
        theme         : "dark" ou "light".
        height        : Hauteur du graphique en pixels.
        margin        : Marges Plotly dict {l, r, t, b}. None = défaut du template.
        title         : Titre du graphique (vide = pas de titre).
        add_ns        : Si True, fitte et trace la courbe Nelson-Siegel.
        ns_annotation : Dict Plotly annotation optionnel (ex: R² quality label).
        legend_y      : Position Y de la légende horizontale sous le graphique.

    Returns:
        go.Figure prêt pour st.plotly_chart.
    """
    is_dark  = theme == "dark"
    text_col = COLORS["dark_text"] if is_dark else COLORS["light_text"]
    orange   = COLORS["bloomberg_orange"]

    colors = get_scatter_colors(theme)
    fig    = go.Figure()

    for i, sector in enumerate(sorted(df_plot["GICS Sector"].dropna().unique())):
        ds = df_plot[df_plot["GICS Sector"] == sector]
        fig.add_trace(go.Scatter(
            x=ds[x_col],
            y=ds[y_col],
            mode="markers",
            name=sector,
            marker=dict(size=6, opacity=0.7, color=colors[i % len(colors)]),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "ISIN : %{customdata[1]}<br>"
                f"{x_label} : %{{x:.1f}} ans<br>"
                f"{y_col} : %{{y:.2f}}<br>"
                "Rating : %{customdata[2]}<br>"
                "Séniorité : %{customdata[3]}"
                "<extra></extra>"
            ),
            customdata=ds[["Short Name", "ISIN", "Bloomberg Composite Ratings", "Seniority"]].values,
        ))

    if add_ns and len(df_plot) >= 10:
        ns = fit_nelson_siegel(df_plot[x_col].values, df_plot[y_col].values)
        if ns["success"]:
            t_curve, y_curve = generate_curve_points(
                ns,
                t_min=float(df_plot[x_col].min()),
                t_max=float(df_plot[x_col].max()),
            )
            fig.add_trace(go.Scatter(
                x=t_curve,
                y=y_curve,
                mode="lines",
                name="Nelson-Siegel Fit",
                line=dict(color=orange, width=2.5),
                hoverinfo="skip",
            ))

    layout = get_plotly_template(theme)
    if title:
        layout["title"] = {
            "text": title,
            "font": {"family": FONT, "size": 14, "color": text_col},
            "x": 0.01,
            "xanchor": "left",
        }
    layout["height"] = height
    if margin is not None:
        layout["margin"] = margin
    layout["xaxis"].update({"title": {"text": x_label + " (ans)", "standoff": 8}})
    layout["yaxis"].update({"title": {"text": Y_LABELS.get(y_col, y_col), "standoff": 8}})
    layout["legend"].update({
        "orientation": "h",
        "y": legend_y,
        "x": 0.5,
        "xanchor": "center",
        "yanchor": "top",
    })
    if ns_annotation is not None:
        layout["annotations"] = [ns_annotation]

    fig.update_layout(**layout)
    return fig


def build_portfolio_chart(
    df_plot: pd.DataFrame,
    x_col: str,
    y_col: str,
    x_label: str,
    theme: str,
    *,
    height: int = 420,
    margin: dict | None = None,
) -> go.Figure:
    """Bubble scatter (taille ∝ poids) par GICS Sector + courbe Nelson-Siegel.

    Attend une colonne "_size" pré-calculée dans df_plot.

    Args:
        df_plot  : DataFrame du portefeuille avec colonne "_size".
        x_col    : Colonne X (ex: "Tenor").
        y_col    : Colonne Y (ex: "Z-Sprd").
        x_label  : Label axe X (ex: "Maturité").
        theme    : "dark" ou "light".
        height   : Hauteur en pixels.
        margin   : Marges Plotly {l, r, t, b}. None = défaut du template.

    Returns:
        go.Figure prêt pour st.plotly_chart.
    """
    is_dark  = theme == "dark"
    text_col = COLORS["dark_text"] if is_dark else COLORS["light_text"]
    orange   = COLORS["bloomberg_orange"]

    y_unit = "bps" if y_col in ("Z-Sprd", "G-Spread") else "%"
    y_fmt  = ".0f"  if y_col in ("Z-Sprd", "G-Spread") else ".2f"

    palette = get_scatter_colors(theme)
    fig     = go.Figure()

    for i, sec in enumerate(sorted(df_plot["GICS Sector"].dropna().unique())):
        ds = df_plot[df_plot["GICS Sector"] == sec]
        fig.add_trace(go.Scatter(
            x=ds[x_col],
            y=ds[y_col],
            mode="markers",
            name=sec,
            marker=dict(
                size=ds["_size"].tolist(),
                color=palette[i % len(palette)],
                opacity=0.88,
                line=dict(width=0.8, color="rgba(255,255,255,0.45)"),
            ),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "%{customdata[1]}<br>"
                "Poids : %{customdata[2]}<br>"
                f"{x_label} : %{{x:.1f}} ans · {y_col} : %{{y:{y_fmt}}} {y_unit}<br>"
                "Notation : %{customdata[3]} · ESG : %{customdata[4]}"
                "<extra></extra>"
            ),
            customdata=list(zip(
                ds["Ticker"].fillna("—"),
                ds["ISIN"],
                ds["weight"].map(lambda x: f"{x * 100:.2f}%"),
                ds["Bloomberg Composite Ratings"].fillna("N/A"),
                ds["ESG Score"].map(lambda x: f"{x:.1f}" if pd.notna(x) else "N/A"),
            )),
        ))

    if len(df_plot) >= 10:
        ns = fit_nelson_siegel(df_plot[x_col].values, df_plot[y_col].values)
        if ns["success"]:
            tc, yc = generate_curve_points(
                ns,
                t_min=float(df_plot[x_col].min()),
                t_max=float(df_plot[x_col].max()),
            )
            fig.add_trace(go.Scatter(
                x=tc, y=yc, mode="lines",
                name="Nelson-Siegel",
                line=dict(color=orange, width=2),
                hoverinfo="skip",
            ))

    layout = get_plotly_template(theme)
    layout["height"] = height
    if margin is not None:
        layout["margin"] = margin
    layout["xaxis"].update({"title": {"text": x_label + " (ans)", "standoff": 6}})
    layout["yaxis"].update({"title": {"text": Y_LABELS.get(y_col, y_col), "standoff": 6}})
    layout["legend"].update({
        "orientation": "h",
        "x": 0.5, "y": -0.18,
        "xanchor": "center", "yanchor": "top",
        "bgcolor": "rgba(0,0,0,0)",
        "borderwidth": 0,
        "font": {"size": 11, "color": text_col},
        "itemsizing": "constant",
    })

    fig.update_layout(**layout)
    return fig


def build_comparables_chart(
    df_plot: pd.DataFrame,
    x_col: str,
    y_col: str,
    x_label: str,
    theme: str,
    *,
    ref_bond: pd.Series,
    comparables_df: pd.DataFrame,
    height: int = 530,
) -> go.Figure:
    """Univers grisé + courbe NS orange + bond référence (étoile) + comparables colorés.

    Args:
        df_plot        : DataFrame du contexte (même BICS + Séniorité), sans NaN sur x/y.
        x_col          : Colonne X (ex: "Tenor to Call").
        y_col          : Colonne Y (ex: "Z-Sprd").
        x_label        : Label axe X (ex: "Maturité to Call").
        theme          : "dark" ou "light".
        ref_bond       : Series du bond de référence.
        comparables_df : DataFrame des bonds comparables (KNN).
        height         : Hauteur en pixels.

    Returns:
        go.Figure prêt pour st.plotly_chart.
    """
    is_dark  = theme == "dark"
    text_sec = COLORS["dark_text_secondary"] if is_dark else COLORS["light_text_secondary"]
    orange   = COLORS["bloomberg_orange"]

    palette      = get_scatter_colors(theme)
    comp_palette = [c for c in palette if c != orange]

    comp_isins = set(comparables_df["ISIN"].tolist())
    ref_isin   = ref_bond["ISIN"]

    universe_df = df_plot[~df_plot["ISIN"].isin(comp_isins | {ref_isin})]

    fig = go.Figure()

    # 1. Univers (fond, grisé)
    if not universe_df.empty:
        fig.add_trace(go.Scatter(
            x=universe_df[x_col],
            y=universe_df[y_col],
            mode="markers",
            name="Univers",
            legendrank=100,
            marker=dict(size=5, color=text_sec, opacity=0.35),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "ISIN : %{customdata[1]}<br>"
                f"{x_label} : %{{x:.1f}} ans<br>"
                f"{y_col} : %{{y:.2f}}"
                "<extra></extra>"
            ),
            customdata=universe_df[["Short Name", "ISIN"]].values,
        ))

    # 2. Courbe Nelson-Siegel
    if len(df_plot) >= 10:
        ns_params = fit_nelson_siegel(df_plot[x_col].values, df_plot[y_col].values)
        if ns_params["success"]:
            t_curve, y_curve = generate_curve_points(
                ns_params,
                t_min=float(df_plot[x_col].min()),
                t_max=float(df_plot[x_col].max()),
            )
            fig.add_trace(go.Scatter(
                x=t_curve,
                y=y_curve,
                mode="lines",
                name="Courbe Nelson-Siegel",
                legendrank=50,
                line=dict(color=orange, width=2.5),
                hoverinfo="skip",
            ))

    # 3. Comparables (un point coloré par bond)
    for idx, (_, comp) in enumerate(comparables_df.iterrows()):
        if pd.isna(comp.get(x_col)) or pd.isna(comp.get(y_col)):
            continue
        rating = comp.get("Bloomberg Composite Ratings", "N/A")
        fig.add_trace(go.Scatter(
            x=[comp[x_col]],
            y=[comp[y_col]],
            mode="markers",
            name=f"{comp['Short Name']} ({rating})",
            legendrank=10 + idx,
            marker=dict(
                size=10,
                color=comp_palette[idx % len(comp_palette)],
                symbol="circle",
                line=dict(width=1.5, color="#FFFFFF"),
            ),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "ISIN : %{customdata[1]}<br>"
                f"Notation : %{{customdata[2]}}<br>"
                f"{x_label} : %{{x:.1f}} ans<br>"
                f"{y_col} : %{{y:.2f}}"
                "<extra></extra>"
            ),
            customdata=[[comp["Short Name"], comp["ISIN"], rating]],
        ))

    # 4. Bond de référence (étoile orange, premier plan)
    ref_tenor = ref_bond.get(x_col)
    ref_y     = ref_bond.get(y_col)
    if pd.notna(ref_tenor) and pd.notna(ref_y):
        ref_rating = ref_bond.get("Bloomberg Composite Ratings", "N/A")
        fig.add_trace(go.Scatter(
            x=[ref_tenor],
            y=[ref_y],
            mode="markers",
            name=f"★ {ref_bond.get('Short Name', ref_isin)} [référence]",
            legendrank=1,
            marker=dict(
                size=15,
                color=orange,
                symbol="star",
                line=dict(width=1.5, color="#FFFFFF"),
            ),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "ISIN : %{customdata[1]}<br>"
                f"Notation : %{{customdata[2]}}<br>"
                f"{x_label} : %{{x:.1f}} ans<br>"
                f"{y_col} : %{{y:.2f}}"
                "<extra></extra>"
            ),
            customdata=[[ref_bond.get("Short Name", ""), ref_isin, ref_rating]],
        ))

    layout = get_plotly_template(theme)
    layout["height"] = height
    layout["xaxis"].update({"title": {"text": x_label + " (ans)", "standoff": 8}})
    layout["yaxis"].update({"title": {"text": Y_LABELS.get(y_col, y_col), "standoff": 8}})
    layout["legend"].update({
        "orientation": "v",
        "x": 1.02,
        "y": 1.0,
        "xanchor": "left",
        "yanchor": "top",
        "bgcolor": "rgba(0,0,0,0)",
        "borderwidth": 0,
        "itemsizing": "constant",
    })

    fig.update_layout(**layout)
    return fig
