"""
app.py — Routeur principal. Rien d'autre que dispatcher vers les modules.
"""
import streamlit as st

from modules import accueil, comparables, filtres
from modules import sales_monitor

st.set_page_config(
    layout="wide",
    page_title="Credit Monitor",
    initial_sidebar_state="collapsed",
)

if "page" not in st.session_state:
    st.session_state["page"] = "accueil"

_pages = {
    "accueil":       accueil.show,
    "comparables":   comparables.show,
    "sales_monitor": sales_monitor.show,
    "filtres":       filtres.show,
}

_pages.get(st.session_state["page"], accueil.show)()
