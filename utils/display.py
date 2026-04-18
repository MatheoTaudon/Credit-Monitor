"""
utils/display.py — Constantes partagées, formateurs et générateurs HTML.

API publique :
- Y_LABELS         : dict  labels axe Y (partagé entre tous les modules)
- X_COL_MAP        : dict  mapping choix UI → nom colonne
- RATING_ORDER     : list  ordre canonique des notations
- format_value     : formateur valeur numérique (remplace _fmt/_fv dans tous modules)
- safe_range       : calcul plage min/max sûre pour sliders Streamlit
- sorted_ratings   : tri des notations selon RATING_ORDER
- render_badge     : HTML badge inline coloré
- render_bond_card : HTML fiche détail complète d'un bond (remplace filtres._detail_card)
- render_switch_card : HTML card proposition de switch (remplace sales_monitor._switch_card)

Règles :
- Zéro import Streamlit — toutes les fonctions sont pures
- Les générateurs HTML retournent str, jamais None
"""
import math

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────────────
# Constantes partagées
# ─────────────────────────────────────────────────────────────────

Y_LABELS: dict[str, str] = {
    "Z-Sprd":    "Z-Spread (bps)",
    "YTM":       "YTM (%)",
    "G-Spread":  "G-Spread (bps)",
}

X_COL_MAP: dict[str, str] = {
    "Maturité":           "Tenor",
    "Maturité to Call":   "Tenor to Call",
}

RATING_ORDER: list[str] = [
    "AAA", "AA+", "AA", "AA-",
    "A+", "A", "A-",
    "BBB+", "BBB", "BBB-",
    "BB+", "BB", "BB-",
    "B+", "B", "B-",
    "CCC+", "CCC", "CC", "C", "D", "NR",
]


# ─────────────────────────────────────────────────────────────────
# Formateur valeur numérique
# ─────────────────────────────────────────────────────────────────

def format_value(val, fmt: str, fallback: str = "N/A") -> str:
    """Formate val selon fmt ; retourne fallback si val est None/NaN/non-numérique.

    Args:
        val      : Valeur à formater (int, float, ou toute valeur convertible).
        fmt      : Format Python, ex: "{:.2f}", "{:.0f} bps", "{:.3f}%".
        fallback : Valeur retournée si val est invalide (défaut "N/A").

    Returns:
        Chaîne formatée ou fallback.
    """
    try:
        fv = float(val)
        if math.isnan(fv) or math.isinf(fv):
            return fallback
        return fmt.format(fv)
    except (TypeError, ValueError):
        return fallback


# ─────────────────────────────────────────────────────────────────
# Helpers de filtres
# ─────────────────────────────────────────────────────────────────

def safe_range(series: pd.Series, decimals: int = 1) -> tuple[float, float]:
    """Calcule min/max sûrs pour un slider Streamlit.

    Si la série est vide ou constante, retourne des bornes distinctes.

    Args:
        series   : Série pandas (valeurs numériques).
        decimals : Nombre de décimales pour arrondir.

    Returns:
        (lo, hi) avec lo < hi garanti.
    """
    valid = series.dropna()
    if valid.empty:
        return 0.0, 1.0
    lo = float(round(valid.min(), decimals))
    hi = float(round(valid.max(), decimals))
    if lo == hi:
        lo -= 1.0
        hi += 1.0
    return lo, hi


def sorted_ratings(available: list[str]) -> list[str]:
    """Trie les notations disponibles selon RATING_ORDER canonique.

    Les notations non présentes dans RATING_ORDER sont placées en fin, triées alphabétiquement.

    Args:
        available : Liste de notations présentes dans les données.

    Returns:
        Liste triée.
    """
    ordered = [r for r in RATING_ORDER if r in available]
    others  = [r for r in available if r not in RATING_ORDER]
    return ordered + sorted(others)


# ─────────────────────────────────────────────────────────────────
# Générateurs HTML — retournent str, jamais None
# ─────────────────────────────────────────────────────────────────

