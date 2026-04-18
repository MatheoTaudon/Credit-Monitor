"""
utils/funds.py — Chargement des fonds clients et moteur de switch.

Chaque sheet de Funds.xlsx = un fonds.
Adaptatif : tout nouveau onglet ajouté au fichier est automatiquement découvert.

API publique :
- load_funds(path)                                        → dict[str, pd.DataFrame]
- get_asset_managers(funds_raw)                          → list[str]
- get_funds_for_am(funds_raw, asset_manager)             → dict[str, pd.DataFrame]
- get_fund_display_name(sheet, raw_df)                   → str
- build_portfolio(raw_df, universe)                      → pd.DataFrame
- propose_switches(portfolio, universe, n, green_only,
                   esg_boost)                            → pd.DataFrame

Règles :
- Zéro import streamlit sauf @st.cache_data
- Fonctions pures sauf load_funds
- Colonnes attendues dans Funds.xlsx : Asset Manager, Nom du fonds, ISIN, % of NAV

Moteur de switch — critères STRICTS (aucun fallback) :
- Même BICS Industry
- Même Country
- Au moins aussi bonne Seniority (senior ≥ courant)
- Même Coupn Type
- Duration ±1 max (pas la maturité)
- Au moins aussi bonne notation (rating_num candidat ≥ rating_num courant)
- Bonds Not Rated exclus (des deux côtés)
- Pickup Z-Sprd > 0 obligatoire
- ESG / Green : uniquement si l'utilisateur les active
"""
import os

import numpy as np
import pandas as pd
import streamlit as st


# ── Constantes ─────────────────────────────────────────────────────
_ISIN   = "ISIN"
_WEIGHT = "% of NAV"
_AM     = "Asset Manager"
_FN     = "Nom du fonds"

# Fenêtre de duration maximale (hard filter)
_DURATION_WINDOW = 1.0   # ± en années de duration

# Echelle de séniorité (plus haut = plus senior = meilleur)
# Couvre tous les labels Bloomberg y compris les niveaux réglementaires EU (BRRD)
_SENIORITY_SCALE: dict[str, int] = {
    # Senior Secured (10)
    "Senior Secured":               10,
    "Sr Secured":                   10,
    "Sr Sec":                       10,
    "Secured":                      10,
    # Senior Unsecured / Senior Preferred (8)
    "Senior Unsecured":             8,
    "Sr Unsecured":                 8,
    "Sr Unsec":                     8,
    "Senior Preferred":             8,
    "Senior":                       8,
    "Sr":                           8,
    # Senior Bail-In / Senior Non-Preferred (6)
    "Senior Bail-In":               6,
    "Senior Non-Preferred":         6,
    "Sr Bail-In":                   6,
    "SNP":                          6,
    # Senior Subordinated (5)
    "Senior Sub":                   5,
    "Senior Subordinated":          5,
    "Sr Sub":                       5,
    "Sr Subordinated":              5,
    # Subordinated / Tier 2 (4)
    "Subordinated":                 4,
    "Subordinated Unsecured":       4,
    "Sub":                          4,
    "Unsecured Subordinated":       4,
    "Tier 2":                       4,
    "T2":                           4,
    # Junior Subordinated (2)
    "Junior Subordinated":          2,
    "Jr Sub":                       2,
    "Jr Subordinated":              2,
    # Junior / AT1 / Tier 1 (1)
    "Junior":                       1,
    "Jr":                           1,
    "Tier 1":                       1,
    "T1":                           1,
    "AT1":                          1,
    "Additional Tier 1":            1,
}

# Echelle numérique des ratings Bloomberg (plus haut = meilleur)
_RATING_SCALE: dict[str, int] = {
    "AAA": 22, "AA+": 21, "AA": 20, "AA-": 19,
    "A+": 18,  "A": 17,   "A-": 16,
    "BBB+": 15, "BBB": 14, "BBB-": 13,
    "BB+": 12,  "BB": 11,  "BB-": 10,
    "B+": 9,    "B": 8,    "B-": 7,
    "CCC+": 6,  "CCC": 5,  "CCC-": 4,
    "CC": 3,    "C": 2,    "D": 1,
}


# ── Chargement ─────────────────────────────────────────────────────

