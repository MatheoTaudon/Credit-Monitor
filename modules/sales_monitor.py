"""
pages/2_Sales_Monitor.py — Sales Monitor : portefeuille fonds clients + propositions de switch.

Layout :
  Header     : titre + bouton retour
  Sélection  : dropdown Asset Manager → dropdown Fonds (filtré)
  Metrics    : 4 KPIs portefeuille
  Chart      : courbe du portefeuille (Tenor × Z-Sprd, taille ∝ poids)
  Switches   : recherche ISIN/Ticker + filtres Green / ESG → 10 meilleures propositions
"""
import numpy as np
import pandas as pd
import streamlit as st

from utils.funds import (
    build_portfolio,
    get_asset_managers,
    get_fund_display_name,
    get_funds_for_am,
    load_funds,
    propose_switches,
)
from utils.loader import load_data
from utils.style import COLORS, FONT, get_theme, inject_css
from utils.display import format_value, render_bond_card, render_switch_card, Y_LABELS, X_COL_MAP
from utils.plots import build_portfolio_chart


@st.dialog("Détails de l'obligation", width="large")
def _bond_detail_dialog(bond: pd.Series, theme: str) -> None:
    st.markdown(render_bond_card(bond, theme), unsafe_allow_html=True)
    _, col_close = st.columns([3, 1])
    with col_close:
        if st.button("Fermer", use_container_width=True, key="_bd_close_sm"):
            st.session_state["_bd_ck_sm"] += 1
            st.rerun()


