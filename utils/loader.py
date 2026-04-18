"""
utils/loader.py — Chargement et merge du fichier dataFI.xlsx.

Feuilles source :
- Qualitative : Ticker, ISIN, Poids, Short Name, BICS Industry, GICS Sector,
                Seniority, Country, Bloomberg Composite Ratings, ESG Score,
                Green Bond, MSCI ESG Rating, Next Call Date, Maturity Date,
                Callable, Amount Outstanding, Coupon, Coupn Type
- Quantitative : ISIN, YTM, Z-Sprd, G-Spread, ModIfied Duration

API publique :
- load_data(path)           → DataFrame mergé, @st.cache_data
- compute_tenor(series)     → Series float, NaN si passé ou invalide
- get_sectors(df)           → list[str] trié
- get_seniorities(df)       → list[str] trié
- get_issuers(df)           → list[str] trié
- filter_df(df, ...)        → DataFrame filtré
- _merge_and_clean(q, q2)   → logique de merge, accessible aux tests
"""
import os

import numpy as np
import pandas as pd
import streamlit as st
from datetime import date


CONFIG = {
    "DATA_PATH": "dataFI.xlsx",
    "SHEET_QUALITATIVE": "Qualitative",
    "SHEET_QUANTITATIVE": "Quantitative",
    "JOIN_KEY": "ISIN",
    "NUMERIC_COLS": [
        "YTM", "Z-Sprd", "G-Spread", "ModIfied Duration",
        "ESG Score", "Coupon", "Amount Outstanding",
    ],
    "DAYS_PER_YEAR": 365.25,
}


@st.cache_data
def load_data(path: str = CONFIG["DATA_PATH"]) -> pd.DataFrame:
    """
    Charge dataFI.xlsx et retourne le DataFrame univers mergé et nettoyé.

    Args:
        path: Chemin vers le fichier .xlsx (défaut : CONFIG["DATA_PATH"]).

    Returns:
        DataFrame avec toutes les colonnes Qualitative + Quantitative + Tenor + Tenor to Call.

    Raises:
        FileNotFoundError: Si le fichier n'existe pas au chemin indiqué.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Fichier de données introuvable : '{path}'. "
            "Vérifiez que dataFI.xlsx est bien à la racine du projet."
        )

    df_qual = pd.read_excel(path, sheet_name=CONFIG["SHEET_QUALITATIVE"])
    df_quant = pd.read_excel(path, sheet_name=CONFIG["SHEET_QUANTITATIVE"])
    return _merge_and_clean(df_qual, df_quant)


def _merge_and_clean(df_qual: pd.DataFrame, df_quant: pd.DataFrame) -> pd.DataFrame:
    """
    Merge et nettoie les deux feuilles. Fonction pure, testable sans Streamlit.

    - Inner join sur ISIN
    - Strip des colonnes string
    - Coercion numérique sur les colonnes quantitatives
    - Calcul de la colonne Tenor
    - Ne modifie jamais df_qual ni df_quant en entrée

    Args:
        df_qual: DataFrame de la feuille Qualitative.
        df_quant: DataFrame de la feuille Quantitative.

    Returns:
        DataFrame mergé, nettoyé, avec Tenor, reset_index.
    """
    qual = df_qual.copy()
    quant = df_quant.copy()

    # Strip des espaces sur toutes les colonnes string
    for df in (qual, quant):
        str_cols = df.select_dtypes(include="object").columns
        df[str_cols] = df[str_cols].apply(lambda col: col.str.strip())

    merged = qual.merge(quant, on=CONFIG["JOIN_KEY"], how="inner")

    # Coercion numérique
    for col in CONFIG["NUMERIC_COLS"]:
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors="coerce")

    merged["Tenor"] = compute_tenor(merged["Maturity Date"])

    # Tenor to Call : pour les callable bonds avec Next Call Date valide,
    # utilise la date du premier call ; sinon, repli sur Tenor
    if "Next Call Date" in merged.columns and "Callable" in merged.columns:
        _tenor_call = compute_tenor(merged["Next Call Date"])
        merged["Tenor to Call"] = merged["Tenor"].copy()
        _callable_mask = (merged["Callable"] == "Y") & _tenor_call.notna()
        merged.loc[_callable_mask, "Tenor to Call"] = _tenor_call[_callable_mask]
    else:
        merged["Tenor to Call"] = merged["Tenor"].copy()

    merged = merged.reset_index(drop=True)
    return merged


def compute_tenor(
    maturity_series: pd.Series,
    ref_date: date | None = None,
) -> pd.Series:
    """
    Calcule le tenor en années depuis ref_date jusqu'à chaque date de maturité.

    Les maturités passées ou invalides retournent NaN.

    Args:
        maturity_series: Series de dates (str, datetime ou NaT acceptés).
        ref_date: Date de référence (défaut : date.today()).

    Returns:
        Series float, NaN si maturité passée, aujourd'hui ou invalide.
    """
    if ref_date is None:
        ref_date = date.today()

    ref_ts = pd.Timestamp(ref_date)
    maturities = pd.to_datetime(maturity_series, errors="coerce")
    delta_days = (maturities - ref_ts).dt.days
    tenor = delta_days / CONFIG["DAYS_PER_YEAR"]

    # NaN pour maturités passées ou nulles
    return tenor.where(tenor > 0, np.nan)


def get_sectors(df: pd.DataFrame) -> list[str]:
    """Retourne la liste triée des GICS Sector uniques (hors NaN)."""
    return sorted(df["GICS Sector"].dropna().unique().tolist())


def get_seniorities(df: pd.DataFrame) -> list[str]:
    """Retourne la liste triée des Seniority uniques (hors NaN)."""
    return sorted(df["Seniority"].dropna().unique().tolist())


def get_issuers(df: pd.DataFrame) -> list[str]:
    """Retourne la liste triée des Short Name uniques (hors NaN)."""
    return sorted(df["Short Name"].dropna().unique().tolist())


def filter_df(
    df: pd.DataFrame,
    sectors: list[str] | None = None,
    seniorities: list[str] | None = None,
) -> pd.DataFrame:
    """
    Filtre le DataFrame selon les critères passés.

    None ou liste vide = pas de filtre appliqué sur ce critère.
    Retourne toujours un DataFrame (jamais None).

    Args:
        df: DataFrame univers (sortie de load_data ou _merge_and_clean).
        sectors: Liste des GICS Sector à conserver.
        seniorities: Liste des Seniority à conserver.

    Returns:
        DataFrame filtré avec reset_index.
    """
    result = df.copy()

    if sectors:
        result = result[result["GICS Sector"].isin(sectors)]

    if seniorities:
        result = result[result["Seniority"].isin(seniorities)]

    return result.reset_index(drop=True)
