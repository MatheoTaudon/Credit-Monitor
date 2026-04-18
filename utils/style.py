"""
utils/style.py — CSS centralisé et helpers de thème Bloomberg Orange.

API publique :
- COLORS                       dict des constantes de couleur
- FONT                         str stack de polices
- get_theme()       -> str     "dark" ou "light"
- get_plotly_template(theme)   -> dict  layout Plotly complet
- get_scatter_colors(theme)    -> list[str]  12 couleurs pour scatter
- get_nav_button_style()       -> str  style HTML inline (fallback)
- inject_css(theme)            -> None  injecte le CSS global (appelle st.markdown)

Règles :
- Toutes les fonctions sont pures SAUF inject_css
- inject_css appelée une seule fois dans app.py au démarrage
- Zéro couleur hardcodée en dehors de COLORS
"""
import streamlit as st


# ─────────────────────────────────────────────────────────────────
# Constantes de design
# ─────────────────────────────────────────────────────────────────

COLORS: dict[str, str] = {
    "bloomberg_orange":    "#FB8B1E",   # aligné sur config.toml primaryColor
    "dark_bg":             "#0D0D0D",
    "dark_surface":        "#1A1A1A",
    "dark_surface_raised": "#222222",
    "dark_border":         "#333333",
    "dark_text":           "#F0F0F0",
    "dark_text_secondary": "#909090",
    "light_bg":            "#FFFFFF",
    "light_surface":       "#F4F4F4",
    "light_surface_raised":"#EBEBEB",
    "light_border":        "#D0D0D0",
    "light_text":          "#111111",
    "light_text_secondary":"#555555",
    "positive":            "#00C853",
    "negative":            "#FF1744",
    "neutral":             "#FB8B1E",
}

FONT: str = "Inter, system-ui, -apple-system, sans-serif"


# ─────────────────────────────────────────────────────────────────
# Détection du thème
# ─────────────────────────────────────────────────────────────────

def get_theme() -> str:
    base = st.get_option("theme.base")
    return "dark" if (base or "dark") == "dark" else "light"


# ─────────────────────────────────────────────────────────────────
# Plotly
# ─────────────────────────────────────────────────────────────────

def get_plotly_template(theme: str) -> dict:
    is_dark = theme == "dark"

    text_color = COLORS["dark_text"]           if is_dark else COLORS["light_text"]
    grid_color = COLORS["dark_border"]          if is_dark else COLORS["light_border"]
    hover_bg   = COLORS["dark_surface_raised"]  if is_dark else COLORS["light_surface_raised"]
    axis_line  = COLORS["dark_text_secondary"]  if is_dark else COLORS["light_text_secondary"]

    axis_common = {
        "gridcolor":  grid_color,
        "gridwidth":  0.5,
        "linecolor":  axis_line,
        "tickcolor":  axis_line,
        "tickfont":   {"family": FONT, "size": 11, "color": text_color},
        "title_font": {"family": FONT, "size": 12, "color": text_color},
        "showgrid":   False,
        "zeroline":   False,
    }

    return {
        "font":          {"family": FONT, "color": text_color},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor":  "rgba(0,0,0,0)",
        "xaxis":         axis_common.copy(),
        "yaxis":         axis_common.copy(),
        "legend": {
            "bgcolor":     "rgba(0,0,0,0)",
            "bordercolor": grid_color,
            "borderwidth": 1,
            "font":        {"family": FONT, "size": 11, "color": text_color},
        },
        "margin": {"l": 50, "r": 20, "t": 40, "b": 50},
        "hoverlabel": {
            "bgcolor":    hover_bg,
            "bordercolor": COLORS["bloomberg_orange"],
            "font":       {"family": FONT, "size": 12, "color": text_color},
        },
    }


def get_scatter_colors(theme: str) -> list[str]:
    return [
        COLORS["bloomberg_orange"],
        "#00B4D8",
        "#00C853",
        "#FF1744",
        "#AB47BC",
        "#26C6DA",
        "#FFA726",
        "#42A5F5",
        "#EF5350",
        "#66BB6A",
        "#EC407A",
        "#78909C",
    ]


# ─────────────────────────────────────────────────────────────────
# Boutons de navigation (fallback HTML inline)
# ─────────────────────────────────────────────────────────────────

def get_nav_button_style() -> str:
    return (
        f"display:inline-block;"
        f"padding:0.6rem 1.4rem;"
        f"border:2px solid {COLORS['bloomberg_orange']};"
        f"border-radius:6px;"
        f"color:{COLORS['bloomberg_orange']};"
        f"background:transparent;"
        f"font-family:{FONT};"
        f"font-size:0.95rem;"
        f"font-weight:600;"
        f"text-decoration:none;"
        f"cursor:pointer;"
        f"transition:all 0.2s ease;"
    )


