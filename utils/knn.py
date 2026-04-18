"""
utils/knn.py — Recherche de bonds comparables par K-Nearest Neighbors.

Features utilisées pour la distance :

  Numériques (z-score StandardScaler) :
    - Z-Sprd         : prime de risque de crédit pure (neutralise la courbe taux)
    - ModIfied Duration : sensibilité aux taux — même segment de courbe

  Catégorielles (pénalité de distance pondérée, sans scaling) :
    - Seniority      : poids 2.0 — crucial (Senior ≠ Subordonnée)
    - BICS Industry  : poids 1.5 — classification Bloomberg granulaire
    - GICS Sector    : poids 1.0 — secteur industriel
    - Country        : poids 0.5 — risque géographique

  Les bonds avec maturité passée (Tenor ≤ 0 ou NaN) sont exclus du pool
  car non-investissables.

API publique :
    find_comparables(df, identifier, k, *, exclude_same_issuer, green_only)
        → (pd.Series | None, pd.DataFrame)

Contrat :
- Fonction pure : zéro import streamlit
- Recherche par ISIN exact (prioritaire) ou texte partiel sur Short Name
- Résultats triés par distance euclidienne croissante
"""
import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler


CONFIG = {
    "DEFAULT_K": 5,
    # Features numériques normalisées par z-score
    "NUMERIC_FEATURES": ["Z-Sprd", "ModIfied Duration"],
    # Pénalités catégorielles ajoutées à la distance (mismatch × poids)
    # Seniority : poids le plus élevé — erreur critique de la mélanger
    "CATEGORICAL_WEIGHTS": {
        "Seniority":      2.0,
        "BICS Industry":  1.5,
        "GICS Sector":    1.0,
        "Country":        0.5,
    },
}


def find_comparables(
    df: pd.DataFrame,
    identifier: str,
    k: int = CONFIG["DEFAULT_K"],
    *,
    exclude_same_issuer: bool = False,
    green_only: bool = False,
    esg_boost: bool = False,
) -> tuple[pd.Series | None, pd.DataFrame]:
    """
    Trouve les k bonds les plus proches du bond identifié par identifier.

    Distance = euclidienne sur (features numériques z-scorées)
               + (pénalités catégorielles pondérées pour Seniority,
                  GICS Sector et Country).

    Args:
        df                  : DataFrame univers (sortie de loader.load_data).
        identifier          : ISIN exact (prioritaire) ou texte partiel
                              sur Short Name (case-insensitive).
        k                   : Nombre de voisins souhaités (défaut 5).
        exclude_same_issuer : Si True, exclut les bonds du même émetteur
                              (même Short Name que le bond de référence).
        green_only          : Si True, ne cherche que parmi les Green Bonds
                              (colonne "Green Bond" == "Y").
        esg_boost           : Si True, ne cherche que parmi les bonds avec
                              un ESG Score strictement supérieur au bond de référence.

    Returns:
        Tuple (ref_bond, comparables) :
            ref_bond    : pd.Series du bond de référence,
                          ou None si identifier introuvable.
            comparables : DataFrame des k voisins, trié par distance
                          euclidienne croissante. DataFrame vide si pool
                          insuffisant ou ref introuvable / sans features
                          valides.
    """
    # ── 1. Trouver le bond de référence ───────────────────────────
    mask = df["ISIN"].str.upper() == identifier.strip().upper()
    if not mask.any():
        mask = df["Short Name"].str.contains(identifier.strip(), case=False, na=False)
    if not mask.any():
        return None, pd.DataFrame()

    ref_bond = df[mask].iloc[0]

    # ── 2. Pool de candidats ──────────────────────────────────────
    pool = df[df["ISIN"] != ref_bond["ISIN"]].copy()

    # Exclure les bonds non-investissables (maturité passée)
    if "Tenor" in pool.columns:
        pool = pool[pool["Tenor"].notna() & (pool["Tenor"] > 0)]

    # ── BICS Industry : prérequis et filtre dur ───────────────────
    # Le modèle ne s'exécute que sur le même secteur BICS que le bond de référence.
    ref_bics = ref_bond.get("BICS Industry")
    if pd.isna(ref_bics) or str(ref_bics).strip() == "":
        return ref_bond, pd.DataFrame()
    if "BICS Industry" in pool.columns:
        pool = pool[pool["BICS Industry"] == ref_bics]

    # ── 3. Filtres optionnels ─────────────────────────────────────
    if green_only and "Green Bond" in pool.columns:
        pool = pool[pool["Green Bond"] == "Y"]
    if exclude_same_issuer and "Short Name" in pool.columns:
        pool = pool[pool["Short Name"] != ref_bond["Short Name"]]
    if esg_boost and "ESG Score" in pool.columns:
        ref_esg = ref_bond.get("ESG Score")
        if pd.notna(ref_esg):
            pool = pool[pool["ESG Score"].fillna(-np.inf) > float(ref_esg)]

    # ── 4. Retirer les bonds avec NaN sur les features numériques ─
    num_features = [f for f in CONFIG["NUMERIC_FEATURES"] if f in df.columns]
    pool_clean = pool.dropna(subset=num_features)

    if pool_clean.empty:
        return ref_bond, pd.DataFrame()

    # ── 5. Vérifier que le bond de référence a des features valides
    ref_num_vals = ref_bond[num_features].values.astype(float)
    if not np.isfinite(ref_num_vals).all():
        return ref_bond, pd.DataFrame()

    # ── 6. Features numériques — normalisation z-score ────────────
    X_num = pool_clean[num_features].values.astype(float)
    scaler = StandardScaler()
    X_num_scaled = scaler.fit_transform(X_num)
    ref_num_scaled = scaler.transform(ref_num_vals.reshape(1, -1))

    # ── 7. Features catégorielles — pénalité de mismatch ──────────
    cat_penalty_cols = []
    ref_penalty_vals = []
    for col, weight in CONFIG["CATEGORICAL_WEIGHTS"].items():
        if col not in pool_clean.columns or col not in ref_bond.index:
            continue
        mismatch = (pool_clean[col] != ref_bond[col]).astype(float) * weight
        cat_penalty_cols.append(mismatch.values.reshape(-1, 1))
        ref_penalty_vals.append(0.0)   # la référence n'a jamais de pénalité vs elle-même

    if cat_penalty_cols:
        X_cat = np.hstack(cat_penalty_cols)
        ref_cat = np.array(ref_penalty_vals).reshape(1, -1)
        X = np.hstack([X_num_scaled, X_cat])
        ref = np.hstack([ref_num_scaled, ref_cat])
    else:
        X = X_num_scaled
        ref = ref_num_scaled

    # ── 8. KNN ────────────────────────────────────────────────────
    actual_k = min(k, len(pool_clean))
    nbrs = NearestNeighbors(n_neighbors=actual_k, algorithm="auto", metric="euclidean")
    nbrs.fit(X)
    _, indices = nbrs.kneighbors(ref)

    result = pool_clean.iloc[indices[0]].reset_index(drop=True)
    return ref_bond, result
