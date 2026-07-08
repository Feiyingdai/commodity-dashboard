# U.S. Corn and Soybean Dashboard

This project is a Streamlit dashboard and data pipeline for monitoring U.S.
corn and soybean fundamentals. It combines USDA/NASS production and stocks,
WASDE balance sheets, crop progress and condition, drought, ethanol, corn FSI,
and soybean crush data.

The dashboard is designed around a few practical research questions:

- Is the balance sheet getting tighter or looser?
- Which production, demand, stock, and weather signals are driving that view?
- How do latest WASDE estimates compare with prior WASDE vintages?
- Are stocks and actual demand indicators confirming or challenging the balance
  sheet?

## Project Structure

```text
.
├── dashboard/
│   └── app.py                       # Streamlit dashboard
├── data/
│   ├── clean/                       # Clean source-shaped tables
│   ├── mart/                        # Dashboard-ready tables
│   └── raw/                         # Raw downloads, ignored by git
├── data_pipeline/
│   ├── fetch_us_grains_data.py      # Fetch raw and clean source data
│   └── build_marts.py               # Build dashboard mart tables
├── tableau/                         # Tableau notes and package builder
├── .env.example                     # API key template
├── .gitignore
└── requirements.txt
```

## Quick Start

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Run the dashboard:

```bash
streamlit run dashboard/app.py
```

The app reads from `data/mart/*.csv`. If `data/mart/` is included in the repo,
the dashboard can run without API keys. API keys are only needed when you want
to refresh or rebuild the data from source.

## API Keys

Create a local `.env` file:

```bash
cp .env.example .env
```

Then fill in:

```bash
NASS_API_KEY=your_nass_key
EIA_API_KEY=your_eia_key
AMS_API_KEY=your_ams_mymarketnews_key
```

- `NASS_API_KEY` is used for USDA NASS QuickStats data such as supply, crop
  progress, crop condition, stocks, corn FSI, and soybean crush.
- `EIA_API_KEY` is used for weekly ethanol production and stocks.
- `AMS_API_KEY` is optional and only needed if you automate USDA AMS export
  inspection data in a future workflow.

`.env` is ignored by git. Do not commit API keys.

## Data Sources

| Module | Source | API key |
| --- | --- | --- |
| Supply, acreage, yield, crop progress, crop condition, stocks | USDA NASS QuickStats | `NASS_API_KEY` |
| WASDE balance sheet | USDA WASDE public files | No key |
| Drought | U.S. Drought Monitor data services | No key |
| Corn ethanol production and stocks | EIA Open Data | `EIA_API_KEY` |
| Corn FSI | USDA NASS QuickStats | `NASS_API_KEY` |
| Soybean crush | USDA NASS QuickStats | `NASS_API_KEY` |
| Export sales | USDA FAS export sales pages | No key for current historical fetcher |
| Export inspections | USDA AMS/FGIS Market News | Optional `AMS_API_KEY` |

## Refreshing Data

Fetch raw and clean data:

```bash
python data_pipeline/fetch_us_grains_data.py --start-year 2015
```

Optional flags:

```bash
python data_pipeline/fetch_us_grains_data.py --start-year 2015 --wasde-historical-years 1
python data_pipeline/fetch_us_grains_data.py --start-year 2015 --fetch-fas-export-sales
```

Build dashboard mart tables:

```bash
python data_pipeline/build_marts.py
```

The fetcher writes raw downloads and clean tables under `data/`. The mart
builder writes dashboard-ready CSVs under `data/mart/`.

## Data Files

Current clean outputs include:

- `data/clean/nass_annual_supply.csv`
- `data/clean/nass_crop_progress_condition.csv`
- `data/clean/nass_stocks.csv`
- `data/clean/nass_corn_fsi_monthly.csv`
- `data/clean/nass_soybean_crush_monthly.csv`
- `data/clean/wasde_us_balance_long.csv`
- `data/clean/wasde_us_balance_wide.csv`
- `data/clean/usdm_drought_state.csv`
- `data/clean/eia_ethanol.csv`

Current mart outputs include:

- `data/mart/mart_supply_annual.csv`
- `data/mart/mart_crop_progress_weekly.csv`
- `data/mart/mart_crop_condition_weekly.csv`
- `data/mart/mart_stocks_quarterly.csv`
- `data/mart/mart_wasde_balance.csv`
- `data/mart/mart_drought_weekly.csv`
- `data/mart/mart_ethanol_weekly.csv`
- `data/mart/mart_corn_fsi_monthly.csv`
- `data/mart/mart_export_sales_weekly.csv`
- `data/mart/mart_export_inspections_weekly.csv`
- `data/mart/mart_soybean_crush_monthly.csv`
- `data/mart/mart_feed_residual_quarterly.csv`

`data/mart/` is small enough to commit and is recommended for GitHub so other
users can open the dashboard without requesting API keys. `data/clean/` is
optional: commit it if you want others to rebuild marts without fetching source
data; leave it out if you only want to ship the dashboard snapshot.

`data/raw/` is ignored by git because raw downloads are larger, noisier, and can
be regenerated.

## GitHub Notes

This repository should not commit local secrets or private reference files.
The current `.gitignore` excludes:

- `.env`
- `.venv/`
- `data/raw/`
- `.DS_Store`

Before the first GitHub push, initialize git from the project root:

```bash
git init
git status
git add .
git commit -m "Initial commodity dashboard"
```

## Notes

The dashboard currently treats WASDE release rows as vintages. For example,
`2026/27 projection Jun` is compared against the prior available WASDE row,
such as `2026/27 projection May`, when marking Balance Cockpit signals.

Some actual-demand marts, especially export sales and export inspections, are
optional and may be empty until the corresponding source files are added.