# ─────────────────────────────────────────────────────────────────
# inject_css — seule fonction avec effet de bord Streamlit
# ─────────────────────────────────────────────────────────────────

def inject_css(theme: str) -> None:
    is_dark = theme == "dark"

    bg       = COLORS["dark_bg"]             if is_dark else COLORS["light_bg"]
    surface  = COLORS["dark_surface"]        if is_dark else COLORS["light_surface"]
    raised   = COLORS["dark_surface_raised"] if is_dark else COLORS["light_surface_raised"]
    border   = COLORS["dark_border"]         if is_dark else COLORS["light_border"]
    text     = COLORS["dark_text"]           if is_dark else COLORS["light_text"]
    text_sec = COLORS["dark_text_secondary"] if is_dark else COLORS["light_text_secondary"]
    orange   = COLORS["bloomberg_orange"]

    css = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* ── Reset global ────────────────────────────────────────── */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
[data-testid="block-container"] {{
    background-color: {bg} !important;
    color: {text} !important;
    font-family: {FONT} !important;
}}

p, span, div, label, li, td, th, h1, h2, h3, h4, h5, h6,
[data-testid="stMarkdown"] p,
[data-testid="stMarkdown"] span {{
    font-family: {FONT} !important;
}}

/* ── Masquer éléments natifs Streamlit ───────────────────── */
#MainMenu, footer, header {{
    visibility: hidden !important;
    height: 0 !important;
}}
[data-testid="stToolbar"] {{
    display: none !important;
}}

/* ── Masquer sidebar + navigation auto-générée ───────────── */
section[data-testid="stSidebar"],
[data-testid="stSidebarNav"],
[data-testid="stSidebarNavItems"],
[data-testid="stSidebarNavLink"],
[data-testid="stSidebarNavSeparator"],
[data-testid="collapsedControl"] {{
    display: none !important;
    visibility: hidden !important;
    width: 0 !important;
}}

/* ── Séparateur (st.divider) ─────────────────────────────── */
hr {{
    border-color: {border} !important;
    border-top-width: 1px !important;
    opacity: 1 !important;
}}

/* ── Labels widgets ──────────────────────────────────────── */
[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] span,
[data-testid="stWidgetLabel"] label {{
    color: {text} !important;
    font-family: {FONT} !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
}}

/* ── Selectbox / Multiselect — conteneur ─────────────────── */
[data-baseweb="select"] {{
    background-color: {surface} !important;
}}
[data-baseweb="select"] > div {{
    background-color: {surface} !important;
    border-color: {border} !important;
}}
[data-baseweb="select"] > div:hover {{
    border-color: {orange} !important;
}}
/* Texte affiché (valeur sélectionnée, placeholder) — sélecteurs robustes
   BaseWeb génère des class names hashés donc on cible par structure */
[data-baseweb="select"] *:not(svg):not(path):not(line):not(circle) {{
    color: {text} !important;
    font-family: {FONT} !important;
}}
[data-baseweb="select"] input {{
    color: {text} !important;
    caret-color: {orange} !important;
}}
[data-baseweb="select"] input::placeholder {{
    color: {text_sec} !important;
}}

/* ── Tags / chips multiselect ────────────────────────────── */
[data-baseweb="tag"] {{
    background-color: {raised} !important;
    border: 1px solid {orange} !important;
    border-radius: 4px !important;
}}
[data-baseweb="tag"] span {{
    color: {text} !important;
    font-family: {FONT} !important;
    font-size: 0.82rem !important;
}}
[data-baseweb="tag"] button {{
    color: {text_sec} !important;
}}
[data-baseweb="tag"] svg {{
    fill: {text_sec} !important;
}}

/* ── Dropdown (popover + menu) ───────────────────────────── */
[data-baseweb="popover"],
[data-baseweb="menu"] {{
    background-color: {raised} !important;
    border: 1px solid {border} !important;
    border-radius: 6px !important;
}}
[data-baseweb="popover"] ul,
[data-baseweb="menu"] ul {{
    background-color: {raised} !important;
}}
[data-baseweb="popover"] [role="option"],
[data-baseweb="menu"] [role="option"],
[data-baseweb="menu"] li {{
    background-color: {raised} !important;
    color: {text} !important;
    font-family: {FONT} !important;
    font-size: 0.9rem !important;
}}
[data-baseweb="popover"] [role="option"]:hover,
[data-baseweb="menu"] [role="option"]:hover,
[data-baseweb="menu"] li:hover,
[data-baseweb="popover"] [aria-selected="true"],
[data-baseweb="menu"] [aria-selected="true"] {{
    background-color: {border} !important;
    color: {orange} !important;
}}

