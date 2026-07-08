#!/usr/bin/env python3
"""Build dashboard-ready mart tables from cleaned corn/soybean CSVs.

Inputs:
    data/clean/*.csv

Outputs:
    data/mart/*.csv

The clean layer keeps source-shaped data. The mart layer reshapes it into
tables that are easier to use in Streamlit, Plotly, Tableau, Power BI, etc.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd


ANNUAL_METRIC_MAP = {
    "AREA PLANTED": "planted_acres",
    "AREA HARVESTED": "harvested_acres",
    "YIELD": "yield_bu_per_acre",
    "PRODUCTION": "production_bu",
}

CONDITION_MAP = {
    "PCT EXCELLENT": "excellent",
    "PCT GOOD": "good",
    "PCT FAIR": "fair",
    "PCT POOR": "poor",
    "PCT VERY POOR": "very_poor",
}

STOCK_MONTH_MAP = {
    "FIRST OF MAR": 3,
    "FIRST OF JUN": 6,
    "FIRST OF SEP": 9,
    "FIRST OF DEC": 12,
}

STOCK_STORAGE_POSITION_MAP = {
    "CORN, GRAIN - STOCKS, MEASURED IN BU": "total",
    "CORN, ON FARM, GRAIN - STOCKS, MEASURED IN BU": "on_farm",
    "CORN, OFF FARM, GRAIN - STOCKS, MEASURED IN BU": "off_farm",
    "SOYBEANS - STOCKS, MEASURED IN BU": "total",
    "SOYBEANS, ON FARM - STOCKS, MEASURED IN BU": "on_farm",
    "SOYBEANS, OFF FARM - STOCKS, MEASURED IN BU": "off_farm",
}

CORN_FSI_METRIC_MAP = {
    "CORN, FOR ALCOHOL & OTHER PRODUCTS - USAGE, MEASURED IN BU": "fsi_use_mbu",
    "CORN, FOR ALCOHOL - USAGE, MEASURED IN BU": "alcohol_use_mbu",
    "CORN, FOR BEVERAGE ALCOHOL - USAGE, MEASURED IN BU": "beverage_alcohol_use_mbu",
    "CORN, FOR FUEL ALCOHOL - USAGE, MEASURED IN BU": "fuel_alcohol_use_mbu",
    "CORN, FOR INDUSTRIAL ALCOHOL - USAGE, MEASURED IN BU": "industrial_alcohol_use_mbu",
    "CORN, FOR OTHER PRODUCTS (EXCL ALCOHOL) - USAGE, MEASURED IN BU": "other_products_use_mbu",
}

SOYBEAN_CRUSH_METRIC_MAP = {
    "SOYBEANS - CRUSHED, MEASURED IN TONS": "soybean_crush_short_tons",
    "CAKE & MEAL, SOYBEAN - PRODUCTION, MEASURED IN TONS": "soybean_meal_production_short_tons",
    "OIL, SOYBEAN, CRUDE - PRODUCTION, MEASURED IN LB": "soybean_oil_production_lb",
    "OIL, SOYBEAN, CRUDE - STOCKS, MEASURED IN LB": "soybean_oil_stocks_lb",
}

CORN_FSI_MONTHLY_COLUMNS = [
    "commodity",
    "month",
    "marketing_year",
    "fsi_use_mbu",
    "alcohol_use_mbu",
    "fuel_alcohol_use_mbu",
    "beverage_alcohol_use_mbu",
    "industrial_alcohol_use_mbu",
    "other_products_use_mbu",
    "other_fsi_use_mbu",
    "source",
]

EXPORT_SALES_COLUMNS = [
    "commodity",
    "marketing_year",
    "week_ending",
    "country",
    "current_week_exports_mbu",
    "accumulated_exports_mbu",
    "outstanding_sales_mbu",
    "gross_new_sales_mbu",
    "net_sales_mbu",
    "total_commitments_mbu",
    "source",
]

EXPORT_INSPECTIONS_COLUMNS = [
    "commodity",
    "marketing_year",
    "week_ending",
    "weekly_inspections_mbu",
    "accumulated_inspections_mbu",
    "source",
]

SOYBEAN_CRUSH_MONTHLY_COLUMNS = [
    "commodity",
    "month",
    "marketing_year",
    "soybean_crush_mbu",
    "soybean_oil_stocks_mlb",
    "soybean_meal_production_short_tons",
    "source",
]

FEED_RESIDUAL_QUARTERLY_COLUMNS = [
    "commodity",
    "marketing_year",
    "crop_year",
    "quarter",
    "quarter_label",
    "quarter_start",
    "quarter_end",
    "stock_date",
    "prev_stock_date",
    "beginning_stocks_mbu",
    "ending_stocks_mbu",
    "production_added_mbu",
    "total_disappearance_mbu",
    "ethanol_use_mbu",
    "other_fsi_use_mbu",
    "exports_mbu",
    "export_inspections_mbu",
    "soybean_crush_mbu",
    "known_non_feed_use_mbu",
    "residual_after_known_uses_mbu",
    "feed_residual_implied_mbu",
    "wasde_feed_residual_annual_mbu",
    "coverage_status",
    "source",
]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_empty_mart(mart_dir: Path, name: str, columns: list[str]) -> Path:
    out_path = mart_dir / name
    pd.DataFrame(columns=columns).to_csv(out_path, index=False)
    return out_path


def read_optional_clean(
    clean_dir: Path,
    names: list[str],
    parse_dates: list[str] | None = None,
) -> pd.DataFrame:
    for name in names:
        path = clean_dir / name
        if path.exists():
            df = pd.read_csv(path)
            for col in parse_dates or []:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
            return df
    return pd.DataFrame()


def pick_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lower_lookup = {col.lower(): col for col in df.columns}
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
        lower_candidate = candidate.lower()
        if lower_candidate in lower_lookup:
            return lower_lookup[lower_candidate]
    return None


def assign_first_available(
    out: pd.DataFrame,
    df: pd.DataFrame,
    output_col: str,
    candidates: list[str],
) -> None:
    source_col = pick_column(df, candidates)
    out[output_col] = df[source_col] if source_col else pd.NA


def assign_mbu(
    out: pd.DataFrame,
    df: pd.DataFrame,
    output_col: str,
    mbu_candidates: list[str],
    bu_candidates: list[str] | None = None,
) -> None:
    mbu_col = pick_column(df, mbu_candidates)
    if mbu_col:
        out[output_col] = pd.to_numeric(df[mbu_col], errors="coerce")
        return

    bu_col = pick_column(df, bu_candidates or [])
    if bu_col:
        out[output_col] = pd.to_numeric(df[bu_col], errors="coerce") / 1_000_000
        return

    out[output_col] = pd.NA


def normalize_commodity(value: object) -> object:
    if pd.isna(value):
        return pd.NA
    text = str(value).strip().upper()
    if "CORN" in text:
        return "CORN"
    if "SOY" in text:
        return "SOYBEANS"
    return text


def marketing_year_from_date(value: object) -> str | None:
    date_value = pd.to_datetime(value, errors="coerce")
    if pd.isna(date_value):
        return None
    start_year = date_value.year if date_value.month >= 9 else date_value.year - 1
    return f"{start_year}/{str(start_year + 1)[-2:]}"


def quickstats_month_frame(df: pd.DataFrame) -> pd.Series:
    years = pd.to_numeric(df["year"], errors="coerce")
    months = pd.to_numeric(df["begin_code"], errors="coerce")
    dates = {
        idx: pd.Timestamp(year=int(year), month=int(month), day=1)
        for idx, year, month in zip(df.index, years, months)
        if pd.notna(year) and pd.notna(month) and 1 <= int(month) <= 12
    }
    return pd.Series(dates, index=df.index, dtype="datetime64[ns]")


def normalize_stage(unit_desc: str) -> str:
    stage = unit_desc.replace("PCT ", "").strip().lower()
    stage = re.sub(r"[^a-z0-9]+", "_", stage).strip("_")
    return stage


def reference_score(reference_period: object) -> int:
    """Prefer final YEAR when load_time ties, otherwise prefer later forecasts."""
    text = "" if pd.isna(reference_period) else str(reference_period).upper()
    scores = {
        "YEAR": 100,
        "YEAR - NOV FORECAST": 95,
        "YEAR - OCT FORECAST": 90,
        "YEAR - SEP FORECAST": 85,
        "YEAR - AUG FORECAST": 80,
        "YEAR - JUN ACREAGE": 75,
        "YEAR - MAR ACREAGE": 70,
        "YEAR - OCT ACREAGE": 65,
        "YEAR - AUG ACREAGE": 60,
    }
    return scores.get(text, 0)


def read_clean(clean_dir: Path, name: str, **kwargs) -> pd.DataFrame:
    path = clean_dir / name
    if not path.exists():
        raise FileNotFoundError(f"Missing required clean table: {path}")
    return pd.read_csv(path, **kwargs)


def build_supply_annual(clean_dir: Path, mart_dir: Path) -> Path:
    df = read_clean(clean_dir, "nass_annual_supply.csv", parse_dates=["load_time"])
    df = df.copy()
    df["commodity"] = df["commodity_desc"]
    df["agg_level"] = df["agg_level_desc"]
    df["metric"] = df["statisticcat_desc"].map(ANNUAL_METRIC_MAP)
    df = df[df["metric"].notna()].copy()
    df["ref_score"] = df["reference_period_desc"].map(reference_score)

    keys = ["commodity", "year", "agg_level", "state_alpha", "state_name", "metric"]
    latest = (
        df.sort_values(keys + ["load_time", "ref_score"])
        .drop_duplicates(keys, keep="last")
        .copy()
    )

    wide = (
        latest.pivot_table(
            index=["commodity", "year", "agg_level", "state_alpha", "state_name"],
            columns="metric",
            values="value_num",
            aggfunc="first",
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )

    max_load = (
        latest.groupby(["commodity", "year", "agg_level", "state_alpha", "state_name"])[
            "load_time"
        ]
        .max()
        .reset_index(name="latest_load_time")
    )
    wide = wide.merge(
        max_load,
        on=["commodity", "year", "agg_level", "state_alpha", "state_name"],
        how="left",
    )

    if "planted_acres" in wide:
        wide["planted_acres_mil"] = wide["planted_acres"] / 1_000_000
    if "harvested_acres" in wide:
        wide["harvested_acres_mil"] = wide["harvested_acres"] / 1_000_000
    if "production_bu" in wide:
        wide["production_mbu"] = wide["production_bu"] / 1_000_000

    preferred_cols = [
        "commodity",
        "year",
        "agg_level",
        "state_alpha",
        "state_name",
        "planted_acres",
        "planted_acres_mil",
        "harvested_acres",
        "harvested_acres_mil",
        "yield_bu_per_acre",
        "production_bu",
        "production_mbu",
        "latest_load_time",
    ]
    wide = wide[[col for col in preferred_cols if col in wide.columns]]
    wide = wide.sort_values(["commodity", "agg_level", "state_alpha", "year"])

    out_path = mart_dir / "mart_supply_annual.csv"
    wide.to_csv(out_path, index=False)
    return out_path


def build_crop_progress_weekly(clean_dir: Path, mart_dir: Path) -> Path:
    df = read_clean(
        clean_dir,
        "nass_crop_progress_condition.csv",
        parse_dates=["week_ending", "load_time"],
    )
    progress = df[df["statisticcat_desc"].eq("PROGRESS")].copy()
    progress["commodity"] = progress["commodity_desc"]
    progress["agg_level"] = progress["agg_level_desc"]
    progress["stage"] = progress["unit_desc"].map(normalize_stage)
    progress = progress.rename(columns={"value_num": "pct"})

    cols = [
        "commodity",
        "year",
        "week_ending",
        "agg_level",
        "state_alpha",
        "state_name",
        "stage",
        "pct",
        "load_time",
    ]
    progress = progress[cols].sort_values(
        ["commodity", "stage", "agg_level", "state_alpha", "week_ending"]
    )

    out_path = mart_dir / "mart_crop_progress_weekly.csv"
    progress.to_csv(out_path, index=False)
    return out_path


def build_crop_condition_weekly(clean_dir: Path, mart_dir: Path) -> Path:
    df = read_clean(
        clean_dir,
        "nass_crop_progress_condition.csv",
        parse_dates=["week_ending", "load_time"],
    )
    cond = df[df["statisticcat_desc"].eq("CONDITION")].copy()
    cond["commodity"] = cond["commodity_desc"]
    cond["agg_level"] = cond["agg_level_desc"]
    cond["condition"] = cond["unit_desc"].map(CONDITION_MAP)
    cond = cond[cond["condition"].notna()].copy()

    idx = [
        "commodity",
        "year",
        "week_ending",
        "agg_level",
        "state_alpha",
        "state_name",
    ]
    wide = (
        cond.pivot_table(index=idx, columns="condition", values="value_num", aggfunc="first")
        .reset_index()
        .rename_axis(None, axis=1)
    )
    max_load = cond.groupby(idx)["load_time"].max().reset_index(name="load_time")
    wide = wide.merge(max_load, on=idx, how="left")

    for col in ("excellent", "good", "fair", "poor", "very_poor"):
        if col not in wide.columns:
            wide[col] = pd.NA

    wide["good_excellent"] = wide["good"] + wide["excellent"]
    wide["poor_very_poor"] = wide["poor"] + wide["very_poor"]
    weighted = (
        5 * wide["excellent"]
        + 4 * wide["good"]
        + 3 * wide["fair"]
        + 2 * wide["poor"]
        + wide["very_poor"]
    )
    wide["condition_score_1_5"] = weighted / 100
    wide["condition_index_0_100"] = weighted / 5

    cols = idx + [
        "excellent",
        "good",
        "fair",
        "poor",
        "very_poor",
        "good_excellent",
        "poor_very_poor",
        "condition_score_1_5",
        "condition_index_0_100",
        "load_time",
    ]
    wide = wide[cols].sort_values(["commodity", "agg_level", "state_alpha", "week_ending"])

    out_path = mart_dir / "mart_crop_condition_weekly.csv"
    wide.to_csv(out_path, index=False)
    return out_path


def stock_date(row: pd.Series) -> pd.Timestamp:
    month = STOCK_MONTH_MAP.get(row["reference_period_desc"])
    if month is None:
        return pd.NaT
    return pd.Timestamp(year=int(row["year"]), month=month, day=1)


def build_stocks_quarterly(clean_dir: Path, mart_dir: Path) -> Path:
    df = read_clean(clean_dir, "nass_stocks.csv", parse_dates=["load_time"])
    stocks = df.copy()
    stocks["commodity"] = stocks["commodity_desc"]
    stocks["agg_level"] = stocks["agg_level_desc"]
    stocks["storage_position"] = stocks["short_desc"].map(STOCK_STORAGE_POSITION_MAP)
    stocks["stock_date"] = stocks.apply(stock_date, axis=1)
    stocks = stocks[stocks["stock_date"].notna() & stocks["storage_position"].notna()].copy()
    stocks = stocks.rename(columns={"value_num": "stocks_bu"})
    stocks["stock_month"] = stocks["stock_date"].dt.month

    idx = [
        "commodity",
        "year",
        "stock_date",
        "stock_month",
        "reference_period_desc",
        "agg_level",
        "state_alpha",
        "state_name",
    ]
    wide = (
        stocks.pivot_table(
            index=idx,
            columns="storage_position",
            values="stocks_bu",
            aggfunc="first",
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )
    max_load = stocks.groupby(idx)["load_time"].max().reset_index(name="load_time")
    wide = wide.merge(max_load, on=idx, how="left")

    for col in ("total", "on_farm", "off_farm"):
        if col not in wide.columns:
            wide[col] = pd.NA

    wide["stocks_bu"] = wide["total"]
    wide["on_farm_stocks_bu"] = wide["on_farm"]
    wide["off_farm_stocks_bu"] = wide["off_farm"]
    wide["stocks_bu"] = wide["stocks_bu"].fillna(
        wide["on_farm_stocks_bu"] + wide["off_farm_stocks_bu"]
    )

    wide["stocks_mbu"] = wide["stocks_bu"] / 1_000_000
    wide["on_farm_stocks_mbu"] = wide["on_farm_stocks_bu"] / 1_000_000
    wide["off_farm_stocks_mbu"] = wide["off_farm_stocks_bu"] / 1_000_000
    wide["on_farm_share_pct"] = wide["on_farm_stocks_mbu"] / wide["stocks_mbu"] * 100
    wide["off_farm_share_pct"] = wide["off_farm_stocks_mbu"] / wide["stocks_mbu"] * 100

    cols = idx + [
        "stocks_bu",
        "stocks_mbu",
        "on_farm_stocks_bu",
        "on_farm_stocks_mbu",
        "off_farm_stocks_bu",
        "off_farm_stocks_mbu",
        "on_farm_share_pct",
        "off_farm_share_pct",
        "load_time",
    ]
    stocks = wide[cols].sort_values(["commodity", "agg_level", "state_alpha", "stock_date"])

    out_path = mart_dir / "mart_stocks_quarterly.csv"
    stocks.to_csv(out_path, index=False)
    return out_path


def build_wasde_balance(clean_dir: Path, mart_dir: Path) -> Path:
    df = read_clean(clean_dir, "wasde_us_balance_wide.csv")
    keep = [
        "report_month",
        "commodity",
        "marketing_year",
        "estimate_type",
        "vintage",
        "column_order",
        "area_planted",
        "area_harvested",
        "yield_per_harvested_acre",
        "production",
        "imports",
        "supply_total",
        "feed_and_residual",
        "food_seedand_industrial",
        "ethanol_and_by_products",
        "crushings",
        "domestic_total",
        "exports",
        "use_total",
        "ending_stocks",
        "stocks_to_use",
        "avg_farmprice_bu",
    ]
    out = df[[col for col in keep if col in df.columns]].copy()
    if "stocks_to_use" in out:
        out["stocks_to_use_pct"] = out["stocks_to_use"] * 100
    out = out.sort_values(["commodity", "column_order"])

    out_path = mart_dir / "mart_wasde_balance.csv"
    out.to_csv(out_path, index=False)
    return out_path


def build_drought_weekly(clean_dir: Path, mart_dir: Path) -> Path:
    df = read_clean(
        clean_dir,
        "usdm_drought_state.csv",
        parse_dates=["mapdate", "validstart", "validend"],
    )
    drought = df.copy()
    for col in ("none", "d0", "d1", "d2", "d3", "d4"):
        drought[col] = pd.to_numeric(drought[col], errors="coerce")

    # USDM area percentages are cumulative: D1 means D1-or-worse, etc.
    drought["d0_plus"] = drought["d0"]
    drought["d1_plus"] = drought["d1"]
    drought["d2_plus"] = drought["d2"]
    drought["d3_plus"] = drought["d3"]
    drought["d4_plus"] = drought["d4"]
    drought["d0_only"] = drought["d0"] - drought["d1"]
    drought["d1_only"] = drought["d1"] - drought["d2"]
    drought["d2_only"] = drought["d2"] - drought["d3"]
    drought["d3_only"] = drought["d3"] - drought["d4"]
    drought["d4_only"] = drought["d4"]
    drought["dsci"] = drought["d0"] + drought["d1"] + drought["d2"] + drought["d3"] + drought["d4"]

    cols = [
        "mapdate",
        "state_alpha",
        "none",
        "d0",
        "d1",
        "d2",
        "d3",
        "d4",
        "d0_plus",
        "d1_plus",
        "d2_plus",
        "d3_plus",
        "d4_plus",
        "d0_only",
        "d1_only",
        "d2_only",
        "d3_only",
        "d4_only",
        "dsci",
        "validstart",
        "validend",
    ]
    drought = drought[cols].sort_values(["state_alpha", "mapdate"])

    out_path = mart_dir / "mart_drought_weekly.csv"
    drought.to_csv(out_path, index=False)
    return out_path


def build_ethanol_weekly(clean_dir: Path, mart_dir: Path) -> Path:
    df = read_clean(clean_dir, "eia_ethanol.csv", parse_dates=["period"])
    eia = df.copy()
    eia["value"] = pd.to_numeric(eia["value"], errors="coerce")
    wide = (
        eia.pivot_table(index="period", columns="metric", values="value", aggfunc="first")
        .reset_index()
        .rename_axis(None, axis=1)
    )
    if "ethanol_production_kbd" in wide.columns:
        wide["implied_corn_use_mbu"] = (
            wide["ethanol_production_kbd"] * 1_000 * 7 * 42 / 2.8 / 1_000_000
        )
    wide = wide.sort_values("period")

    out_path = mart_dir / "mart_ethanol_weekly.csv"
    wide.to_csv(out_path, index=False)
    return out_path


def build_export_sales_weekly(clean_dir: Path, mart_dir: Path) -> Path:
    """Standardize optional USDA FAS export-sales data if a clean file exists."""
    df = read_optional_clean(
        clean_dir,
        ["export_sales_weekly.csv", "fas_export_sales_weekly.csv"],
        parse_dates=["week_ending"],
    )
    if df.empty:
        return write_empty_mart(mart_dir, "mart_export_sales_weekly.csv", EXPORT_SALES_COLUMNS)

    out = pd.DataFrame(index=df.index)
    assign_first_available(out, df, "commodity", ["commodity", "commodity_desc", "crop", "product"])
    out["commodity"] = out["commodity"].map(normalize_commodity)
    assign_first_available(out, df, "marketing_year", ["marketing_year", "market_year"])
    assign_first_available(out, df, "week_ending", ["week_ending", "week_end", "report_date", "date"])
    out["week_ending"] = pd.to_datetime(out["week_ending"], errors="coerce")
    out["marketing_year"] = out["marketing_year"].fillna(out["week_ending"].map(marketing_year_from_date))
    assign_first_available(out, df, "country", ["country", "destination", "country_name"])
    assign_mbu(
        out,
        df,
        "current_week_exports_mbu",
        ["current_week_exports_mbu", "weekly_exports_mbu", "exports_mbu"],
        ["current_week_exports_bu", "weekly_exports_bu", "exports_bu"],
    )
    assign_mbu(
        out,
        df,
        "accumulated_exports_mbu",
        ["accumulated_exports_mbu", "accum_exports_mbu", "ytd_exports_mbu"],
        ["accumulated_exports_bu", "accum_exports_bu", "ytd_exports_bu"],
    )
    assign_mbu(
        out,
        df,
        "outstanding_sales_mbu",
        ["outstanding_sales_mbu", "outstanding_mbu"],
        ["outstanding_sales_bu", "outstanding_bu"],
    )
    assign_mbu(
        out,
        df,
        "gross_new_sales_mbu",
        ["gross_new_sales_mbu", "gross_sales_mbu"],
        ["gross_new_sales_bu", "gross_sales_bu"],
    )
    assign_mbu(
        out,
        df,
        "net_sales_mbu",
        ["net_sales_mbu", "weekly_net_sales_mbu"],
        ["net_sales_bu", "weekly_net_sales_bu"],
    )
    assign_mbu(
        out,
        df,
        "total_commitments_mbu",
        ["total_commitments_mbu", "commitments_mbu"],
        ["total_commitments_bu", "commitments_bu"],
    )
    out["total_commitments_mbu"] = out["total_commitments_mbu"].fillna(
        out["accumulated_exports_mbu"] + out["outstanding_sales_mbu"]
    )
    out["source"] = "USDA FAS Export Sales"
    out = out[EXPORT_SALES_COLUMNS].dropna(subset=["commodity", "week_ending"])
    out = out.sort_values(["commodity", "marketing_year", "week_ending", "country"])

    out_path = mart_dir / "mart_export_sales_weekly.csv"
    out.to_csv(out_path, index=False)
    return out_path


def build_export_inspections_weekly(clean_dir: Path, mart_dir: Path) -> Path:
    """Standardize optional weekly export-inspection data if a clean file exists."""
    df = read_optional_clean(
        clean_dir,
        ["export_inspections_weekly.csv", "ams_export_inspections_weekly.csv"],
        parse_dates=["week_ending"],
    )
    if df.empty:
        return write_empty_mart(
            mart_dir,
            "mart_export_inspections_weekly.csv",
            EXPORT_INSPECTIONS_COLUMNS,
        )

    out = pd.DataFrame(index=df.index)
    assign_first_available(out, df, "commodity", ["commodity", "commodity_desc", "crop", "product"])
    out["commodity"] = out["commodity"].map(normalize_commodity)
    assign_first_available(out, df, "marketing_year", ["marketing_year", "market_year"])
    assign_first_available(out, df, "week_ending", ["week_ending", "week_end", "report_date", "date"])
    out["week_ending"] = pd.to_datetime(out["week_ending"], errors="coerce")
    out["marketing_year"] = out["marketing_year"].fillna(out["week_ending"].map(marketing_year_from_date))
    assign_mbu(
        out,
        df,
        "weekly_inspections_mbu",
        ["weekly_inspections_mbu", "inspections_mbu", "weekly_shipments_mbu"],
        ["weekly_inspections_bu", "inspections_bu", "weekly_shipments_bu"],
    )
    assign_mbu(
        out,
        df,
        "accumulated_inspections_mbu",
        ["accumulated_inspections_mbu", "ytd_inspections_mbu"],
        ["accumulated_inspections_bu", "ytd_inspections_bu"],
    )
    out["source"] = "USDA AMS/FGIS Export Inspections"
    out = out[EXPORT_INSPECTIONS_COLUMNS].dropna(subset=["commodity", "week_ending"])
    out = out.sort_values(["commodity", "marketing_year", "week_ending"])

    out_path = mart_dir / "mart_export_inspections_weekly.csv"
    out.to_csv(out_path, index=False)
    return out_path


def build_corn_fsi_monthly(clean_dir: Path, mart_dir: Path) -> Path:
    df = read_optional_clean(clean_dir, ["nass_corn_fsi_monthly.csv"])
    if df.empty:
        return write_empty_mart(
            mart_dir,
            "mart_corn_fsi_monthly.csv",
            CORN_FSI_MONTHLY_COLUMNS,
        )

    fsi = df.copy()
    fsi["metric"] = fsi["short_desc"].map(CORN_FSI_METRIC_MAP)
    fsi = fsi[fsi["metric"].notna()].copy()
    if fsi.empty:
        return write_empty_mart(
            mart_dir,
            "mart_corn_fsi_monthly.csv",
            CORN_FSI_MONTHLY_COLUMNS,
        )

    fsi["month"] = quickstats_month_frame(fsi)
    fsi["value_num"] = pd.to_numeric(fsi["value_num"], errors="coerce")
    fsi["value_mbu"] = fsi["value_num"] / 1_000_000
    wide = (
        fsi.pivot_table(index="month", columns="metric", values="value_mbu", aggfunc="first")
        .reset_index()
        .rename_axis(None, axis=1)
    )
    for col in CORN_FSI_MONTHLY_COLUMNS:
        if col not in wide.columns and col not in {"commodity", "marketing_year", "source"}:
            wide[col] = pd.NA
    wide["commodity"] = "CORN"
    wide["marketing_year"] = wide["month"].map(marketing_year_from_date)
    wide["other_fsi_use_mbu"] = (
        wide["beverage_alcohol_use_mbu"].fillna(0)
        + wide["industrial_alcohol_use_mbu"].fillna(0)
        + wide["other_products_use_mbu"].fillna(0)
    )
    if "fsi_use_mbu" in wide.columns:
        wide["other_fsi_use_mbu"] = wide["other_fsi_use_mbu"].where(
            wide["other_fsi_use_mbu"].ne(0),
            wide["fsi_use_mbu"] - wide["fuel_alcohol_use_mbu"],
        )
    wide["source"] = "USDA NASS Grain Crushings and Co-Products"
    out = wide[CORN_FSI_MONTHLY_COLUMNS].sort_values("month")

    out_path = mart_dir / "mart_corn_fsi_monthly.csv"
    out.to_csv(out_path, index=False)
    return out_path


def build_soybean_crush_monthly(clean_dir: Path, mart_dir: Path) -> Path:
    """Standardize optional monthly soybean-crush data if a clean file exists."""
    df = read_optional_clean(
        clean_dir,
        ["soybean_crush_monthly.csv", "nass_soybean_crush_monthly.csv"],
        parse_dates=["month"],
    )
    if df.empty:
        return write_empty_mart(
            mart_dir,
            "mart_soybean_crush_monthly.csv",
            SOYBEAN_CRUSH_MONTHLY_COLUMNS,
        )

    if {"short_desc", "value_num", "year", "begin_code"}.issubset(df.columns):
        crush = df.copy()
        crush["metric"] = crush["short_desc"].map(SOYBEAN_CRUSH_METRIC_MAP)
        crush = crush[crush["metric"].notna()].copy()
        if crush.empty:
            return write_empty_mart(
                mart_dir,
                "mart_soybean_crush_monthly.csv",
                SOYBEAN_CRUSH_MONTHLY_COLUMNS,
            )
        crush["month"] = quickstats_month_frame(crush)
        crush["value_num"] = pd.to_numeric(crush["value_num"], errors="coerce")
        wide = (
            crush.pivot_table(
                index="month",
                columns="metric",
                values="value_num",
                aggfunc="first",
            )
            .reset_index()
            .rename_axis(None, axis=1)
        )
        wide["commodity"] = "SOYBEANS"
        wide["marketing_year"] = wide["month"].map(marketing_year_from_date)
        wide["soybean_crush_mbu"] = (
            wide.get("soybean_crush_short_tons", pd.Series(index=wide.index, dtype=float))
            * 2_000
            / 60
            / 1_000_000
        )
        wide["soybean_oil_stocks_mlb"] = (
            wide.get("soybean_oil_stocks_lb", pd.Series(index=wide.index, dtype=float))
            / 1_000_000
        )
        wide["source"] = "USDA NASS Oilseed Crushings"
        for col in SOYBEAN_CRUSH_MONTHLY_COLUMNS:
            if col not in wide.columns:
                wide[col] = pd.NA
        out = wide[SOYBEAN_CRUSH_MONTHLY_COLUMNS].dropna(subset=["month"])
        out = out.sort_values(["month"])

        out_path = mart_dir / "mart_soybean_crush_monthly.csv"
        out.to_csv(out_path, index=False)
        return out_path

    out = pd.DataFrame(index=df.index)
    out["commodity"] = "SOYBEANS"
    assign_first_available(out, df, "month", ["month", "period", "report_month", "date"])
    out["month"] = pd.to_datetime(out["month"], errors="coerce")
    assign_first_available(out, df, "marketing_year", ["marketing_year", "market_year"])
    out["marketing_year"] = out["marketing_year"].fillna(out["month"].map(marketing_year_from_date))
    assign_mbu(
        out,
        df,
        "soybean_crush_mbu",
        ["soybean_crush_mbu", "crush_mbu", "crushings_mbu"],
        ["soybean_crush_bu", "crush_bu", "crushings_bu"],
    )
    assign_first_available(
        out,
        df,
        "soybean_oil_stocks_mlb",
        ["soybean_oil_stocks_mlb", "oil_stocks_mlb"],
    )
    out["soybean_oil_stocks_mlb"] = pd.to_numeric(
        out["soybean_oil_stocks_mlb"],
        errors="coerce",
    )
    assign_first_available(
        out,
        df,
        "soybean_meal_production_short_tons",
        ["soybean_meal_production_short_tons", "meal_production_short_tons"],
    )
    out["soybean_meal_production_short_tons"] = pd.to_numeric(
        out["soybean_meal_production_short_tons"],
        errors="coerce",
    )
    out["source"] = "USDA NASS Oilseed Crushings"
    out = out[SOYBEAN_CRUSH_MONTHLY_COLUMNS].dropna(subset=["month"])
    out = out.sort_values(["month"])

    out_path = mart_dir / "mart_soybean_crush_monthly.csv"
    out.to_csv(out_path, index=False)
    return out_path


def stock_quarter_fields(stock_date: pd.Timestamp) -> tuple[int, str, int, str]:
    month = int(stock_date.month)
    if month == 12:
        crop_year = int(stock_date.year)
        quarter = 1
        label = "Q1 Sep-Nov"
    elif month == 3:
        crop_year = int(stock_date.year) - 1
        quarter = 2
        label = "Q2 Dec-Feb"
    elif month == 6:
        crop_year = int(stock_date.year) - 1
        quarter = 3
        label = "Q3 Mar-May"
    elif month == 9:
        crop_year = int(stock_date.year) - 1
        quarter = 4
        label = "Q4 Jun-Aug"
    else:
        crop_year = int(stock_date.year)
        quarter = 0
        label = "Unknown"
    marketing_year = f"{crop_year}/{str(crop_year + 1)[-2:]}"
    return crop_year, marketing_year, quarter, label


def sum_between_dates(
    df: pd.DataFrame,
    date_col: str,
    value_col: str,
    start_date: object,
    end_date: object,
    include_start: bool = False,
    include_end: bool = True,
) -> float | None:
    if df.empty or date_col not in df.columns or value_col not in df.columns:
        return None
    dates = pd.to_datetime(df[date_col], errors="coerce")
    values = pd.to_numeric(df[value_col], errors="coerce")
    start = pd.to_datetime(start_date, errors="coerce")
    end = pd.to_datetime(end_date, errors="coerce")
    if pd.isna(start) or pd.isna(end):
        return None
    lower_mask = dates.ge(start) if include_start else dates.gt(start)
    upper_mask = dates.le(end) if include_end else dates.lt(end)
    window = values[lower_mask & upper_mask]
    if window.notna().any():
        return float(window.sum())
    return None


def build_feed_residual_quarterly(clean_dir: Path, mart_dir: Path) -> Path:
    """Build a quarterly disappearance table for feed/residual work.

    True feed/residual needs quarterly exports and non-feed domestic use. This
    mart keeps the stock-based disappearance backbone and fills the direct
    components currently available.
    """
    stocks_path = mart_dir / "mart_stocks_quarterly.csv"
    supply_path = mart_dir / "mart_supply_annual.csv"
    wasde_path = mart_dir / "mart_wasde_balance.csv"
    if not stocks_path.exists() or not supply_path.exists():
        return write_empty_mart(
            mart_dir,
            "mart_feed_residual_quarterly.csv",
            FEED_RESIDUAL_QUARTERLY_COLUMNS,
        )

    stocks = pd.read_csv(stocks_path, parse_dates=["stock_date"])
    supply = pd.read_csv(supply_path)
    wasde = pd.read_csv(wasde_path) if wasde_path.exists() else pd.DataFrame()
    ethanol_path = mart_dir / "mart_ethanol_weekly.csv"
    corn_fsi_path = mart_dir / "mart_corn_fsi_monthly.csv"
    export_sales_path = mart_dir / "mart_export_sales_weekly.csv"
    inspections_path = mart_dir / "mart_export_inspections_weekly.csv"
    crush_path = mart_dir / "mart_soybean_crush_monthly.csv"
    ethanol = (
        pd.read_csv(ethanol_path, parse_dates=["period"])
        if ethanol_path.exists()
        else pd.DataFrame()
    )
    corn_fsi = (
        pd.read_csv(corn_fsi_path, parse_dates=["month"])
        if corn_fsi_path.exists()
        else pd.DataFrame()
    )
    export_sales = (
        pd.read_csv(export_sales_path, parse_dates=["week_ending"])
        if export_sales_path.exists()
        else pd.DataFrame()
    )
    inspections = (
        pd.read_csv(inspections_path, parse_dates=["week_ending"])
        if inspections_path.exists()
        else pd.DataFrame()
    )
    crush = (
        pd.read_csv(crush_path, parse_dates=["month"])
        if crush_path.exists()
        else pd.DataFrame()
    )

    stocks = stocks[
        stocks["state_alpha"].eq("US")
        & stocks["agg_level"].eq("NATIONAL")
        & stocks["stocks_mbu"].notna()
    ].copy()
    stocks = stocks.sort_values(["commodity", "stock_date"])
    stocks["prev_stock_date"] = stocks.groupby("commodity")["stock_date"].shift(1)
    stocks["beginning_stocks_mbu"] = stocks.groupby("commodity")["stocks_mbu"].shift(1)
    stocks = stocks.dropna(subset=["prev_stock_date", "beginning_stocks_mbu"]).copy()

    production = supply[
        supply["state_alpha"].eq("US") & supply["production_mbu"].notna()
    ][["commodity", "year", "production_mbu"]].copy()
    production = production.rename(
        columns={"year": "crop_year", "production_mbu": "production_added_mbu"}
    )

    if not wasde.empty and "feed_and_residual" in wasde.columns:
        wasde_feed = (
            wasde[["commodity", "marketing_year", "feed_and_residual", "column_order"]]
            .dropna(subset=["feed_and_residual"])
            .sort_values(["commodity", "marketing_year", "column_order"])
            .drop_duplicates(["commodity", "marketing_year"], keep="last")
            .rename(columns={"feed_and_residual": "wasde_feed_residual_annual_mbu"})
        )
    else:
        wasde_feed = pd.DataFrame(
            columns=["commodity", "marketing_year", "wasde_feed_residual_annual_mbu"]
        )

    rows = []
    for _, row in stocks.iterrows():
        crop_year, marketing_year, quarter, quarter_label = stock_quarter_fields(row["stock_date"])
        production_added_mbu = 0.0
        if quarter == 1:
            match = production[
                production["commodity"].eq(row["commodity"])
                & production["crop_year"].eq(crop_year)
            ]
            if not match.empty:
                production_added_mbu = float(match.iloc[-1]["production_added_mbu"])

        total_disappearance_mbu = (
            float(row["beginning_stocks_mbu"])
            + production_added_mbu
            - float(row["stocks_mbu"])
        )

        ethanol_use_mbu = None
        other_fsi_use_mbu = None
        exports_mbu = None
        soybean_crush_mbu = None
        if row["commodity"] == "CORN":
            corn_fsi_scope = (
                corn_fsi[corn_fsi["commodity"].eq("CORN")]
                if "commodity" in corn_fsi.columns
                else pd.DataFrame()
            )
            ethanol_use_mbu = sum_between_dates(
                corn_fsi_scope,
                "month",
                "fuel_alcohol_use_mbu",
                row["prev_stock_date"],
                row["stock_date"],
                include_start=True,
                include_end=False,
            )
            if ethanol_use_mbu is None:
                ethanol_use_mbu = sum_between_dates(
                    ethanol,
                    "period",
                    "implied_corn_use_mbu",
                    row["prev_stock_date"],
                    row["stock_date"],
                )
            other_fsi_use_mbu = sum_between_dates(
                corn_fsi_scope,
                "month",
                "other_fsi_use_mbu",
                row["prev_stock_date"],
                row["stock_date"],
                include_start=True,
                include_end=False,
            )
        elif row["commodity"] == "SOYBEANS":
            crush_scope = (
                crush[crush["commodity"].eq("SOYBEANS")]
                if "commodity" in crush.columns
                else pd.DataFrame()
            )
            soybean_crush_mbu = sum_between_dates(
                crush_scope,
                "month",
                "soybean_crush_mbu",
                row["prev_stock_date"],
                row["stock_date"],
                include_start=True,
                include_end=False,
            )

        export_sales_scope = (
            export_sales[export_sales["commodity"].eq(row["commodity"])]
            if "commodity" in export_sales.columns
            else pd.DataFrame()
        )
        exports_mbu = sum_between_dates(
            export_sales_scope,
            "week_ending",
            "current_week_exports_mbu",
            row["prev_stock_date"],
            row["stock_date"],
        )

        inspection_scope = (
            inspections[inspections["commodity"].eq(row["commodity"])]
            if "commodity" in inspections.columns
            else pd.DataFrame()
        )
        export_inspections_mbu = sum_between_dates(
            inspection_scope,
            "week_ending",
            "weekly_inspections_mbu",
            row["prev_stock_date"],
            row["stock_date"],
        )

        known_components = [
            value
            for value in (
                ethanol_use_mbu,
                other_fsi_use_mbu,
                exports_mbu,
                soybean_crush_mbu,
            )
            if value is not None and pd.notna(value)
        ]
        known_non_feed_use_mbu = sum(known_components) if known_components else None
        residual_after_known = (
            total_disappearance_mbu - known_non_feed_use_mbu
            if known_non_feed_use_mbu is not None
            else None
        )

        coverage_status = "stock disappearance only"
        if known_components:
            coverage_status = "partial: missing other domestic uses and/or exports"
        if (
            row["commodity"] == "CORN"
            and ethanol_use_mbu is not None
            and export_inspections_mbu is not None
        ):
            coverage_status = "partial: missing non-ethanol FSI"

        rows.append(
            {
                "commodity": row["commodity"],
                "marketing_year": marketing_year,
                "crop_year": crop_year,
                "quarter": quarter,
                "quarter_label": quarter_label,
                "quarter_start": row["prev_stock_date"],
                "quarter_end": row["stock_date"],
                "stock_date": row["stock_date"],
                "prev_stock_date": row["prev_stock_date"],
                "beginning_stocks_mbu": row["beginning_stocks_mbu"],
                "ending_stocks_mbu": row["stocks_mbu"],
                "production_added_mbu": production_added_mbu,
                "total_disappearance_mbu": total_disappearance_mbu,
                "ethanol_use_mbu": ethanol_use_mbu,
                "other_fsi_use_mbu": other_fsi_use_mbu,
                "exports_mbu": exports_mbu,
                "export_inspections_mbu": export_inspections_mbu,
                "soybean_crush_mbu": soybean_crush_mbu,
                "known_non_feed_use_mbu": known_non_feed_use_mbu,
                "residual_after_known_uses_mbu": residual_after_known,
                "feed_residual_implied_mbu": pd.NA,
                "coverage_status": coverage_status,
                "source": "NASS Grain Stocks + NASS production",
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        return write_empty_mart(
            mart_dir,
            "mart_feed_residual_quarterly.csv",
            FEED_RESIDUAL_QUARTERLY_COLUMNS,
        )

    out = out.merge(wasde_feed, on=["commodity", "marketing_year"], how="left")
    out = out[FEED_RESIDUAL_QUARTERLY_COLUMNS].sort_values(
        ["commodity", "quarter_end"]
    )

    out_path = mart_dir / "mart_feed_residual_quarterly.csv"
    out.to_csv(out_path, index=False)
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean-dir", type=Path, default=Path("data/clean"))
    parser.add_argument("--mart-dir", type=Path, default=Path("data/mart"))
    args = parser.parse_args()

    ensure_dir(args.mart_dir)
    builders = [
        build_supply_annual,
        build_crop_progress_weekly,
        build_crop_condition_weekly,
        build_stocks_quarterly,
        build_wasde_balance,
        build_drought_weekly,
        build_ethanol_weekly,
        build_export_sales_weekly,
        build_export_inspections_weekly,
        build_corn_fsi_monthly,
        build_soybean_crush_monthly,
        build_feed_residual_quarterly,
    ]

    print("Building mart tables")
    print("--------------------")
    for builder in builders:
        out_path = builder(args.clean_dir, args.mart_dir)
        rows = sum(1 for _ in out_path.open("r", encoding="utf-8")) - 1
        print(f"OK {out_path} ({rows:,} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
