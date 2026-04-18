"""
accueil.py — Homepage : courbe Nelson-Siegel de l'univers obligataire.

Orchestration uniquement. Toute logique métier est dans utils/.
"""
import streamlit as st
import pandas as pd
from datetime import date

from utils.loader import load_data, get_sectors, get_seniorities, filter_df
from utils.nelson_siegel import (
    fit_nelson_siegel,
    generate_curve_points,
    get_fit_quality_label,
)
from utils.style import COLORS, FONT, get_theme, inject_css
from utils.display import format_value, Y_LABELS, X_COL_MAP, render_bond_card
from utils.plots import build_sector_chart


@st.dialog("Détails de l'obligation", width="medium")
def _bond_detail_dialog(bond: pd.Series, theme: str) -> None:
    st.markdown(render_bond_card(bond, theme), unsafe_allow_html=True)
    _, col_close = st.columns([3, 1])
    with col_close:
        if st.button("Fermer", use_container_width=True, key="_bd_close_acc"):
            st.session_state["_bd_ck_acc"] += 1
            st.rerun()


def show() -> None:
    # ── Config ────────────────────────────────────────────────────────

    theme = get_theme()
    inject_css(theme)

    # ── Chargement des données ────────────────────────────────────────
    try:
        df = load_data()
    except FileNotFoundError as exc:
        st.error(str(exc))
        st.stop()
    except Exception as exc:
        st.error(f"Erreur inattendue lors du chargement : {exc}")
        st.stop()

    # ── Session state (initialisation unique ici) ─────────────────────
    if "selected_sectors" not in st.session_state:
        st.session_state["selected_sectors"] = []
    if "selected_seniorities" not in st.session_state:
        st.session_state["selected_seniorities"] = []
    if "_bd_ck_acc" not in st.session_state:
        st.session_state["_bd_ck_acc"] = 0

    # ── Header ────────────────────────────────────────────────────────
    text_sec = COLORS["dark_text_secondary"] if theme == "dark" else COLORS["light_text_secondary"]
    text_col = COLORS["dark_text"]           if theme == "dark" else COLORS["light_text"]

    col_title, col_date = st.columns([4, 1])
    with col_title:
        st.markdown(
            f'<h2 style="color:{COLORS["bloomberg_orange"]};font-family:{FONT};'
            f'margin:0;font-weight:700;letter-spacing:-0.3px;line-height:1.2">'
            f'Bloomberg Euro Corporate Bond Index</h2>'
            f'<p style="color:{text_sec};font-family:{FONT};margin:0.2rem 0 0 0;'
            f'font-size:0.88rem;font-weight:400">Fixed Income Analytics</p>',
            unsafe_allow_html=True,
        )
    with col_date:
        st.markdown(
            f'<p style="text-align:right;color:{text_sec};font-family:{FONT};'
            f'padding-top:1rem;font-size:0.82rem;margin:0">'
            f'{date.today().strftime("%d %B %Y")}</p>',
            unsafe_allow_html=True,
        )

    # ── Navigation ────────────────────────────────────────────────────
    nav1, nav2, nav3 = st.columns(3)
    with nav1:
        st.button("Trouver des Comparables", on_click=lambda: st.session_state.update({"page": "comparables"}), use_container_width=True, key="nav_acc_comp")
    with nav2:
        st.button("Fonds des clients", on_click=lambda: st.session_state.update({"page": "sales_monitor"}), use_container_width=True, key="nav_acc_sm")
    with nav3:
        st.button("Filtrer l'Univers", on_click=lambda: st.session_state.update({"page": "filtres"}), use_container_width=True, key="nav_acc_filt")

    st.divider()

    # ── Filtres ───────────────────────────────────────────────────────
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        selected_sectors = st.multiselect(
            "Secteur GICS",
            options=get_sectors(df),
            key="selected_sectors",
        )
    with f2:
        selected_seniorities = st.multiselect(
            "Séniorité",
            options=get_seniorities(df),
            key="selected_seniorities",
        )
    with f3:
        y_col = st.selectbox(
            "Axe Y",
            options=["Z-Sprd", "YTM", "G-Spread"],
            index=0,
            key="y_axis",
        )
    with f4:
        x_choice = st.selectbox("Axe X", options=["Maturité to Call", "Maturité"], key="acc_x_axis")

    x_col = X_COL_MAP[x_choice]

    # ── Filtrage ──────────────────────────────────────────────────────
    df_filtered = filter_df(df, sectors=selected_sectors, seniorities=selected_seniorities)

    if df_filtered.empty:
        st.warning("Aucune obligation correspondant aux filtres sélectionnés.")
        st.stop()

    df_plot = df_filtered.dropna(subset=[x_col, y_col]).reset_index(drop=True)

    if df_plot.empty:
        st.warning(f"Aucune obligation avec des données valides pour {y_col} et {x_col}.")
        st.stop()

    # ── Annotation Nelson-Siegel (R² quality label) ───────────────────
    MIN_NS_POINTS = 10
    info_msg  = None
    annotation = None

    if len(df_plot) < MIN_NS_POINTS:
        info_msg = (
            f"Moins de {MIN_NS_POINTS} obligations après filtre "
            f"({len(df_plot)}) — courbe Nelson-Siegel non calculée."
        )
    else:
        params = fit_nelson_siegel(df_plot[x_col].values, df_plot[y_col].values)

        if params["success"]:
            label = get_fit_quality_label(params["r_squared"])
            quality_color = {
                "Excellent": COLORS["positive"],
                "Bon":       COLORS["positive"],
                "Moyen":     COLORS["neutral"],
                "Faible":    COLORS["negative"],
            }[label]
            annotation = dict(
                text=f"R² = {params['r_squared']:.2f} — Qualité : {label}",
                xref="paper", yref="paper",
                x=0.99, y=0.99,
                xanchor="right", yanchor="top",
                showarrow=False,
                font=dict(size=11, color=quality_color, family=FONT),
                bgcolor="rgba(0,0,0,0.4)",
                bordercolor=quality_color,
                borderwidth=1,
                borderpad=5,
            )
        else:
            info_msg = (
                f"Fit Nelson-Siegel non convergé — {params['reason']} "
                f"({params['n_points']} points utilisés)."
            )

    # ── Graphique ─────────────────────────────────────────────────────
    fig = build_sector_chart(
        df_plot, x_col, y_col, x_choice, theme,
        height=520,
        title=f"Courbe {y_col} — {len(df_plot)} obligations",
        ns_annotation=annotation,
    )
    event = st.plotly_chart(fig, on_select="rerun", key=f"chart_acc_{st.session_state['_bd_ck_acc']}", use_container_width=True)

    if event.selection.points:
        cd = event.selection.points[0].get("customdata") or []
        if len(cd) > 1:
            matches = df_plot[df_plot["ISIN"] == cd[1]]
            if not matches.empty:
                _bond_detail_dialog(matches.iloc[0], theme)

    if info_msg:
        st.info(info_msg)

    # ── Métriques ─────────────────────────────────────────────────────
    st.divider()
    m1, m2, m3, m4 = st.columns(4)

    with m1:
        st.metric("Obligations", len(df_filtered))
    with m2:
        st.metric("YTM Médian", format_value(df_filtered["YTM"].median(), "{:.2f}%"))
    with m3:
        st.metric("Z-Spread Médian", format_value(df_filtered["Z-Sprd"].median(), "{:.0f} bps"))
    with m4:
        st.metric("Duration Médiane", format_value(df_filtered["ModIfied Duration"].median(), "{:.1f} ans"))
