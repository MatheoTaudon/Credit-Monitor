# Credit Monitor

A Bloomberg-styled fixed income analytics dashboard built with Streamlit.
Live app → **[credit-monitor.streamlit.app](https://credit-monitor.streamlit.app)**

---

## Overview

Credit Monitor is an interactive analytics platform covering the **Bloomberg Euro Corporate Bond Index**. It provides four interconnected views for fixed income analysis: yield curve fitting, universe screening, portfolio monitoring, and comparable bond search.

---

## Features

### Homepage — Yield Curve
- Scatter plot of the full bond universe coloured by GICS Sector
- **Nelson-Siegel curve fitting** with R² quality annotation
- Filters: GICS Sector, Seniority, Y-axis (Z-Spread / YTM / G-Spread), X-axis (Maturity / Maturity to Call)
- Summary metrics: bond count, median YTM, median Z-Spread, median duration

### Universe Screener
- 7-column categorical filter bar (Sector, Seniority, Country, Rating, BICS Industry, Coupon Type, Issuer)
- Numeric sliders: Z-Spread, YTM, Duration, Tenor, Coupon, Outstanding amount
- ESG filters: Green Bond toggle, ESG Score range with index-level benchmark marker
- Zoomable Nelson-Siegel chart updated in real time
- Selectable table → detailed bond card on click

### Client Fund Monitor
- Asset Manager → Fund cascade selector (reads from `Funds.xlsx`)
- Portfolio bubble chart (bubble size ∝ portfolio weight) + Nelson-Siegel fit
- **Intelligent switch proposals** (top 10 per fund):
  - Same BICS industry, country, seniority, coupon type
  - Duration within ±1, at least equal rating
  - Ranked by maximum Z-Spread pickup
  - Optional ESG / Green Bond constraints

### Comparable Bond Search
- Free-text search by ISIN, issuer name, or ticker
- KNN-based comparable finder (same BICS industry + seniority universe)
- Constraints: exclude same issuer, Green Bond only, best ESG score
- Chart: greyed universe + orange NS curve + star marker for reference bond + coloured comparables

---

## Architecture

```
app.py              → Pure router (session_state page dispatch)
modules/
  accueil.py        → Homepage UI
  filtres.py        → Universe screener UI
  sales_monitor.py  → Client fund monitor UI
  comparables.py    → Comparable bond search UI
utils/
  display.py        → Shared constants (Y_LABELS, X_COL_MAP, RATING_ORDER)
                      + format_value, safe_range, sorted_ratings
                      + render_badge, render_bond_card, render_switch_card
  plots.py          → Pure Plotly figure builders (build_sector_chart,
                      build_portfolio_chart, build_comparables_chart)
  loader.py         → Excel data loading & caching
  style.py          → Theme detection, CSS injection, Plotly templates
  nelson_siegel.py  → Nelson-Siegel curve fitting (scipy)
  knn.py            → KNN comparable search (scikit-learn)
  funds.py          → Portfolio building & switch proposal engine
.streamlit/
  config.toml       → Bloomberg Orange theme
```

**Design principles:**
- `utils/` contains only pure functions — no `st.*` calls (except `style.inject_css`)
- `modules/` handles UI and orchestration only — consumes utils
- `app.py` is a router only — reads `st.session_state.page`, calls the right module

---

## Data

| File | Description |
|------|-------------|
| `dataFI.xlsx` | Bloomberg Euro Corporate Bond Index universe (bonds, spreads, ratings, ESG scores) |
| `Funds.xlsx` | Client fund holdings (one sheet per fund, with weights and ISINs) |

---

## Tech Stack

| Library | Usage |
|---------|-------|
| `streamlit >= 1.35` | UI framework |
| `pandas >= 2.0` | Data manipulation |
| `plotly >= 5.20` | Interactive charts |
| `scipy >= 1.12` | Nelson-Siegel curve fitting |
| `scikit-learn >= 1.4` | KNN comparable search |
| `openpyxl >= 3.1` | Excel file reading |

---

## Running Locally

```bash
# Clone
git clone https://github.com/MatheoTaudon/Credit-Monitor.git
cd Credit-Monitor

# Install dependencies
pip install -r requirements.txt

# Run
streamlit run app.py
```

---

## License

Private repository — all rights reserved.