def render_badge(label: str, color: str, text_color: str = "#000") -> str:
    """Badge HTML inline coloré.

    Args:
        label      : Texte du badge.
        color      : Couleur de fond (hex ou CSS).
        text_color : Couleur du texte (défaut noir).

    Returns:
        Chaîne HTML span.
    """
    return (
        f'<span style="background:{color};color:{text_color};padding:2px 8px;'
        f'border-radius:4px;font-size:0.72rem;font-weight:700;'
        f'letter-spacing:0.04em;margin-left:6px">{label}</span>'
    )


def render_bond_card(bond: pd.Series, theme: str) -> str:
    from utils.style import COLORS, FONT

    is_dark  = theme == "dark"
    text_col = COLORS["dark_text"]           if is_dark else COLORS["light_text"]
    text_sec = COLORS["dark_text_secondary"] if is_dark else COLORS["light_text_secondary"]
    surface  = COLORS["dark_surface"]        if is_dark else COLORS["light_surface"]
    border   = COLORS["dark_border"]         if is_dark else COLORS["light_border"]
    orange   = COLORS["bloomberg_orange"]

    def _row(lbl: str, val: str) -> str:
        # RÉDUCTION DU PADDING : de 16px à 6px pour gagner de la place en largeur
        # Taille de police très légèrement ajustée
        return (
            f'<tr>'
            f'<td style="color:{text_sec};padding:2px 6px 2px 0;font-size:0.8rem;'
            f'white-space:nowrap;font-family:{FONT}">{lbl}</td>'
            f'<td style="color:{text_col};font-weight:600;font-size:0.8rem;'
            f'white-space:nowrap;font-family:{FONT}">{val}</td>'
            f'</tr>'
        )

    b       = bond
    rating  = b.get("Bloomberg Composite Ratings", "N/A")
    green   = b.get("Green Bond", "N")
    green_b = render_badge("GREEN", COLORS["positive"]) if green == "Y" else ""
    call    = b.get("Callable", "N")
    call_b  = render_badge("CALLABLE", text_sec, text_col) if call == "Y" else ""

    amount_raw   = b.get("Amount Outstanding")
    amount_str   = f"{float(amount_raw) / 1e6:.0f} M€" if pd.notna(amount_raw) else "N/A"
    coupon_type  = b.get("Coupn Type")
    coupon_str   = f"{format_value(b.get('Coupon'), '{:.3f}%')} ({'N/A' if pd.isna(coupon_type) else coupon_type})"
    next_call    = b.get("Next Call Date")
    next_call_str = "—" if pd.isna(next_call) else str(next_call)
    maturity     = b.get("Maturity Date")
    maturity_str = "—" if pd.isna(maturity) else str(maturity)

    market = "".join([
        _row("Z-Spread", format_value(b.get("Z-Sprd"),           "{:.0f} bps")),
        _row("YTM",      format_value(b.get("YTM"),               "{:.2f}%")),
        _row("G-Spread", format_value(b.get("G-Spread"),          "{:.0f} bps")),
        _row("Duration", format_value(b.get("ModIfied Duration"), "{:.2f}")),
        _row("Tenor",    format_value(b.get("Tenor"),             "{:.1f} ans")),
    ])
    
    issue = "".join([
        _row("Coupon",    coupon_str),
        _row("Encours",   amount_str),
        _row("Seniorité", str(b.get("Seniority", "N/A"))), # <-- Remplacement effectué ici
        _row("Next Call", next_call_str),
        _row("Maturité",  maturity_str),
    ])

    esg_score = format_value(b.get("ESG Score"), "{:.1f}")
    msci      = b.get("MSCI ESG Rating", "N/A")
    esg_color = COLORS["positive"] if green == "Y" else text_sec

    # RÉDUCTION DU GAP : de 1.5rem à 0.5rem entre les deux tableaux
    # RÉDUCTION DU PADDING GLOBAL : de 1.2rem à 0.8rem
    html = (
        f'<div style="background:{surface};border:1px solid {border};border-left:4px solid {orange};border-radius:10px;padding:0.8rem 1rem;margin-top:0.5rem">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start">'
        f'<div>'
        f'<p style="margin:0;color:{text_col};font-size:1.1rem;font-weight:700;font-family:{FONT}">{b.get("Short Name","—")}</p>'
        f'<p style="margin:0.2rem 0 0;color:{text_sec};font-size:0.8rem;font-family:{FONT}">{b.get("ISIN","—")} &nbsp;·&nbsp; {b.get("Ticker","—")}</p>'
        f'<p style="margin:0.1rem 0 0;color:{text_sec};font-size:0.8rem;font-family:{FONT}">{b.get("Country","N/A")} &nbsp;·&nbsp; {b.get("BICS Industry","N/A")}</p>'
        f'</div>'
        f'<div style="text-align:right;flex-shrink:0;padding-left:0.5rem">'
        f'<span style="font-size:1.3rem;font-weight:700;color:{orange};font-family:{FONT}">{rating}</span><br>'
        f'{green_b}{call_b}'
        f'</div>'
        f'</div>'
        f'<hr style="border:none;border-top:1px solid {border};margin:0.6rem 0">'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem">' # <-- Les 2 colonnes maintenues, mais rapprochées
        f'<div>'
        f'<p style="color:{text_sec};font-size:0.72rem;font-weight:600;margin:0 0 0.2rem;text-transform:uppercase;letter-spacing:0.06em;font-family:{FONT}">Marché</p>'
        f'<table style="border-collapse:collapse; width:100%">{market}</table>'
        f'</div>'
        f'<div>'
        f'<p style="color:{text_sec};font-size:0.72rem;font-weight:600;margin:0 0 0.2rem;text-transform:uppercase;letter-spacing:0.06em;font-family:{FONT}">Émission</p>'
        f'<table style="border-collapse:collapse; width:100%">{issue}</table>'
        f'</div>'
        f'</div>'
        f'<p style="color:{text_sec};font-size:0.75rem;margin:0.6rem 0 0;border-top:1px solid {border};padding-top:0.4rem;font-family:{FONT}">'
        f'ESG Score &nbsp;<b style="color:{text_col}">{esg_score}</b> &nbsp;·&nbsp; '
        f'MSCI ESG &nbsp;<b style="color:{text_col}">{msci}</b>'
        f'</p>'
        f'</div>'
    )
    return html


