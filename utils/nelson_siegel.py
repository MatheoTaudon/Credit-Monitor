"""
utils/nelson_siegel.py — Fitting de la courbe Nelson-Siegel.

Modèle Nelson-Siegel (1987) :
    y(t) = β0 + β1·(1−e^(−t/τ))/(t/τ) + β2·[(1−e^(−t/τ))/(t/τ) − e^(−t/τ)]

Paramètres :
    β0 : niveau long terme
    β1 : pente (impact court terme)
    β2 : courbure (impact moyen terme)
    τ  : constante de decay (> 0)

API publique :
    nelson_siegel_curve(t, beta0, beta1, beta2, tau)  → np.ndarray
    fit_nelson_siegel(tenors, yields)                 → dict
    generate_curve_points(params, t_min, t_max, n)    → (array, array) | (None, None)
    get_fit_quality_label(r_squared)                  → str

Contrat :
    - Zéro import Streamlit — toutes les fonctions sont pures
    - NaN/inf nettoyés avant fit
    - Échecs retournés proprement via {"success": False, ...}
"""
import numpy as np
from scipy.optimize import curve_fit


CONFIG = {
    "MIN_POINTS": 10,
    # Guess et bounds sur échelle normalisée (z-score) — scale-indépendant
    # Fonctionne pour YTM (%) comme pour Z-Sprd / G-Spread (bps)
    "P0_NORM":    [0.5, -0.3, 0.5, 2.0],
    "BOUNDS_NORM": (
        [-5.0, -5.0, -5.0, 0.1],
        [ 8.0,  8.0,  8.0, 30.0],
    ),
    "MAX_ITER": 5000,
}


# ─────────────────────────────────────────────────────────────────
# Formule Nelson-Siegel
# ─────────────────────────────────────────────────────────────────

def nelson_siegel_curve(
    t: float | np.ndarray,
    beta0: float,
    beta1: float,
    beta2: float,
    tau: float,
) -> np.ndarray:
    """
    Évalue la courbe Nelson-Siegel en un ou plusieurs tenors.

    Gère le cas t == 0 par la limite mathématique : y(0) = β0 + β1.

    Args:
        t      : Tenor(s) en années. Scalaire ou ndarray.
        beta0  : Niveau long terme.
        beta1  : Pente court terme.
        beta2  : Courbure moyen terme.
        tau    : Constante de decay (> 0).

    Returns:
        np.ndarray de même forme que t.
    """
    t = np.asarray(t, dtype=float)
    result = np.empty_like(t)

    zero_mask = t == 0.0
    pos_mask  = ~zero_mask

    # Limite en t → 0 : (1 − e^(−t/τ)) / (t/τ) → 1
    result[zero_mask] = beta0 + beta1

    if pos_mask.any():
        t_pos  = t[pos_mask]
        x      = t_pos / tau
        factor = (1.0 - np.exp(-x)) / x
        result[pos_mask] = (
            beta0
            + beta1 * factor
            + beta2 * (factor - np.exp(-x))
        )

    return result


# ─────────────────────────────────────────────────────────────────
# Fitting
# ─────────────────────────────────────────────────────────────────

def fit_nelson_siegel(
    tenors: np.ndarray,
    yields: np.ndarray,
) -> dict:
    """
    Fitte les 4 paramètres NS par moindres carrés (scipy.optimize.curve_fit).

    Nettoie NaN et inf avant le fit. Exige au moins CONFIG["MIN_POINTS"]
    points valides. Retourne toujours un dict (jamais None).

    Args:
        tenors : Array-like de tenors en années (valeurs > 0 attendues).
        yields : Array-like de taux/spreads (même longueur que tenors).

    Returns:
        Succès :
            {"success": True, "beta0": float, "beta1": float,
             "beta2": float, "tau": float,
             "r_squared": float, "n_points": int}
        Échec :
            {"success": False, "reason": str, "n_points": int}
    """
    t = np.asarray(tenors, dtype=float)
    y = np.asarray(yields, dtype=float)

    # Nettoyage : retirer NaN, inf et tenors ≤ 0
    valid = np.isfinite(t) & np.isfinite(y) & (t > 0)
    t_clean = t[valid]
    y_clean = y[valid]
    n = int(t_clean.size)

    if n < CONFIG["MIN_POINTS"]:
        return {
            "success": False,
            "reason": f"Pas assez de points valides : {n} < {CONFIG['MIN_POINTS']}",
            "n_points": n,
        }

    y_std = np.std(y_clean)
    # Données sans variance → curve_fit peut diverger sans raison utile
    if y_std == 0.0:
        return {
            "success": False,
            "reason": "Tous les yields sont identiques (variance nulle).",
            "n_points": n,
        }

    # Normalisation z-score : rend le fit scale-indépendant
    # (fonctionne aussi bien pour YTM en % que Z-Sprd/G-Spread en bps)
    y_mean = np.mean(y_clean)
    y_norm = (y_clean - y_mean) / y_std

    try:
        popt, _ = curve_fit(
            nelson_siegel_curve,
            t_clean,
            y_norm,
            p0=CONFIG["P0_NORM"],
            bounds=CONFIG["BOUNDS_NORM"],
            maxfev=CONFIG["MAX_ITER"],
        )
    except (RuntimeError, ValueError) as exc:
        return {
            "success": False,
            "reason": str(exc),
            "n_points": n,
        }

    # Dénormalisation : β0/β1/β2 dans les unités originales, τ inchangé
    beta0 = float(popt[0]) * y_std + y_mean
    beta1 = float(popt[1]) * y_std
    beta2 = float(popt[2]) * y_std
    tau   = float(popt[3])

    y_hat     = nelson_siegel_curve(t_clean, beta0, beta1, beta2, tau)
    ss_res    = float(np.sum((y_clean - y_hat) ** 2))
    ss_tot    = float(np.sum((y_clean - y_mean) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    return {
        "success":   True,
        "beta0":     beta0,
        "beta1":     beta1,
        "beta2":     beta2,
        "tau":       tau,
        "r_squared": round(r_squared, 6),
        "n_points":  n,
    }


# ─────────────────────────────────────────────────────────────────
# Génération de la courbe lissée
# ─────────────────────────────────────────────────────────────────

def generate_curve_points(
    params: dict,
    t_min: float,
    t_max: float,
    n_points: int = 200,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """
    Génère n_points sur la courbe NS fittée entre t_min et t_max.

    Args:
        params   : Dict retourné par fit_nelson_siegel.
        t_min    : Tenor minimum (années).
        t_max    : Tenor maximum (années).
        n_points : Nombre de points sur la courbe (défaut 200).

    Returns:
        (tenors_array, yields_array) si params["success"] is True,
        (None, None) sinon.
    """
    if not params.get("success"):
        return None, None

    tenors = np.linspace(t_min, t_max, n_points)
    yields = nelson_siegel_curve(
        tenors,
        params["beta0"],
        params["beta1"],
        params["beta2"],
        params["tau"],
    )
    return tenors, yields


# ─────────────────────────────────────────────────────────────────
# Qualité du fit
# ─────────────────────────────────────────────────────────────────

def get_fit_quality_label(r_squared: float) -> str:
    """
    Convertit un R² en label lisible.

    Args:
        r_squared : Coefficient de détermination (float).

    Returns:
        "Excellent" (≥ 0.90) | "Bon" (≥ 0.75) | "Moyen" (≥ 0.50) | "Faible" (< 0.50)
    """
    if r_squared >= 0.90:
        return "Excellent"
    if r_squared >= 0.75:
        return "Bon"
    if r_squared >= 0.50:
        return "Moyen"
    return "Faible"
