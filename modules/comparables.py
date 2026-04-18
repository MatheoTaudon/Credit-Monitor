"""
pages/1_Comparables.py — Recherche de bonds comparables par KNN.

Flux :
1. Recherche par ISIN ou nom émetteur (text_input + selectbox)
2. Carte d'information du bond sélectionné
3. Options : nombre de comparables, axe Y, filtres
4. Tableau des comparables
5. Graphique : univers filtré (BICS Industry × Séniorité) + courbe NS
   + bond de référence + comparables mis en valeur
"""
import pandas as pd
import streamlit as st

from utils.knn import find_comparables
from utils.loader import load_data
from utils.style import COLORS, FONT, get_theme, inject_css
from utils.display import format_value, Y_LABELS, X_COL_MAP, render_bond_card
from utils.plots import build_comparables_chart


@st.dialog("Détails de l'obligation", width="large")
def _bond_detail_dialog(bond: pd.Series, theme: str) -> None:
    st.markdown(render_bond_card(bond, theme), unsafe_allow_html=True)
    _, col_close = st.columns([3, 1])
    with col_close:
        if st.button("Fermer", use_container_width=True, key="_bd_close_cmp"):
            st.session_state["_bd_ck_cmp"] += 1
            st.rerun()


def show() -> None:

    theme = get_theme()
    inject_css(theme)

    if "_bd_ck_cmp" not in st.session_state:
        st.session_state["_bd_ck_cmp"] = 0

    is_dark  = theme == "dark"
    text_col = COLORS["dark_text"]           if is_dark else COLORS["light_text"]
    text_sec = COLORS["dark_text_secondary"] if is_dark else COLORS["light_text_secondary"]
    surface  = COLORS["dark_surface"]        if is_dark else COLORS["light_surface"]
    border   = COLORS["dark_border"]         if is_dark else COLORS["light_border"]
    orange   = COLORS["bloomberg_orange"]

    # ── Header ────────────────────────────────────────────────────────
    col_title, col_nav = st.columns([5, 1])
    with col_title:
        st.markdown(
            f'<h2 style="color:{orange};font-family:{FONT};margin:0;font-weight:700;'
            f'letter-spacing:-0.3px;line-height:1.2">Trouver des Comparables</h2>'
            f'<p style="color:{text_sec};font-family:{FONT};margin:0.2rem 0 0 0;'
            f'font-size:0.88rem;font-weight:400">'
            f'KNN sur univers Bloomberg Euro Corporate Bond Index</p>',
            unsafe_allow_html=True,
        )
    with col_nav:
        st.markdown('<div style="padding-top:1.1rem">', unsafe_allow_html=True)
        def _to_accueil():
            st.session_state["page"] = "accueil"
        st.button("← Accueil", on_click=_to_accueil, use_container_width=True, key="nav_comp_accueil")
        st.markdown("</div>", unsafe_allow_html=True)

    st.divider()

    # ── Chargement des données ────────────────────────────────────────
    try:
        df = load_data()
    except FileNotFoundError as exc:
        st.error(str(exc))
        st.stop()
    except Exception as exc:
        st.error(f"Erreur inattendue lors du chargement : {exc}")
        st.stop()

    # ── Recherche ─────────────────────────────────────────────────────
    st.markdown(
        f'<p style="color:{text_col};font-family:{FONT};font-size:0.9rem;font-weight:600;'
        f'margin-bottom:0.3rem">Rechercher un bond</p>',
        unsafe_allow_html=True,
    )
    search_text = st.text_input(
        "Rechercher",
        placeholder="Ex : XS1234567890  ou  BNP PARIBAS  ou  AIRBUS",
        label_visibility="collapsed",
        key="comp_search",
    )

    selected_isin: str | None = None
    ref_bond: pd.Series | None = None

    if search_text and len(search_text.strip()) >= 2:
        query = search_text.strip()
        isin_mask   = df["ISIN"].str.upper() == query.upper()
        name_mask   = df["Short Name"].str.contains(query, case=False, na=False)
        ticker_mask = df["Ticker"].str.contains(query, case=False, na=False)
        all_matches = df[isin_mask | name_mask | ticker_mask].drop_duplicates("ISIN")
        matches = all_matches[["ISIN", "Ticker", "Bloomberg Composite Ratings", "BICS Industry", "Seniority"]].head(80)

        if matches.empty:
            st.warning(f"Aucun bond correspondant à « {query} ».")
        else:
            if len(all_matches) > 80:
                st.caption("Affichage limité à 80 résultats — affinez la recherche pour plus de précision.")

            options = {
                (
                    f"{row.get('Ticker', '—')}  ·  {row['ISIN']}  ·  "
                    f"{row.get('Bloomberg Composite Ratings', '')}  ·  {row.get('Seniority', '')}"
                ): row["ISIN"]
                for _, row in matches.iterrows()
            }
            selected_label = st.selectbox(
                f"{len(matches)} bond(s) trouvé(s)",
                list(options.keys()),
            )
            selected_isin = options[selected_label]
            ref_bond = df[df["ISIN"] == selected_isin].iloc[0]

    # ── Bond sélectionné — carte compacte ────────────────────────────
    if ref_bond is not None:
        r = ref_bond

        tenor_str = format_value(r.get("Tenor"),            "{:.1f} ans")
        zsprd_str = format_value(r.get("Z-Sprd"),           "{:.0f} bps")
        ytm_str   = format_value(r.get("YTM"),              "{:.2f}%")
        dur_str   = format_value(r.get("ModIfied Duration"), "{:.1f}")

        st.markdown(
            f"""
            <div style="background:{surface};border:1px solid {border};
                        border-left:4px solid {orange};border-radius:8px;
                        padding:0.9rem 1.2rem;margin:0.75rem 0 0.5rem 0">
                <p style="margin:0;font-family:{FONT};font-size:1.05rem;
                          font-weight:700;color:{text_col}">{r.get("Short Name","—")}</p>
                <p style="margin:0.25rem 0 0 0;font-family:{FONT};
                          font-size:0.82rem;color:{text_sec}">
                    {r.get("ISIN","—")} &nbsp;·&nbsp;
                    {r.get("Bloomberg Composite Ratings","N/A")} &nbsp;·&nbsp;
                    {r.get("BICS Industry","N/A")} &nbsp;·&nbsp;
                    {r.get("Seniority","N/A")} &nbsp;·&nbsp;
                    {r.get("Country","N/A")}
                </p>
                <div style="display:flex;gap:2.5rem;margin-top:0.6rem;flex-wrap:wrap">
                    <span style="font-family:{FONT};font-size:0.85rem;color:{text_sec}">
                        Tenor&nbsp;<b style="color:{text_col}">{tenor_str}</b></span>
                    <span style="font-family:{FONT};font-size:0.85rem;color:{text_sec}">
                        Z-Sprd&nbsp;<b style="color:{text_col}">{zsprd_str}</b></span>
                    <span style="font-family:{FONT};font-size:0.85rem;color:{text_sec}">
                        YTM&nbsp;<b style="color:{text_col}">{ytm_str}</b></span>
                    <span style="font-family:{FONT};font-size:0.85rem;color:{text_sec}">
                        Duration&nbsp;<b style="color:{text_col}">{dur_str}</b></span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Options + Contraintes ─────────────────────────────────────
        opt_col, cst_col = st.columns([1, 2])
        with opt_col:
            n_comp = st.number_input(
                "Nombre de comparables", min_value=1, max_value=20, value=5, step=1,
            )
        with cst_col:
            st.markdown(
                f'<p style="font-size:0.72rem;font-weight:700;color:{text_sec};'
                f'margin:0 0 0.35rem;font-family:{FONT};text-transform:uppercase;'
                f'letter-spacing:0.07em;border-left:2px solid {orange};padding-left:7px">'
                f'Contraintes</p>',
                unsafe_allow_html=True,
            )
            c1, c2, c3 = st.columns(3)
            with c1:
                exclude_issuer = st.checkbox("Exclure même émetteur", key="comp_excl")
            with c2:
                green_only = st.checkbox("Green uniquement", key="comp_green")
            with c3:
                esg_boost = st.checkbox("Meilleur ESG score", key="comp_esg")

        st.divider()

        # ── Prérequis : BICS Industry obligatoire ─────────────────────
        ref_bics = ref_bond.get("BICS Industry")
        if pd.isna(ref_bics) or str(ref_bics).strip() == "":
            st.warning(
                "Le modèle KNN requiert un **BICS Industry** renseigné. "
                "Ce bond n'en possède pas — impossible de calculer les comparables."
            )
            st.stop()

        # ── KNN ───────────────────────────────────────────────────────
        _, comparables_df = find_comparables(
            df,
            selected_isin,
            k=int(n_comp),
            exclude_same_issuer=exclude_issuer,
            green_only=green_only,
            esg_boost=esg_boost,
        )

        if comparables_df.empty:
            st.info("Aucun comparable trouvé avec les critères sélectionnés.")
            st.stop()

        # ── Tableau ───────────────────────────────────────────────────
        DISPLAY_COLS = [
            "Short Name", "ISIN", "Bloomberg Composite Ratings",
            "BICS Industry", "Seniority", "Country",
            "Tenor", "Z-Sprd", "YTM", "G-Spread", "ModIfied Duration",
        ]
        table_df = comparables_df[
            [c for c in DISPLAY_COLS if c in comparables_df.columns]
        ].copy()

        st.markdown(
            f'<p style="font-family:{FONT};font-size:0.9rem;font-weight:600;'
            f'color:{text_col};margin-bottom:0.4rem">'
            f'{len(table_df)} comparable(s) — trié(s) par proximité KNN</p>',
            unsafe_allow_html=True,
        )

        col_config = {
            "Short Name":                  st.column_config.TextColumn("Émetteur",     width="medium"),
            "ISIN":                        st.column_config.TextColumn("ISIN",         width="medium"),
            "Bloomberg Composite Ratings": st.column_config.TextColumn("Notation",     width="small"),
            "BICS Industry":               st.column_config.TextColumn("Secteur BICS", width="small"),
            "Seniority":                   st.column_config.TextColumn("Séniorité",    width="medium"),
            "Country":                     st.column_config.TextColumn("Pays",         width="small"),
            "Tenor":                       st.column_config.NumberColumn("Tenor (ans)", format="%.1f"),
            "Z-Sprd":                      st.column_config.NumberColumn("Z-Sprd (bps)", format="%.0f"),
            "YTM":                         st.column_config.NumberColumn("YTM (%)",    format="%.2f"),
            "G-Spread":                    st.column_config.NumberColumn("G-Sprd (bps)", format="%.0f"),
            "ModIfied Duration":           st.column_config.NumberColumn("Duration",   format="%.1f"),
        }
        st.dataframe(
            table_df,
            column_config={col: cfg for col, cfg in col_config.items() if col in table_df.columns},
            use_container_width=True,
            hide_index=True,
        )

        st.divider()

        # ── Graphique ─────────────────────────────────────────────────
        ref_bics      = ref_bond.get("BICS Industry")
        ref_seniority = ref_bond.get("Seniority")

        g_label_col, g_y_col, g_x_col = st.columns([3, 1, 1])
        with g_label_col:
            filter_label = (
                f"{ref_bics} · {ref_seniority}"
                if pd.notna(ref_bics) and pd.notna(ref_seniority)
                else "Univers filtré"
            )
            st.markdown(
                f'<p style="font-size:0.88rem;font-weight:600;color:{text_col};'
                f'font-family:{FONT};margin:0;padding-top:0.4rem">'
                f'Courbe — {filter_label}</p>',
                unsafe_allow_html=True,
            )
        with g_y_col:
            y_col = st.selectbox(
                "Axe Y", ["Z-Sprd", "YTM", "G-Spread"],
                key="comp_y_col", label_visibility="collapsed",
            )
        with g_x_col:
            x_choice = st.selectbox(
                "Axe X", ["Maturité to Call", "Maturité"],
                key="comp_x_col", label_visibility="collapsed",
            )
        x_col = X_COL_MAP[x_choice]

        # Contexte : même BICS Industry + même Séniorité
        df_context = df.copy()
        if pd.notna(ref_bics):
            df_context = df_context[df_context["BICS Industry"] == ref_bics]
        if pd.notna(ref_seniority):
            df_context = df_context[df_context["Seniority"] == ref_seniority]

        df_plot = df_context.dropna(subset=[x_col, y_col]).reset_index(drop=True)

        fig = build_comparables_chart(
            df_plot, x_col, y_col, x_choice, theme,
            ref_bond=ref_bond,
            comparables_df=comparables_df,
            height=530,
        )
        event = st.plotly_chart(fig, on_select="rerun", key=f"chart_cmp_{st.session_state['_bd_ck_cmp']}", use_container_width=True)

        if event.selection.points:
            cd = event.selection.points[0].get("customdata") or []
            if len(cd) > 1:
                matches = df[df["ISIN"] == cd[1]]
                if not matches.empty:
                    _bond_detail_dialog(matches.iloc[0], theme)