@st.cache_data
def load_funds(path: str = "Funds.xlsx") -> dict[str, pd.DataFrame]:
    """
    Charge tous les onglets de Funds.xlsx.

    Returns:
        dict {sheet_name: raw_df}.

    Raises:
        FileNotFoundError: si le fichier est introuvable.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Fichier fonds introuvable : '{path}'. "
            "Vérifiez que Funds.xlsx est à la racine du projet."
        )
    xl = pd.ExcelFile(path)
    return {sheet: xl.parse(sheet) for sheet in xl.sheet_names}


# ── Navigation AM / Fonds ───────────────────────────────────────────

def get_asset_managers(funds_raw: dict) -> list[str]:
    """
    Retourne la liste triée des Asset Managers uniques (un par fonds).

    Lit la première valeur non-NaN de la colonne 'Asset Manager' dans chaque
    sheet. Si aucun fonds n'a de valeur, retourne une liste vide.
    """
    ams: set[str] = set()
    for raw_df in funds_raw.values():
        if _AM not in raw_df.columns:
            continue
        valid = raw_df[_AM].dropna()
        if not valid.empty:
            ams.add(str(valid.iloc[0]).strip())
    return sorted(ams)


def get_funds_for_am(funds_raw: dict, asset_manager: str) -> dict[str, pd.DataFrame]:
    """
    Retourne le sous-ensemble de funds_raw appartenant à un Asset Manager donné.
    """
    result: dict[str, pd.DataFrame] = {}
    for sheet, raw_df in funds_raw.items():
        if _AM not in raw_df.columns:
            continue
        valid = raw_df[_AM].dropna()
        if not valid.empty and str(valid.iloc[0]).strip() == asset_manager:
            result[sheet] = raw_df
    return result


def get_fund_display_name(sheet: str, raw_df: pd.DataFrame) -> str:
    """
    Retourne 'Asset Manager — Nom du fonds' depuis la première ligne non-NaN.
    Fallback sur le nom du sheet si les colonnes sont absentes/vides.
    """
    def _first(col: str) -> str:
        if col not in raw_df.columns:
            return ""
        valid = raw_df[col].dropna()
        return str(valid.iloc[0]).strip() if not valid.empty else ""

    am, fn = _first(_AM), _first(_FN)
    if am and fn:
        return f"{am} — {fn}"
    return fn or am or sheet


# ── Portefeuille ────────────────────────────────────────────────────

def build_portfolio(raw_df: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    """
    Agrège les holdings (somme des poids par ISIN) et merge avec l'univers.

    - Colonnes dupliquées sur le même ISIN → poids sommés
    - Merge LEFT sur ISIN : holdings sans match conservés (colonnes univers = NaN)
    - Colonne 'weight' = % of NAV brut (ex: 0.0027 = 0.27%)

    Returns:
        DataFrame trié par poids décroissant, reset_index.
    """
    if _ISIN not in raw_df.columns or _WEIGHT not in raw_df.columns:
        return pd.DataFrame()

    h = raw_df[[_ISIN, _WEIGHT]].copy().rename(columns={_WEIGHT: "weight"})
    h["weight"] = pd.to_numeric(h["weight"], errors="coerce")
    h = h.dropna(subset=[_ISIN, "weight"])
    h = h.groupby(_ISIN, as_index=False)["weight"].sum()

    portfolio = h.merge(universe, on=_ISIN, how="left")
    return portfolio.sort_values("weight", ascending=False).reset_index(drop=True)


# ── Moteur de switch ────────────────────────────────────────────────

def _seniority_to_num(seniority_str) -> int:
    """Convertit une séniorité en entier (plus haut = plus senior). Inconnu → 0."""
    if pd.isna(seniority_str):
        return 0
    return _SENIORITY_SCALE.get(str(seniority_str).strip(), 0)


def _rating_to_num(rating_str) -> int:
    """Convertit un rating Bloomberg en entier (plus haut = meilleur). NR/NaN → 0."""
    if pd.isna(rating_str):
        return 0
    return _RATING_SCALE.get(str(rating_str).strip(), 0)


def _is_rated(rating_str) -> bool:
    """True si le bond a un rating reconnu (non NR / NaN)."""
    if pd.isna(rating_str):
        return False
    return str(rating_str).strip() in _RATING_SCALE


def _build_switch_row(
    current: pd.Series,
    candidate: pd.Series,
    pickup: float,
) -> dict:
    """Construit le dict résultat pour une paire de switch."""

    def _delta(col: str):
        a, b = current.get(col), candidate.get(col)
        return float(b) - float(a) if pd.notna(a) and pd.notna(b) else None

    return {
        # Bond actuel
        "from_isin":        current.get(_ISIN, ""),
        "from_ticker":      current.get("Ticker", ""),
        "from_name":        current.get("Short Name", ""),
        "from_rating":      current.get("Bloomberg Composite Ratings", "N/A"),
        "from_seniority":   current.get("Seniority", ""),
        "from_bics":        current.get("BICS Industry", ""),
        "from_sector":      current.get("GICS Sector", ""),
        "from_esg":         current.get("ESG Score"),
        "from_green":       current.get("Green Bond", "N"),
        "from_spread":      current.get("Z-Sprd"),
        "from_tenor":       current.get("Tenor"),
        "from_weight":      current.get("weight"),
        "from_duration":    current.get("ModIfied Duration"),
        "from_callable":    current.get("Callable", "N"),
        "from_coupon_type": current.get("Coupn Type", ""),
        "from_country":     current.get("Country", ""),
        # Bond proposé
        "to_isin":          candidate.get(_ISIN, ""),
        "to_ticker":        candidate.get("Ticker", ""),
        "to_name":          candidate.get("Short Name", ""),
        "to_rating":        candidate.get("Bloomberg Composite Ratings", "N/A"),
        "to_seniority":     candidate.get("Seniority", ""),
        "to_bics":          candidate.get("BICS Industry", ""),
        "to_sector":        candidate.get("GICS Sector", ""),
        "to_esg":           candidate.get("ESG Score"),
        "to_green":         candidate.get("Green Bond", "N"),
        "to_spread":        candidate.get("Z-Sprd"),
        "to_tenor":         candidate.get("Tenor"),
        "to_duration":      candidate.get("ModIfied Duration"),
        "to_callable":      candidate.get("Callable", "N"),
        "to_coupon_type":   candidate.get("Coupn Type", ""),
        "to_country":       candidate.get("Country", ""),
        # Deltas
        "delta_esg":      _delta("ESG Score"),
        "delta_spread":   _delta("Z-Sprd"),
        "delta_tenor":    _delta("Tenor"),
        "delta_duration": _delta("ModIfied Duration"),
        "score":          pickup,
    }


def _find_best_switches_for_bond(
    current: pd.Series,
    pool: pd.DataFrame,
    green_only: bool,
    esg_boost: bool,
    top_k: int = 1,
) -> list[dict]:
    """
    Trouve les top_k meilleurs candidats dans pool pour remplacer current.

    Critères STRICTS (hard filters, aucun fallback) :
    1. current non NR (sinon aucun switch généré)
    2. Candidats non NR
    3. Même Country
    4. Même BICS Industry
    5. Seniority candidat ≥ seniority courante (au moins aussi senior)
    6. Même Coupn Type
    7. Rating candidat ≥ rating courant (au moins aussi bonne notation)
    8. Duration ± _DURATION_WINDOW
    9. Z-Sprd pickup > 0 (spread candidat > spread courant)
    10. ESG : si esg_boost → ESG candidat > ESG courant
              si green_only → déjà filtré dans le pool

    Triage final : pickup Z-Sprd décroissant.

    Returns:
        Liste de dicts (max top_k). Vide si aucun candidat valide.
    """
    # ── 1. Skip NR sur le bond courant ────────────────────────────
    if not _is_rated(current.get("Bloomberg Composite Ratings")):
        return []

    curr_rating_num = _rating_to_num(current.get("Bloomberg Composite Ratings"))

    # ── 2. Exclure NR du pool ─────────────────────────────────────
    sub = pool[pool["Bloomberg Composite Ratings"].map(_is_rated)].copy()
    if sub.empty:
        return []

    # ── 3. Même Country ───────────────────────────────────────────
    country = current.get("Country")
    if pd.notna(country) and str(country).strip():
        sub = sub[sub["Country"] == str(country).strip()]
    if sub.empty:
        return []

    # ── 4. Même BICS Industry ────────────────────────────────────
    industry = current.get("BICS Industry")
    if pd.notna(industry) and str(industry).strip():
        sub = sub[sub["BICS Industry"] == str(industry).strip()]
    if sub.empty:
        return []

    # ── 5. Au moins aussi bonne Seniority ────────────────────────
    seniority = current.get("Seniority")
    curr_sen_num = _seniority_to_num(seniority)
    if curr_sen_num > 0:
        sub = sub[sub["Seniority"].map(_seniority_to_num) >= curr_sen_num].copy()
    if sub.empty:
        return []

    # ── 6. Même Coupn Type ────────────────────────────────────────
    coupon_type = current.get("Coupn Type")
    if pd.notna(coupon_type) and str(coupon_type).strip():
        sub = sub[sub["Coupn Type"] == str(coupon_type).strip()]
    if sub.empty:
        return []

    # ── 7. Au moins aussi bonne notation ──────────────────────────
    sub = sub[sub["Bloomberg Composite Ratings"].map(_rating_to_num) >= curr_rating_num].copy()
    if sub.empty:
        return []

    # ── 8. Duration ± _DURATION_WINDOW ────────────────────────────
    curr_dur = current.get("ModIfied Duration")
    if pd.isna(curr_dur):
        return []
    curr_dur_f = float(curr_dur)
    sub = sub[
        sub["ModIfied Duration"].notna() &
        ((sub["ModIfied Duration"] - curr_dur_f).abs() <= _DURATION_WINDOW)
    ].copy()
    if sub.empty:
        return []

    # ── 9. Pickup Z-Sprd > 0 ─────────────────────────────────────
    curr_spread = current.get("Z-Sprd")
    if pd.isna(curr_spread):
        return []
    curr_sf = float(curr_spread)
    sub = sub[sub["Z-Sprd"].fillna(-np.inf) > curr_sf].copy()
    if sub.empty:
        return []

    # ── 10. Contrainte ESG ────────────────────────────────────────
    if esg_boost:
        curr_esg = current.get("ESG Score")
        if pd.notna(curr_esg):
            sub = sub[sub["ESG Score"].fillna(-np.inf) > float(curr_esg)].copy()
        if sub.empty:
            return []

    # ── Triage par pickup décroissant ─────────────────────────────
    sub["_pickup"] = sub["Z-Sprd"] - curr_sf
    top = sub.nlargest(top_k, "_pickup")

    return [
        _build_switch_row(current, cand, float(cand["_pickup"]))
        for _, cand in top.iterrows()
    ]


def propose_switches(
    portfolio: pd.DataFrame,
    universe: pd.DataFrame,
    n: int = 10,
    green_only: bool = False,
    esg_boost: bool = False,
) -> pd.DataFrame:
    """
    Propose les n meilleurs switches du portefeuille.

    Pour chaque bond éligible du portefeuille, trouve le meilleur swap
    dans l'univers (critères stricts). Retourne les n meilleures paires
    triées par pickup Z-Sprd décroissant. Si moins de n switches trouvés,
    retourne ceux disponibles.

    Args:
        portfolio  : sortie de build_portfolio
        universe   : sortie de loader.load_data
        n          : nombre max de switches à retourner (défaut 10)
        green_only : si True, seuls les Green Bonds sont proposés
        esg_boost  : si True, la destination doit améliorer l'ESG Score

    Returns:
        DataFrame avec colonnes from_*, to_*, delta_*, score.
        DataFrame vide si aucun switch trouvable.
    """
    fund_isins = set(portfolio[_ISIN].tolist())

    # Pool : univers hors portefeuille, maturités valides
    pool = universe[~universe[_ISIN].isin(fund_isins)].copy()
    pool = pool[pool["Tenor"].notna() & (pool["Tenor"] > 0)]

    if green_only:
        gb_col = pool.get("Green Bond", pd.Series("N", index=pool.index))
        pool = pool[gb_col == "Y"]

    if pool.empty:
        return pd.DataFrame()

    eligible = portfolio.dropna(subset=[_ISIN]).copy()
    if eligible.empty:
        return pd.DataFrame()

    all_rows: list[dict] = []
    for _, current in eligible.iterrows():
        rows = _find_best_switches_for_bond(current, pool, green_only, esg_boost, top_k=1)
        all_rows.extend(rows)

    if not all_rows:
        return pd.DataFrame()

    return (
        pd.DataFrame(all_rows)
        .sort_values("delta_spread", ascending=False)
        .head(n)
        .reset_index(drop=True)
    )
