"""
pages/3_Screener.py — Filtrage interactif de l'univers obligataire.

Layout :
  Top   : filtres catégoriels rapides (5 multiselects + reset)
  Milieu: filtres numériques (colonne gauche 25%) + graphique NS (colonne droite 75%)
  Bas   : recherche + tableau sélectionnable (pleine largeur) + fiche détail
"""
import pandas as pd
import streamlit as st

from utils.loader import load_data
from utils.style import COLORS, FONT, get_theme, inject_css
from utils.display import (
    format_value,
    safe_range,
    sorted_ratings,
    render_badge,
    render_bond_card,
    Y_LABELS,
    X_COL_MAP,
    RATING_ORDER,
)
from utils.plots import build_sector_chart


@st.dialog("Détails de l'obligation", width="large")
def _bond_detail_dialog(bond: pd.Series, theme: str) -> None:
    st.markdown(render_bond_card(bond, theme), unsafe_allow_html=True)
    _, col_close = st.columns([3, 1])
    with col_close:
        if st.button("Fermer", use_container_width=True, key="_bd_close_flt"):
            st.session_state["_bd_ck_flt"] += 1
            st.rerun()


def show() -> None:

    theme = get_theme()
    inject_css(theme)

    is_dark  = theme == "dark"
    text_col = COLORS["dark_text"]           if is_dark else COLORS["light_text"]
    text_sec = COLORS["dark_text_secondary"] if is_dark else COLORS["light_text_secondary"]
    orange   = COLORS["bloomberg_orange"]

    TABLE_COLS = [
        "Short Name", "ISIN", "Bloomberg Composite Ratings",
        "BICS Industry", "Seniority", "Country",
        "Tenor", "Z-Sprd", "YTM", "ModIfied Duration",
        "Green Bond", "Callable",
    ]

    TABLE_CONFIG = {
        "Short Name":                  st.column_config.TextColumn("Émetteur",      width="medium"),
        "ISIN":                        st.column_config.TextColumn("ISIN",          width="medium"),
        "Bloomberg Composite Ratings": st.column_config.TextColumn("Notation",      width="small"),
        "BICS Industry":               st.column_config.TextColumn("Industrie",     width="small"),
        "Seniority":                   st.column_config.TextColumn("Séniorité",     width="medium"),
        "Country":                     st.column_config.TextColumn("Pays",          width="small"),
        "Tenor":                       st.column_config.NumberColumn("Tenor (ans)", format="%.1f"),
        "Z-Sprd":                      st.column_config.NumberColumn("Z-Sprd",      format="%.0f"),
        "YTM":                         st.column_config.NumberColumn("YTM (%)",     format="%.2f"),
        "ModIfied Duration":           st.column_config.NumberColumn("Duration",    format="%.1f"),
        "Green Bond":                  st.column_config.TextColumn("Green",         width="small"),
        "Callable":                    st.column_config.TextColumn("Callable",      width="small"),
    }

    # ── Reset counter ─────────────────────────────────────────────────
    if "scr_reset_n" not in st.session_state:
        st.session_state["scr_reset_n"] = 0
    if "_bd_ck_flt" not in st.session_state:
        st.session_state["_bd_ck_flt"] = 0

    n = st.session_state["scr_reset_n"]

    # ── Helpers locaux ────────────────────────────────────────────────

    def _reset_filters() -> None:
        to_del = [k for k in st.session_state if k.startswith("scr_") and k != "scr_reset_n"]
        for k in to_del:
            del st.session_state[k]
        st.session_state["scr_reset_n"] += 1

    def _sec_label(text: str) -> None:
        """Label de section dans le panneau gauche — filet orange à gauche."""
        st.markdown(
            f'<p style="font-family:{FONT};font-size:0.72rem;font-weight:700;'
            f'color:{text_sec};margin:1.1rem 0 0.2rem;text-transform:uppercase;'
            f'letter-spacing:0.07em;border-left:2px solid {orange};'
            f'padding-left:7px">{text}</p>',
            unsafe_allow_html=True,
        )

    # ══════════════════════════════════════════════════════════════════
    # HEADER
    # ══════════════════════════════════════════════════════════════════
    col_h, col_nav = st.columns([5, 1])
    with col_h:
        st.markdown(
            f'<h2 style="color:{orange};font-family:{FONT};margin:0;font-weight:700;'
            f'letter-spacing:-0.3px;line-height:1.2">Filtrer l\'Univers</h2>'
            f'<p style="color:{text_sec};font-family:{FONT};margin:0.2rem 0 0;'
            f'font-size:0.88rem">Screener Bloomberg Euro Corporate Bond Index</p>',
            unsafe_allow_html=True,
        )
    with col_nav:
        st.markdown('<div style="padding-top:1.1rem">', unsafe_allow_html=True)
        def _to_accueil():
            st.session_state["page"] = "accueil"
        st.button("← Accueil", on_click=_to_accueil, use_container_width=True, key="nav_scr_accueil")
        st.markdown("</div>", unsafe_allow_html=True)

    st.divider()

    # ── Données ───────────────────────────────────────────────────────
    try:
        df = load_data()
    except FileNotFoundError as exc:
        st.error(str(exc))
        st.stop()
    except Exception as exc:
        st.error(f"Erreur inattendue : {exc}")
        st.stop()

    N_TOTAL = len(df)

    # Pré-calcul des plages (depuis l'univers complet)
    z_min, z_max = safe_range(df["Z-Sprd"],            decimals=0)
    y_min, y_max = safe_range(df["YTM"],               decimals=2)
    g_min, g_max = safe_range(df["G-Spread"],          decimals=0)
    d_min, d_max = safe_range(df["ModIfied Duration"], decimals=1)
    t_min, t_max = safe_range(df["Tenor"].dropna(),    decimals=1)
    c_min, c_max = safe_range(df["Coupon"],            decimals=2)

    amt_series = df["Amount Outstanding"].dropna() / 1e6
    a_min = float(round(amt_series.min(), 0)) if not amt_series.empty else 0.0
    a_max = float(round(amt_series.max(), 0)) if not amt_series.empty else 5000.0

    esg_min, esg_max = safe_range(df["ESG Score"], decimals=1)
    _esg_df = df[df["ESG Score"].notna() & df["Poids"].notna()].copy()
    index_esg: float | None = (
        float((_esg_df["ESG Score"] * _esg_df["Poids"]).sum() / _esg_df["Poids"].sum())
        if not _esg_df.empty and _esg_df["Poids"].sum() > 0
        else None
    )

    # ══════════════════════════════════════════════════════════════════
    # TOP BAR — Filtres catégoriels
    # ══════════════════════════════════════════════════════════════════
    t1, t2, t3, t4, t5, t6, t7 = st.columns(7)

    with t1:
        f_sectors = st.multiselect(
            "Secteur GICS",
            sorted(df["GICS Sector"].dropna().unique()),
            key=f"scr_sectors_{n}", placeholder="Tous",
        )
    with t2:
        f_seniorities = st.multiselect(
            "Séniorité",
            sorted(df["Seniority"].dropna().unique()),
            key=f"scr_seniorities_{n}", placeholder="Toutes",
        )
    with t3:
        f_countries = st.multiselect(
            "Pays",
            sorted(df["Country"].dropna().unique()),
            key=f"scr_countries_{n}", placeholder="Tous",
        )
    with t4:
        f_ratings = st.multiselect(
            "Notation",
            sorted_ratings(df["Bloomberg Composite Ratings"].dropna().unique().tolist()),
            key=f"scr_ratings_{n}", placeholder="Toutes",
        )
    with t5:
        f_industries = st.multiselect(
            "Industrie BICS",
            sorted(df["BICS Industry"].dropna().unique()),
            key=f"scr_industries_{n}", placeholder="Tous",
        )
    with t6:
        all_ctypes_top = sorted(df["Coupn Type"].dropna().unique()) if "Coupn Type" in df.columns else []
        f_ctypes = st.multiselect(
            "Type coupon",
            all_ctypes_top,
            key=f"scr_ctypes_{n}", placeholder="Tous",
        )
    with t7:
        f_issuers = st.multiselect(
            "Émetteur",
            sorted(df["Short Name"].dropna().unique()),
            key=f"scr_issuers_{n}", placeholder="Tous",
        )

    st.divider()

    # ══════════════════════════════════════════════════════════════════
    # PANNEAU GAUCHE — Filtres numériques
    # ══════════════════════════════════════════════════════════════════
    col_left, col_right = st.columns([1, 3])

    with col_left:
        _sec_label("Spreads & Rendement")
        f_zsprd    = st.slider("Z-Spread (bps)", z_min, z_max, (z_min, z_max), step=1.0,  key=f"scr_zsprd_{n}")
        f_ytm      = st.slider("YTM (%)",        y_min, y_max, (y_min, y_max), step=0.01, key=f"scr_ytm_{n}")

        _sec_label("Sensibilité & Maturité")
        f_duration = st.slider("Duration",       d_min, d_max, (d_min, d_max), step=0.1,  key=f"scr_duration_{n}")
        f_tenor    = st.slider("Tenor (ans)",    t_min, t_max, (t_min, t_max), step=0.1,  key=f"scr_tenor_{n}")

        _sec_label("ESG")
        f_green = st.checkbox("Green Bond seulement", key=f"scr_green_{n}")
        if esg_min < esg_max:
            f_esg = st.slider("ESG Score", esg_min, esg_max, (esg_min, esg_max), step=0.1, key=f"scr_esg_{n}")
            if index_esg is not None:
                _pct = max(0.0, min(100.0, (index_esg - esg_min) / (esg_max - esg_min) * 100))
                st.markdown(
                    f'<div style="margin:-4px 0 8px;position:relative;height:14px;width:100%">'
                    f'<div style="position:absolute;left:{_pct:.1f}%;top:0;height:100%;'
                    f'width:2px;background:{orange};border-radius:1px"></div>'
                    f'<span style="position:absolute;left:calc({_pct:.1f}% + 4px);top:50%;'
                    f'transform:translateY(-50%);font-size:0.6rem;'
                    f'color:{orange};white-space:nowrap;font-family:{FONT}">'
                    f'Indice&nbsp;{index_esg:.1f}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            f_esg = (esg_min, esg_max)

        with st.expander("Caractéristiques d'émission"):
            f_coupon = st.slider("Coupon (%)",   c_min, c_max, (c_min, c_max), step=0.01, key=f"scr_coupon_{n}")
            f_amount = st.slider("Encours (M€)", a_min, a_max, (a_min, a_max), step=50.0, key=f"scr_amount_{n}")

    # ── Appliquer les filtres ─────────────────────────────────────────
    r = df.copy()

    if f_sectors:     r = r[r["GICS Sector"].isin(f_sectors)]
    if f_industries:  r = r[r["BICS Industry"].isin(f_industries)]
    if f_seniorities: r = r[r["Seniority"].isin(f_seniorities)]
    if f_countries:   r = r[r["Country"].isin(f_countries)]
    if f_ratings:     r = r[r["Bloomberg Composite Ratings"].isin(f_ratings)]
    if f_ctypes and "Coupn Type" in r.columns:
        r = r[r["Coupn Type"].isin(f_ctypes)]

    if f_zsprd    != (z_min, z_max): r = r[r["Z-Sprd"].between(f_zsprd[0], f_zsprd[1])]
    if f_ytm      != (y_min, y_max): r = r[r["YTM"].between(f_ytm[0], f_ytm[1])]
    if f_duration != (d_min, d_max): r = r[r["ModIfied Duration"].between(f_duration[0], f_duration[1])]
    if f_tenor    != (t_min, t_max): r = r[r["Tenor"].between(f_tenor[0], f_tenor[1])]
    if f_coupon   != (c_min, c_max): r = r[r["Coupon"].between(f_coupon[0], f_coupon[1])]
    if f_amount   != (a_min, a_max):
        r = r[
            r["Amount Outstanding"].isna() |
            (r["Amount Outstanding"] / 1e6).between(f_amount[0], f_amount[1])
        ]

    if f_issuers:      r = r[r["Short Name"].isin(f_issuers)]
    if f_green:        r = r[r["Green Bond"] == "Y"]
    if f_esg != (esg_min, esg_max) and esg_min < esg_max:
        r = r[r["ESG Score"].between(f_esg[0], f_esg[1])]

    df_filtered = r.reset_index(drop=True)
    n_filtered  = len(df_filtered)

    active = sum([
        bool(f_sectors), bool(f_industries), bool(f_seniorities), bool(f_countries),
        bool(f_ratings),  bool(f_ctypes),
        f_zsprd    != (z_min, z_max), f_ytm  != (y_min, y_max),
        f_duration != (d_min, d_max),
        f_tenor    != (t_min, t_max), f_coupon   != (c_min, c_max),
        f_amount   != (a_min, a_max), f_green,    bool(f_issuers),
        f_esg != (esg_min, esg_max) if esg_min < esg_max else False,
    ])
    count_color = orange if n_filtered < N_TOTAL else text_sec
    filter_info = f" · {active} filtre(s) actif(s)" if active else ""

    # ══════════════════════════════════════════════════════════════════
    # PANNEAU DROIT — Graphique
    # ══════════════════════════════════════════════════════════════════
    with col_right:
        if df_filtered.empty:
            st.warning("Aucun bond ne correspond aux filtres. Élargissez les critères.")
        else:
            g_info, g_y_sel, g_x_sel = st.columns([3, 1, 1])
            with g_info:
                st.markdown(
                    f'<p style="color:{text_sec};font-size:0.85rem;font-family:{FONT};'
                    f'padding-top:0.4rem;margin:0">'
                    f'<b style="color:{count_color}">{n_filtered}</b>'
                    f' obligation(s) sur {N_TOTAL}{filter_info}</p>',
                    unsafe_allow_html=True,
                )
            with g_y_sel:
                y_col = st.selectbox(
                    "Axe Y", ["Z-Sprd", "YTM", "G-Spread"],
                    key=f"scr_y_{n}", label_visibility="collapsed",
                )
            with g_x_sel:
                x_choice = st.selectbox(
                    "Axe X", ["Maturité to Call", "Maturité"],
                    key=f"scr_x_{n}", label_visibility="collapsed",
                )
            x_col = X_COL_MAP[x_choice]

            df_graph = df_filtered.dropna(subset=[x_col, y_col]).reset_index(drop=True)

            fig = build_sector_chart(
                df_graph, x_col, y_col, x_choice, theme,
                height=700,
                margin={"l": 40, "r": 10, "t": 10, "b": 110},
                legend_y=-0.12,
            )
            event = st.plotly_chart(fig, on_select="rerun", key=f"chart_flt_{st.session_state['_bd_ck_flt']}", use_container_width=True)

            if event.selection.points:
                cd = event.selection.points[0].get("customdata") or []
                if len(cd) > 1:
                    matches = df_graph[df_graph["ISIN"] == cd[1]]
                    if not matches.empty:
                        _bond_detail_dialog(matches.iloc[0], theme)

    if df_filtered.empty:
        st.stop()

    st.divider()

    # ══════════════════════════════════════════════════════════════════
    # TABLEAU — pleine largeur
    # ══════════════════════════════════════════════════════════════════
    c_search, c_count = st.columns([4, 1])
    with c_search:
        search_q = st.text_input(
            "Recherche",
            placeholder="ISIN, émetteur, ticker…",
            label_visibility="collapsed",
            key=f"scr_search_{n}",
        )
    with c_count:
        st.markdown(
            f'<p style="color:{count_color};font-size:0.85rem;font-family:{FONT};'
            f'padding-top:0.55rem;text-align:right;font-weight:600">'
            f'{n_filtered} / {N_TOTAL}</p>',
            unsafe_allow_html=True,
        )

    if search_q and len(search_q.strip()) >= 2:
        q = search_q.strip()
        m = (
            df_filtered["ISIN"].str.contains(q, case=False, na=False) |
            df_filtered["Short Name"].str.contains(q, case=False, na=False) |
            df_filtered["Ticker"].str.contains(q, case=False, na=False)
        )
        df_displayed = df_filtered[m].reset_index(drop=True)
        if df_displayed.empty:
            st.caption(f"Aucun résultat pour « {q} » dans l'univers filtré.")
            df_displayed = df_filtered
    else:
        df_displayed = df_filtered

    table_df = df_displayed[
        [c for c in TABLE_COLS if c in df_displayed.columns]
    ].copy()

    st.dataframe(
        table_df,
        column_config={k: v for k, v in TABLE_CONFIG.items() if k in table_df.columns},
        use_container_width=True,
        hide_index=True,
        height=350,
        key=f"scr_table_{n}",
    )
