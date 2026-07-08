#!/usr/bin/env python3
"""Create a Tableau-ready data package from dashboard mart tables."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pandas as pd


MART_TABLES = [
    "mart_supply_annual.csv",
    "mart_crop_progress_weekly.csv",
    "mart_crop_condition_weekly.csv",
    "mart_stocks_quarterly.csv",
    "mart_wasde_balance.csv",
    "mart_drought_weekly.csv",
    "mart_ethanol_weekly.csv",
    "mart_corn_fsi_monthly.csv",
    "mart_export_sales_weekly.csv",
    "mart_export_inspections_weekly.csv",
    "mart_soybean_crush_monthly.csv",
    "mart_feed_residual_quarterly.csv",
]


FIELD_DESCRIPTIONS = {
    "commodity": "Commodity code. CORN or SOYBEANS.",
    "year": "Crop year / calendar year as reported by source.",
    "state_alpha": "Two-letter U.S. state abbreviation. US means national total.",
    "state_name": "State display name from NASS.",
    "agg_level": "NASS aggregation level, usually NATIONAL or STATE.",
    "week_ending": "Weekly NASS crop progress / condition report date.",
    "stage": "Crop progress stage, normalized from NASS unit_desc.",
    "pct": "Percent complete for crop progress stage.",
    "good_excellent": "Crop condition percent rated good plus excellent.",
    "poor_very_poor": "Crop condition percent rated poor plus very poor.",
    "condition_index_0_100": "Weighted condition score scaled 0-100.",
    "stock_date": "Quarterly NASS grain stock date.",
    "stocks_mbu": "Grain stocks in million bushels.",
    "on_farm_stocks_mbu": "NASS on-farm grain stocks in million bushels.",
    "off_farm_stocks_mbu": "NASS off-farm grain stocks in million bushels.",
    "on_farm_share_pct": "On-farm stocks divided by total stocks, in percent.",
    "off_farm_share_pct": "Off-farm stocks divided by total stocks, in percent.",
    "report_month": "WASDE report month parsed from latest report.",
    "marketing_year": "WASDE marketing year, e.g. 2026/27.",
    "vintage": "WASDE vintage column, e.g. current, May, Jun.",
    "production": "WASDE production in million bushels.",
    "exports": "WASDE exports in million bushels.",
    "ending_stocks": "WASDE ending stocks in million bushels.",
    "stocks_to_use_pct": "WASDE stocks-to-use ratio in percent.",
    "mapdate": "U.S. Drought Monitor map date.",
    "d1_plus": "Percent area in D1 or worse drought.",
    "d2_plus": "Percent area in D2 or worse drought.",
    "dsci": "Drought Severity and Coverage Index proxy from cumulative drought buckets.",
    "period": "EIA weekly period date.",
    "ethanol_production_kbd": "Weekly U.S. ethanol production in thousand barrels per day.",
    "ethanol_stocks_kbbl": "Weekly U.S. ethanol stocks in thousand barrels.",
    "implied_corn_use_mbu": "Estimated weekly corn use for ethanol in million bushels.",
    "fsi_use_mbu": "Monthly corn food, seed, and industrial use from NASS, in million bushels.",
    "alcohol_use_mbu": "Monthly corn used for alcohol products, in million bushels.",
    "fuel_alcohol_use_mbu": "Monthly corn used for fuel alcohol, in million bushels.",
    "beverage_alcohol_use_mbu": "Monthly corn used for beverage alcohol, in million bushels.",
    "industrial_alcohol_use_mbu": "Monthly corn used for industrial alcohol, in million bushels.",
    "other_products_use_mbu": "Monthly corn used for other products excluding alcohol, in million bushels.",
    "other_fsi_use_mbu": "Monthly corn FSI excluding fuel alcohol, in million bushels.",
    "current_week_exports_mbu": "Current-week exports from USDA FAS export sales, in million bushels.",
    "accumulated_exports_mbu": "Marketing-year-to-date exports from USDA FAS export sales, in million bushels.",
    "outstanding_sales_mbu": "Outstanding export sales, in million bushels.",
    "net_sales_mbu": "Weekly net export sales, in million bushels.",
    "total_commitments_mbu": "Accumulated exports plus outstanding sales, in million bushels.",
    "weekly_inspections_mbu": "Weekly export inspections, in million bushels.",
    "accumulated_inspections_mbu": "Marketing-year-to-date export inspections, in million bushels.",
    "month": "Monthly period date.",
    "soybean_crush_mbu": "Monthly soybean crush, in million bushels.",
    "soybean_oil_stocks_mlb": "Soybean oil stocks, in million pounds.",
    "soybean_meal_production_short_tons": "Soybean meal production, in short tons.",
    "quarter": "Marketing-year quarter number.",
    "quarter_label": "Marketing-year quarter label.",
    "quarter_start": "Beginning stock date for the disappearance quarter.",
    "quarter_end": "Ending stock date for the disappearance quarter.",
    "beginning_stocks_mbu": "Beginning stocks for the quarter, in million bushels.",
    "ending_stocks_mbu": "Ending stocks for the quarter, in million bushels.",
    "production_added_mbu": "Production added to supply during the quarter, in million bushels.",
    "total_disappearance_mbu": "Quarterly disappearance implied by stocks and production, in million bushels.",
    "ethanol_use_mbu": "EIA-implied corn use for ethanol during the quarter, in million bushels.",
    "other_fsi_use_mbu": "NASS corn FSI excluding fuel alcohol during the quarter, in million bushels.",
    "exports_mbu": "FAS weekly exports summed during the quarter, in million bushels.",
    "export_inspections_mbu": "Export inspections during the quarter, in million bushels.",
    "known_non_feed_use_mbu": "Known non-feed components captured in the mart, in million bushels.",
    "residual_after_known_uses_mbu": "Total disappearance minus currently captured known uses.",
    "feed_residual_implied_mbu": "Implied feed and residual when all required quarterly components are available.",
    "wasde_feed_residual_annual_mbu": "Latest WASDE annual feed and residual for the marketing year.",
    "coverage_status": "Notes whether the quarterly disappearance bridge has complete component coverage.",
}


CALCULATED_FIELDS = [
    {
        "name": "WASDE Latest Vintage",
        "table": "mart_wasde_balance",
        "formula": "[column_order] = { FIXED [commodity] : MAX([column_order]) }",
        "description": "Keeps the latest vintage row for each selected commodity.",
    },
    {
        "name": "Stocks-to-Use Label",
        "table": "mart_wasde_balance",
        "formula": 'STR(ROUND([stocks_to_use_pct], 1)) + "%"',
        "description": "Display label for stocks-to-use KPI.",
    },
    {
        "name": "Good Excellent Label",
        "table": "mart_crop_condition_weekly",
        "formula": 'STR(ROUND([good_excellent], 1)) + "%"',
        "description": "Display label for crop condition KPI.",
    },
    {
        "name": "Latest Week",
        "table": "mart_crop_condition_weekly",
        "formula": "[week_ending] = { FIXED [commodity], [state_alpha] : MAX([week_ending]) }",
        "description": "Flags the latest available crop condition week by commodity and state.",
    },
    {
        "name": "Latest Drought Week",
        "table": "mart_drought_weekly",
        "formula": "[mapdate] = { FIXED [state_alpha] : MAX([mapdate]) }",
        "description": "Flags the latest available drought week by state.",
    },
]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def copy_mart_tables(mart_dir: Path, tables_dir: Path) -> None:
    for table in MART_TABLES:
        src = mart_dir / table
        if not src.exists():
            raise FileNotFoundError(f"Missing mart table: {src}")
        shutil.copy2(src, tables_dir / table)


def build_dim_commodity(tables_dir: Path) -> Path:
    df = pd.DataFrame(
        [
            {"commodity": "CORN", "commodity_label": "Corn", "commodity_color": "#D2A10D"},
            {
                "commodity": "SOYBEANS",
                "commodity_label": "Soybeans",
                "commodity_color": "#2F8F5B",
            },
        ]
    )
    out = tables_dir / "dim_commodity.csv"
    df.to_csv(out, index=False)
    return out


def build_dim_state(mart_dir: Path, tables_dir: Path) -> Path:
    frames = []
    for table in ["mart_supply_annual.csv", "mart_crop_condition_weekly.csv", "mart_stocks_quarterly.csv"]:
        path = mart_dir / table
        df = pd.read_csv(path, usecols=lambda col: col in {"state_alpha", "state_name"})
        frames.append(df)
    states = pd.concat(frames, ignore_index=True).dropna(subset=["state_alpha"])
    states = states.drop_duplicates("state_alpha").sort_values("state_alpha")
    states["is_national"] = states["state_alpha"].eq("US")
    out = tables_dir / "dim_state.csv"
    states.to_csv(out, index=False)
    return out


def build_data_dictionary(tables_dir: Path, output_dir: Path) -> Path:
    rows = []
    for path in sorted(tables_dir.glob("*.csv")):
        df = pd.read_csv(path, nrows=0)
        table = path.stem
        for field in df.columns:
            rows.append(
                {
                    "table": table,
                    "field": field,
                    "description": FIELD_DESCRIPTIONS.get(field, ""),
                }
            )
    out = output_dir / "tableau_data_dictionary.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    return out


def build_calculated_fields(output_dir: Path) -> Path:
    out = output_dir / "tableau_calculated_fields.csv"
    pd.DataFrame(CALCULATED_FIELDS).to_csv(out, index=False)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mart-dir", type=Path, default=Path("data/mart"))
    parser.add_argument("--output-dir", type=Path, default=Path("tableau/tableau_data"))
    args = parser.parse_args()

    tables_dir = args.output_dir / "tables"
    ensure_dir(tables_dir)

    copy_mart_tables(args.mart_dir, tables_dir)
    build_dim_commodity(tables_dir)
    build_dim_state(args.mart_dir, tables_dir)
    dictionary_path = build_data_dictionary(tables_dir, args.output_dir)
    calc_path = build_calculated_fields(args.output_dir)

    print("Tableau package created")
    print("-----------------------")
    print(f"Tables: {tables_dir}")
    print(f"Data dictionary: {dictionary_path}")
    print(f"Calculated fields: {calc_path}")
    for path in sorted(tables_dir.glob("*.csv")):
        rows = sum(1 for _ in path.open("r", encoding="utf-8")) - 1
        print(f"OK {path.name}: {rows:,} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
