# Public Dashboard Repos For Commodity / Economic Data Inspiration

Collected on 2026-07-01 from public GitHub search results and repository
metadata. Star counts are only a rough signal; several commodity-specific repos
are small/student projects but still useful for layout and workflow ideas.

## Best References For Structure

| Repo | Focus | What To Borrow |
| --- | --- | --- |
| [owid/owid-grapher](https://github.com/owid/owid-grapher) | Public data visualization platform | Dataset catalog thinking, chart metadata, clear source notes, reusable visual grammar. |
| [shashankvemuri/economic-dashboard](https://github.com/shashankvemuri/economic-dashboard) | Macro and stock market dashboard with Python/Dash | Macro indicator layout, Dash callbacks, multi-panel economic dashboard structure. |
| [webn3ewbie/OpenBBxStreamlit](https://github.com/webn3ewbie/OpenBBxStreamlit) | Streamlit financial dashboard using OpenBB | Multi-asset navigation, market dashboard sections, sidebar-driven workflows. |
| [brad-darksbian/fed_dashboard](https://github.com/brad-darksbian/fed_dashboard) | Federal economic data dashboard with Dash/Plotly | FRED-style economic series comparison and clean time-series UX. |
| [SunFish98/MacroDashboard](https://github.com/SunFish98/MacroDashboard) | Self-hosted macro monitoring dashboard | Terminal-style market monitor, regime indicators, top-level macro summary cards. |

## Commodity / Multi-Asset Specific References

| Repo | Focus | What To Borrow |
| --- | --- | --- |
| [workjay-it/commodity-market-dashboard](https://github.com/workjay-it/commodity-market-dashboard) | Commodity price analytics with DuckDB and Streamlit | ETL-to-dashboard pattern, rolling averages, SQL-backed analytics. |
| [HugoCretois/All-in-One-Market-Dashboard](https://github.com/HugoCretois/All-in-One-Market-Dashboard) | Equities, bonds, commodities, FX, macro drivers | Multi-asset framing and regime/macro-driver grouping. |
| [Shimirnahsherin-235/Stock-Analysis](https://github.com/Shimirnahsherin-235/Stock-Analysis) | Stock and commodity price dashboard with Streamlit | Lightweight Streamlit market dashboard structure. |
| [jj-acton/Financial-Dashboard](https://github.com/jj-acton/Financial-Dashboard) | Streamlit finance dashboard including commodity forecasting | Forecasting panel ideas and mixed tool dashboard sections. |
| [DeepakM2012/commodity-price-forecasting-dashboard](https://github.com/DeepakM2012/commodity-price-forecasting-dashboard) | Commodity prices, volatility, ARIMA forecasting | Forecasting/volatility panel inspiration, not necessarily production-grade. |

## FRED / Economic Indicator References

| Repo | Focus | What To Borrow |
| --- | --- | --- |
| [tarang-tj/economic-pulse-dashboard](https://github.com/tarang-tj/economic-pulse-dashboard) | FRED pipeline, trend detection, Streamlit dashboard | Simple macro ETL pipeline and indicator trend status logic. |
| [omarnasirii/economic-insights-dashboard](https://github.com/omarnasirii/economic-insights-dashboard) | GDP, CPI, unemployment via FRED API | Macro sidebar filters and SQLite-backed persistence ideas. |
| [OpalIrene/OpalsEconDashboard](https://github.com/OpalIrene/OpalsEconDashboard) | U.S. economic indicators, Streamlit, Plotly, FRED | Long-history macro chart layout. |
| [len1/Country-Economic-Indicators](https://github.com/len1/Country-Economic-Indicators) | Country economic indicators with FRED API | Country/indicator selector workflow. |

## How This Maps To Our Corn / Soybean Dashboard

Recommended ideas to adopt:

1. Use an Overview page with 4-6 KPI cards and 2-4 dense charts.
2. Keep source notes close to the chart, especially for USDA/WASDE/NASS/EIA.
3. Separate data layers: raw -> clean -> mart -> dashboard.
4. Keep commodity, state, and crop year filters global.
5. Add a "regime/status" layer: bullish/bearish/neutral based on stocks-to-use,
   crop condition, export pace, drought severity, and ethanol/crush demand.
6. Add a data dictionary page so users know exactly what each metric means.