/* ── Text input ──────────────────────────────────────────── */
[data-baseweb="input"] > div {{
    background-color: {surface} !important;
    border-color: {border} !important;
}}
[data-baseweb="input"] > div:focus-within {{
    border-color: {orange} !important;
}}
[data-baseweb="input"] input {{
    color: {text} !important;
    font-family: {FONT} !important;
    caret-color: {orange} !important;
}}
[data-baseweb="input"] input::placeholder {{
    color: {text_sec} !important;
}}

/* ── st.button ───────────────────────────────────────────── */
[data-testid="stButton"] > button {{
    border: 2px solid {orange} !important;
    color: {orange} !important;
    background: transparent !important;
    font-family: {FONT} !important;
    font-weight: 600 !important;
    border-radius: 6px !important;
    transition: all 0.2s ease !important;
}}
[data-testid="stButton"] > button:hover {{
    background: {orange} !important;
    color: #000000 !important;
}}

/* ── st.metric ───────────────────────────────────────────── */
[data-testid="stMetric"] {{
    background: {surface} !important;
    border: 1px solid {border} !important;
    border-radius: 8px !important;
    padding: 0.75rem 1rem !important;
}}
[data-testid="stMetricValue"] {{
    color: {text} !important;
    font-family: {FONT} !important;
    font-weight: 700 !important;
}}
[data-testid="stMetricLabel"] {{
    color: {text_sec} !important;
    font-family: {FONT} !important;
}}

/* ── st.info / st.warning / st.error / st.success ────────── */
[data-testid="stAlert"] {{
    background-color: {raised} !important;
    border-radius: 6px !important;
    border-left-width: 3px !important;
}}
[data-testid="stAlert"] p,
[data-testid="stAlert"] span,
[data-testid="stAlert"] div {{
    color: {text} !important;
    font-family: {FONT} !important;
}}

/* ── Slider — masquer le tick bar (bornes min/max sous le track) ── */
[data-testid="stSliderTickBar"] {{
    display: none !important;
}}
[data-testid="stSliderTickBarMin"],
[data-testid="stSliderTickBarMax"] {{
    display: none !important;
    opacity: 0 !important;
    font-size: 0 !important;
    height: 0 !important;
    overflow: hidden !important;
}}

/* ── Toggle ──────────────────────────────────────────────── */
/* Track activé — Streamlit toggle = checkbox caché + div visuel */
[data-testid="stToggle"] > label > input:checked ~ div,
[data-testid="stToggle"] input:checked + div,
[data-testid="stToggle"] input:checked ~ div {{
    background-color: {orange} !important;
    border-color: {orange} !important;
}}

/* ── Dataframes ──────────────────────────────────────────── */
/* Les cellules canvas (glide-data-grid) lisent backgroundColor de config.toml.
   Le CSS cible tous les wrappers HTML entourant le canvas. */
[data-testid="stDataFrame"] {{
    border: 1px solid {border} !important;
    border-radius: 8px !important;
    overflow: hidden !important;
    background-color: {surface} !important;
}}
[data-testid="stDataFrame"] > div,
[data-testid="stDataFrame"] > div > div,
[data-testid="stDataFrame"] > div > div > div {{
    background-color: {surface} !important;
}}
[data-testid="stDataFrame"] [role="columnheader"],
[data-testid="stDataFrame"] th {{
    background-color: {raised} !important;
    color: {text} !important;
    font-weight: 600 !important;
    font-family: {FONT} !important;
}}
[data-testid="stDataFrame"] [role="cell"],
[data-testid="stDataFrame"] td {{
    background-color: {surface} !important;
    color: {text} !important;
    font-family: {FONT} !important;
}}

/* ── Scrollbar custom ────────────────────────────────────── */
::-webkit-scrollbar {{
    width: 5px;
    height: 5px;
}}
::-webkit-scrollbar-track {{
    background: {surface};
}}
::-webkit-scrollbar-thumb {{
    background: {orange};
    border-radius: 3px;
}}
::-webkit-scrollbar-thumb:hover {{
    background: {text_sec};
}}

/* ── Bond cards ──────────────────────────────────────────── */
.bond-card {{
    background: {surface};
    border: 1px solid {border};
    border-radius: 10px;
    padding: 1rem 1.25rem;
    margin-bottom: 0.5rem;
    transition: border-color 0.2s ease;
}}
.bond-card:hover {{
    border-color: {orange};
}}

/* ── Tabs actifs ─────────────────────────────────────────── */
[data-testid="stTab"][aria-selected="true"] {{
    border-bottom-color: {orange} !important;
    color: {orange} !important;
}}

/* ── Dialog — masquer le bouton X natif (utiliser Fermer) ── */
button[data-testid="stBaseButton-headerNoPadding"],
[role="dialog"] button[data-testid="stBaseButton-headerNoPadding"] {{
    display: none !important;
}}
</style>
"""
    st.markdown(css, unsafe_allow_html=True)