def render_switch_card(
    switch: pd.Series,
    idx: int,
    badge_label: str,
    mode_accent: str,
    theme: str,
) -> str:
    """Génère la card HTML d'une proposition de switch.

    Args:
        switch      : Series pandas avec les données du switch.
        idx         : Index 0-based pour le rang affiché (#1, #2, ...).
        badge_label : Texte du badge (ex: "SWITCH", "ESG+", "GREEN BOND").
        mode_accent : Couleur de la bordure et du badge.
        theme       : "dark" ou "light".

    Returns:
        Chaîne HTML prête pour st.markdown(..., unsafe_allow_html=True).
    """
    from utils.style import COLORS, FONT

    is_dark  = theme == "dark"
    text_col = COLORS["dark_text"]           if is_dark else COLORS["light_text"]
    text_sec = COLORS["dark_text_secondary"] if is_dark else COLORS["light_text_secondary"]
    surface  = COLORS["dark_surface"]        if is_dark else COLORS["light_surface"]
    border   = COLORS["dark_border"]         if is_dark else COLORS["light_border"]
    orange   = COLORS["bloomberg_orange"]
    green_c  = COLORS["positive"]
    red_c    = COLORS["negative"]

    sw = switch

    # ── Helpers internes (non exportés) ───────────────────────────

    def _delta_html(v, fmt: str, good_positive: bool = True) -> str:
        try:
            fv = float(v)
            if np.isnan(fv):
                return f'<span style="color:{text_sec}">—</span>'
        except (TypeError, ValueError):
            return f'<span style="color:{text_sec}">—</span>'
        is_good = (fv > 0 and good_positive) or (fv < 0 and not good_positive)
        color = (
            green_c if (is_good and fv != 0)
            else (red_c if (not is_good and fv != 0) else text_sec)
        )
        return (
            f'<span style="color:{color};font-weight:700;font-size:0.63rem">'
            f'{fmt.format(fv)}</span>'
        )

    def _bond_col(
        side: str, ticker, name, rating, seniority, country, extra: str = ""
    ) -> str:
        return (
            f'<div>'
            f'<p style="margin:0;font-size:0.59rem;color:{text_sec};font-family:{FONT};'
            f'font-weight:700;text-transform:uppercase;letter-spacing:0.06em">'
            f'{side}{extra}</p>'
            f'<p style="margin:0.1rem 0 0;font-size:0.9rem;font-weight:700;'
            f'color:{text_col};font-family:{FONT};line-height:1.15">'
            f'{ticker or "—"}</p>'
            f'<p style="margin:0;font-size:0.66rem;color:{text_sec};font-family:{FONT};'
            f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:180px">'
            f'{name or "—"}</p>'
            f'<p style="margin:0.1rem 0 0;font-size:0.62rem;color:{text_sec};'
            f'font-family:{FONT}">'
            f'{rating}&nbsp;·&nbsp;{seniority}&nbsp;·&nbsp;{country or "—"}</p>'
            f'</div>'
        )

    def _row(label: str, from_v: str, to_v: str, dhtml: str) -> str:
        return (
            f'<tr>'
            f'<td style="font-size:0.63rem;color:{text_sec};font-family:{FONT};'
            f'padding:2px 0;white-space:nowrap">{label}</td>'
            f'<td style="font-size:0.63rem;color:{text_col};font-weight:600;'
            f'font-family:{FONT};text-align:right;padding:2px 8px">{from_v}</td>'
            f'<td style="font-size:0.68rem;color:{text_sec};padding:2px 5px;'
            f'text-align:center">→</td>'
            f'<td style="font-size:0.63rem;color:{text_col};font-weight:600;'
            f'font-family:{FONT};padding:2px 8px">{to_v}</td>'
            f'<td style="padding:2px 0">{dhtml}</td>'
            f'</tr>'
        )

    def _row_text(label: str, from_v: str, to_v: str) -> str:
        return (
            f'<tr>'
            f'<td style="font-size:0.63rem;color:{text_sec};font-family:{FONT};'
            f'padding:2px 0;white-space:nowrap">{label}</td>'
            f'<td style="font-size:0.63rem;color:{text_col};font-weight:600;'
            f'font-family:{FONT};text-align:right;padding:2px 8px">{from_v or "—"}</td>'
            f'<td style="font-size:0.68rem;color:{text_sec};padding:2px 5px;'
            f'text-align:center">→</td>'
            f'<td style="font-size:0.63rem;color:{text_col};font-weight:600;'
            f'font-family:{FONT};padding:2px 8px">{to_v or "—"}</td>'
            f'<td style="padding:2px 0"></td>'
            f'</tr>'
        )

    # ── Calculs ───────────────────────────────────────────────────

    weight_raw = sw.get("from_weight")
    try:
        weight_pct = float(weight_raw) * 100
    except (TypeError, ValueError):
        weight_pct = None
    weight_str = format_value(weight_pct, "{:.2f}%", fallback="—")

    to_green_badge = (
        f'&nbsp;<span style="background:{green_c};color:#000;padding:1px 5px;'
        f'border-radius:3px;font-size:0.57rem;font-weight:700;'
        f'vertical-align:middle">GREEN</span>'
        if str(sw.get("to_green", "N")) == "Y" else ""
    )

    # Duration delta : neutre (gris, ni bon ni mauvais)
    dur_delta = sw.get("delta_duration")
    try:
        dur_fv = float(dur_delta)
        if not np.isnan(dur_fv):
            sign = "+" if dur_fv > 0 else ""
            dur_dhtml = (
                f'<span style="color:{text_sec};font-weight:700;font-size:0.63rem">'
                f'{sign}{dur_fv:.2f}</span>'
            )
        else:
            dur_dhtml = f'<span style="color:{text_sec}">—</span>'
    except (TypeError, ValueError):
        dur_dhtml = f'<span style="color:{text_sec}">—</span>'

    callable_from = "Oui" if str(sw.get("from_callable", "N")) == "Y" else "Non"
    callable_to   = "Oui" if str(sw.get("to_callable",   "N")) == "Y" else "Non"

    rank_html = (
        f'<span style="font-size:0.63rem;color:{text_sec};font-family:{FONT}">'
        f'#{idx + 1}</span>'
    )

    from_spread_s   = format_value(sw.get("from_spread"),    "{:.0f}", fallback="—")
    to_spread_s     = format_value(sw.get("to_spread"),      "{:.0f}", fallback="—")
    from_tenor_s    = format_value(sw.get("from_tenor"),     "{:.1f}", fallback="—")
    to_tenor_s      = format_value(sw.get("to_tenor"),       "{:.1f}", fallback="—")
    from_dur_s      = format_value(sw.get("from_duration"),  "{:.2f}", fallback="—")
    to_dur_s        = format_value(sw.get("to_duration"),    "{:.2f}", fallback="—")
    from_esg_s      = format_value(sw.get("from_esg"),       "{:.1f}", fallback="—")
    to_esg_s        = format_value(sw.get("to_esg"),         "{:.1f}", fallback="—")

    rows_html = "".join([
        _row("Z-Sprd (bps)", from_spread_s, to_spread_s,
             _delta_html(sw.get("delta_spread"), "{:+.0f}", good_positive=True)),
        _row("Tenor (ans)", from_tenor_s, to_tenor_s,
             _delta_html(sw.get("delta_tenor"), "{:+.1f}", good_positive=True)),
        _row("Duration", from_dur_s, to_dur_s, dur_dhtml),
        _row("ESG Score", from_esg_s, to_esg_s,
             _delta_html(sw.get("delta_esg"), "{:+.1f}", good_positive=True)),
        _row_text("Type coupon",
                  str(sw.get("from_coupon_type") or "—"),
                  str(sw.get("to_coupon_type")   or "—")),
        _row_text("Callable", callable_from, callable_to),
        _row_text("Industrie BICS",
                  str(sw.get("from_bics") or "—"),
                  str(sw.get("to_bics")   or "—")),
    ])

    from_col = _bond_col(
        "Vend",
        sw.get("from_ticker"), sw.get("from_name"),
        sw.get("from_rating", "N/A"), sw.get("from_seniority", ""),
        str(sw.get("from_country") or "—"),
    )
    to_col = _bond_col(
        "Achète",
        sw.get("to_ticker"), sw.get("to_name"),
        sw.get("to_rating", "N/A"), sw.get("to_seniority", ""),
        str(sw.get("to_country") or "—"),
        to_green_badge,
    )

    return f"""
<div style="background:{surface};border:1px solid {border};
            border-left:3px solid {mode_accent};border-radius:8px;
            padding:0.85rem 1rem 0.75rem;margin-bottom:0.1rem">

  <div style="display:flex;align-items:center;gap:0.45rem;margin-bottom:0.6rem">
    <span style="font-size:0.57rem;font-weight:700;background:{mode_accent};
                 color:#000;padding:1px 7px;border-radius:3px;
                 letter-spacing:0.06em;font-family:{FONT}">{badge_label}</span>
    {rank_html}
    <span style="margin-left:auto;font-size:0.63rem;color:{text_sec};font-family:{FONT}">
      Poids&nbsp;<b style="color:{text_col}">{weight_str}</b></span>
  </div>

  <div style="display:grid;grid-template-columns:1fr 18px 1fr;
              gap:0.35rem;align-items:start;margin-bottom:0.55rem">
    {from_col}
    <div style="padding-top:1rem;text-align:center;color:{orange};
                font-size:1rem;font-family:{FONT}">→</div>
    {to_col}
  </div>

  <div style="border-top:1px solid {border};padding-top:0.4rem">
    <table style="width:100%;border-collapse:collapse">
      {rows_html}
    </table>
  </div>
</div>
"""