def show() -> None:

    theme = get_theme()
    inject_css(theme)

    if "_bd_ck_sm" not in st.session_state:
        st.session_state["_bd_ck_sm"] = 0

    is_dark  = theme == "dark"
    text_col = COLORS["dark_text"]           if is_dark else COLORS["light_text"]
    text_sec = COLORS["dark_text_secondary"] if is_dark else COLORS["light_text_secondary"]
    orange   = COLORS["bloomberg_orange"]
    green_c  = COLORS["positive"]

    # ── Helpers locaux ───────────────────────────────────────────────

    def _section_header(title: str, subtitle: str = "") -> str:
        sub_html = (
            f'<p style="color:{text_sec};font-family:{FONT};margin:0.15rem 0 0;'
            f'font-size:0.83rem">{subtitle}</p>'
            if subtitle else ""
        )
        return (
            f'<h3 style="color:{text_col};font-family:{FONT};font-size:1.05rem;'
            f'font-weight:700;margin:0">{title}</h3>'
            + sub_html
        )

    # ── Chargement des données ────────────────────────────────────────

    try:
        universe = load_data()
    except Exception as exc:
        st.error(str(exc))
        st.stop()

    try:
        funds_raw = load_funds()
    except FileNotFoundError as exc:
        st.error(str(exc))
        st.stop()

    if not funds_raw:
        st.warning("Aucun fonds trouvé dans Funds.xlsx.")
        st.stop()

    # ══════════════════════════════════════════════════════════════════
    # HEADER
    # ══════════════════════════════════════════════════════════════════
    col_h, col_nav = st.columns([5, 1])
    with col_h:
        st.markdown(
            f'<h2 style="color:{orange};font-family:{FONT};margin:0;font-weight:700;'
            f'letter-spacing:-0.3px;line-height:1.2">Fonds des clients</h2>'
            f'<p style="color:{text_sec};font-family:{FONT};margin:0.2rem 0 0;font-size:0.88rem">'
            f'Suivi des fonds clients benchmarké à l\'indice (depuis reporting des sociétés de gestion) · Propositions de switch intelligentes</p>',
            unsafe_allow_html=True,
        )
    with col_nav:
        st.markdown('<div style="padding-top:1.1rem">', unsafe_allow_html=True)
        def _to_accueil():
            st.session_state["page"] = "accueil"
        st.button("← Accueil", on_click=_to_accueil, use_container_width=True, key="nav_sm_accueil")
        st.markdown("</div>", unsafe_allow_html=True)

    st.divider()

    # ══════════════════════════════════════════════════════════════════
    # SÉLECTION AM → FONDS (cascade)
    # ══════════════════════════════════════════════════════════════════
    am_list   = get_asset_managers(funds_raw)
    has_am_data = len(am_list) > 0

    if has_am_data:
        am_col, fund_col, _ = st.columns([1.6, 2.6, 1.8])
        with am_col:
            selected_am = st.selectbox("Asset Manager", am_list, key="sales_am_selector")
        funds_for_am = get_funds_for_am(funds_raw, selected_am)
        if not funds_for_am:
            funds_for_am = funds_raw
    else:
        selected_am  = None
        funds_for_am = funds_raw
        fund_col, _  = st.columns([2.6, 3.4])

    display_names  = {sheet: get_fund_display_name(sheet, df) for sheet, df in funds_for_am.items()}
    name_to_sheet  = {v: k for k, v in display_names.items()}

    with fund_col:
        selected_display = st.selectbox("Fonds", list(display_names.values()), key="sales_fund_selector")

    selected_sheet = name_to_sheet[selected_display]
    portfolio      = build_portfolio(funds_for_am[selected_sheet], universe)

    if portfolio.empty:
        st.warning("Portefeuille vide ou colonnes manquantes dans le fichier Funds.xlsx.")
        st.stop()

    st.divider()

    # ══════════════════════════════════════════════════════════════════
    # COURBE DU PORTEFEUILLE
    # ══════════════════════════════════════════════════════════════════
    g_title_col, g_y_col, g_x_col = st.columns([3, 1, 1])
    with g_title_col:
        st.markdown(
            f'<p style="font-size:0.88rem;font-weight:600;color:{text_col};'
            f'font-family:{FONT};margin:0">Portefeuille — {selected_display}</p>',
            unsafe_allow_html=True,
        )
    with g_y_col:
        y_col_chart = st.selectbox(
            "Axe Y", ["Z-Sprd", "YTM", "G-Spread"],
            key="sales_chart_y", label_visibility="collapsed",
        )
    with g_x_col:
        x_choice = st.selectbox(
            "Axe X", ["Maturité", "Maturité to Call"],
            key="sales_chart_x", label_visibility="collapsed",
        )
    x_col_chart = X_COL_MAP[x_choice]

    df_plot = portfolio.dropna(subset=[x_col_chart, y_col_chart]).reset_index(drop=True).copy()

    if df_plot.empty:
        st.info("Aucun bond avec données Tenor et " + y_col_chart + " disponibles.")
    else:
        w = df_plot["weight"].values
        w_min, w_max = float(w.min()), float(w.max())
        df_plot["_size"] = (
            6 + (w - w_min) / (w_max - w_min) * 14
            if w_max > w_min else np.full(len(w), 10.0)
        )

        fig = build_portfolio_chart(
            df_plot, x_col_chart, y_col_chart, x_choice, theme,
            height=420,
            margin={"l": 45, "r": 10, "t": 10, "b": 110},
        )
        event = st.plotly_chart(fig, on_select="rerun", key=f"chart_sm_{st.session_state['_bd_ck_sm']}", use_container_width=True)

        if event.selection.points:
            cd = event.selection.points[0].get("customdata") or []
            if len(cd) > 1:
                matches = df_plot[df_plot["ISIN"] == cd[1]]
                if not matches.empty:
                    _bond_detail_dialog(matches.iloc[0], theme)

    st.divider()

    # ══════════════════════════════════════════════════════════════════
    # PROPOSITIONS DE SWITCH
    # ══════════════════════════════════════════════════════════════════
    st.markdown(_section_header("Propositions de Switch"), unsafe_allow_html=True)
    st.markdown('<div style="height:0.6rem"></div>', unsafe_allow_html=True)

    esg_col, _ = st.columns([3, 3])
    with esg_col:
        st.markdown(
            f'<p style="font-size:0.75rem;font-weight:700;color:{text_sec};'
            f'margin:0 0 0.3rem;font-family:{FONT};text-transform:uppercase;'
            f'letter-spacing:0.07em;border-left:2px solid {orange};padding-left:7px">'
            f'Contraintes ESG</p>',
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2)
        with c1:
            green_flag = st.checkbox("Green Bond uniquement", key="sales_sw_green")
        with c2:
            esg_flag = st.checkbox("Meilleur score ESG uniquement", key="sales_sw_esg")

    if esg_flag and green_flag:
        badge_label = "ESG+ · GREEN"
        mode_accent = green_c
    elif esg_flag:
        badge_label = "ESG+"
        mode_accent = orange
    elif green_flag:
        badge_label = "GREEN BOND"
        mode_accent = green_c
    else:
        badge_label = "SWITCH"
        mode_accent = orange

    alg_note = (
        "Même BICS · même pays · au moins même séniorité · même type coupon · "
        "duration ±1 · au moins même rating · pickup Z-Sprd maximal · bonds NR exclus"
    )
    st.markdown(
        f'<p style="font-size:0.78rem;color:{text_sec};margin:0.5rem 0 0.5rem">'
        f'Top 10 switches — portefeuille complet'
        f'&nbsp;&nbsp;·&nbsp;&nbsp;{alg_note}</p>',
        unsafe_allow_html=True,
    )

    switches = propose_switches(
        portfolio,
        universe,
        n=10,
        green_only=green_flag,
        esg_boost=esg_flag,
    )

    if switches.empty:
        if green_flag and esg_flag:
            hint = "Aucun green bond avec amélioration ESG disponible dans la fenêtre de maturité."
        elif green_flag:
            hint = "Aucun green bond disponible avec un pickup de spread dans ce contexte."
        elif esg_flag:
            hint = "Tous les bonds comparables ont déjà un score ESG équivalent ou meilleur."
        else:
            hint = "Aucune proposition disponible : vérifiez que les bonds du portefeuille ont un Z-Sprd, une duration et un rating valides."
        st.info(hint)
        st.stop()

    # ── Rendu des cards — grille 2 colonnes ──────────────────────────
    N_COLS = 2
    for row_start in range(0, len(switches), N_COLS):
        batch = switches.iloc[row_start: row_start + N_COLS]
        cols  = st.columns(N_COLS)
        for col_idx, (_, sw) in enumerate(batch.iterrows()):
            with cols[col_idx]:
                st.markdown(
                    render_switch_card(sw, row_start + col_idx, badge_label, mode_accent, theme),
                    unsafe_allow_html=True,
                )
