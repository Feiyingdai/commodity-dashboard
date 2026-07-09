from __future__ import annotations

from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
MART_DIR = ROOT / "data" / "mart"

COLOR = {
    "corn": "#d2a10d",
    "soybeans": "#2f8f5b",
    "line": "#356a8a",
    "muted": "#6b7280",
}

STAGE_ORDER = {
    "CORN": ["planted", "emerged", "silking", "dough", "dented", "mature", "harvested"],
    "SOYBEANS": [
        "planted",
        "emerged",
        "blooming",
        "setting pods",
        "dropping leaves",
        "harvested",
    ],
}

CONDITION_LABELS = {
    "good_excellent": "Good/Excellent",
    "poor_very_poor": "Poor/Very Poor",
    "condition_index_0_100": "Condition Index",
}

STOCK_MONTH_LABELS = {
    3: "Mar 1",
    6: "Jun 1",
    9: "Sep 1",
    12: "Dec 1",
}

STOCK_MONTH_ORDER = ["Mar 1", "Jun 1", "Sep 1", "Dec 1"]

KEY_DROUGHT_STATES = {
    "CORN": ["IA", "IL", "NE", "MN", "IN"],
    "SOYBEANS": ["IL", "IA", "MN", "IN", "MO"],
}

YIELD_SIGNAL_RULES = {
    "CORN": {
        "condition_coef": 0.4,
        "condition_cap": 8.0,
        "drought_coef": 0.03,
        "drought_cap": 6.0,
    },
    "SOYBEANS": {
        "condition_coef": 0.12,
        "condition_cap": 3.0,
        "drought_coef": 0.01,
        "drought_cap": 2.0,
    },
}

OPTIONAL_MART_SCHEMAS = {
    "mart_corn_fsi_monthly.csv": [
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
    ],
    "mart_export_sales_weekly.csv": [
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
    ],
    "mart_export_inspections_weekly.csv": [
        "commodity",
        "marketing_year",
        "week_ending",
        "weekly_inspections_mbu",
        "accumulated_inspections_mbu",
        "source",
    ],
    "mart_soybean_crush_monthly.csv": [
        "commodity",
        "month",
        "marketing_year",
        "soybean_crush_mbu",
        "soybean_oil_stocks_mlb",
        "soybean_meal_production_short_tons",
        "source",
    ],
    "mart_feed_residual_quarterly.csv": [
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
    ],
}


def marketing_year_start(marketing_year: object) -> int | None:
    if pd.isna(marketing_year):
        return None
    text = str(marketing_year)
    try:
        return int(text.split("/", 1)[0])
    except (TypeError, ValueError):
        return None


def short_marketing_year(marketing_year: object) -> str:
    if pd.isna(marketing_year):
        return "-"

    text = str(marketing_year)
    if "/" not in text:
        return text

    start, end = text.split("/", 1)
    return f"{start[-2:]}/{end}" if len(start) == 4 else text


def short_wasde_label(
    marketing_year: object,
    estimate_type: object,
    vintage: object,
) -> str:
    year = short_marketing_year(marketing_year)
    estimate = "" if pd.isna(estimate_type) else str(estimate_type).lower()
    vintage_text = "" if pd.isna(vintage) else str(vintage)

    if estimate == "reported":
        suffix = "Rpt"
    elif estimate == "estimate":
        suffix = "Est"
    elif estimate == "projection" and vintage_text.lower() != "current":
        suffix = vintage_text
    elif estimate == "projection":
        suffix = "Proj"
    else:
        suffix = str(estimate_type) if not pd.isna(estimate_type) else ""

    return f"{year} {suffix}".strip()


st.set_page_config(
    page_title="U.S. Corn & Soybean Dashboard",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.4rem; padding-bottom: 2rem; }
    h1 { font-size: 1.65rem !important; margin-bottom: .2rem !important; }
    h2, h3 { letter-spacing: 0; }
    div[data-testid="stMetric"] {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 12px 14px;
        background: #ffffff;
    }
    div[data-testid="stMetricValue"] { font-size: 1.45rem; }
    div[data-testid="stMetricLabel"] { color: #4b5563; }
    .small-muted { color: #6b7280; font-size: .86rem; }
    .signal-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: .7rem;
        margin: .7rem 0 1rem;
    }
    .signal-card {
        min-height: 126px;
        border: 1px solid #e5e7eb;
        border-left: 5px solid #9ca3af;
        border-radius: 8px;
        padding: 12px 13px;
        background: #ffffff;
    }
    .signal-tight {
        border-left-color: #dc2626;
        background: linear-gradient(90deg, #fef2f2 0%, #ffffff 42%);
    }
    .signal-loose {
        border-left-color: #16a34a;
        background: linear-gradient(90deg, #f0fdf4 0%, #ffffff 42%);
    }
    .signal-watch {
        border-left-color: #d97706;
        background: linear-gradient(90deg, #fffbeb 0%, #ffffff 42%);
    }
    .signal-neutral {
        border-left-color: #9ca3af;
        background: #ffffff;
    }
    .signal-topline {
        display: flex;
        justify-content: space-between;
        gap: .5rem;
        align-items: center;
        margin-bottom: .35rem;
    }
    .signal-module {
        color: #6b7280;
        font-size: .74rem;
        font-weight: 700;
        letter-spacing: .04em;
        text-transform: uppercase;
    }
    .signal-badge {
        border-radius: 999px;
        border: 1px solid #d1d5db;
        padding: 2px 7px;
        color: #374151;
        font-size: .68rem;
        font-weight: 700;
        white-space: nowrap;
    }
    .signal-tight .signal-badge {
        color: #991b1b;
        border-color: #fecaca;
        background: #fee2e2;
    }
    .signal-loose .signal-badge {
        color: #166534;
        border-color: #bbf7d0;
        background: #dcfce7;
    }
    .signal-watch .signal-badge {
        color: #92400e;
        border-color: #fde68a;
        background: #fef3c7;
    }
    .signal-metric {
        color: #111827;
        font-size: .9rem;
        font-weight: 650;
        line-height: 1.2;
        min-height: 2.1em;
    }
    .signal-value {
        color: #111827;
        font-size: 1.28rem;
        font-weight: 740;
        line-height: 1.25;
        margin-top: .25rem;
    }
    .signal-detail {
        color: #4b5563;
        font-size: .78rem;
        line-height: 1.25;
        margin-top: .35rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def read_csv(
    name: str,
    parse_dates: list[str] | None = None,
    file_mtime: float | None = None,
) -> pd.DataFrame:
    path = MART_DIR / name
    if not path.exists():
        st.error(f"Missing mart table: {path}")
        st.stop()
    return pd.read_csv(path, parse_dates=parse_dates)


@st.cache_data(show_spinner=False)
def read_optional_csv(
    name: str,
    parse_dates: list[str] | None = None,
    file_mtime: float | None = None,
) -> pd.DataFrame:
    path = MART_DIR / name
    if not path.exists():
        return pd.DataFrame(columns=OPTIONAL_MART_SCHEMAS[name])
    return pd.read_csv(path, parse_dates=parse_dates)


def mart_mtime(name: str) -> float | None:
    path = MART_DIR / name
    return path.stat().st_mtime if path.exists() else None


def load_data() -> dict[str, pd.DataFrame]:
    return {
        "supply": read_csv(
            "mart_supply_annual.csv",
            parse_dates=["latest_load_time"],
            file_mtime=mart_mtime("mart_supply_annual.csv"),
        ),
        "progress": read_csv(
            "mart_crop_progress_weekly.csv",
            parse_dates=["week_ending", "load_time"],
            file_mtime=mart_mtime("mart_crop_progress_weekly.csv"),
        ),
        "condition": read_csv(
            "mart_crop_condition_weekly.csv",
            parse_dates=["week_ending", "load_time"],
            file_mtime=mart_mtime("mart_crop_condition_weekly.csv"),
        ),
        "stocks": read_csv(
            "mart_stocks_quarterly.csv",
            parse_dates=["stock_date", "load_time"],
            file_mtime=mart_mtime("mart_stocks_quarterly.csv"),
        ),
        "wasde": read_csv(
            "mart_wasde_balance.csv",
            file_mtime=mart_mtime("mart_wasde_balance.csv"),
        ),
        "drought": read_csv(
            "mart_drought_weekly.csv",
            parse_dates=["mapdate", "validstart", "validend"],
            file_mtime=mart_mtime("mart_drought_weekly.csv"),
        ),
        "ethanol": read_csv(
            "mart_ethanol_weekly.csv",
            parse_dates=["period"],
            file_mtime=mart_mtime("mart_ethanol_weekly.csv"),
        ),
        "corn_fsi": read_optional_csv(
            "mart_corn_fsi_monthly.csv",
            parse_dates=["month"],
            file_mtime=mart_mtime("mart_corn_fsi_monthly.csv"),
        ),
        "export_sales": read_optional_csv(
            "mart_export_sales_weekly.csv",
            parse_dates=["week_ending"],
            file_mtime=mart_mtime("mart_export_sales_weekly.csv"),
        ),
        "export_inspections": read_optional_csv(
            "mart_export_inspections_weekly.csv",
            parse_dates=["week_ending"],
            file_mtime=mart_mtime("mart_export_inspections_weekly.csv"),
        ),
        "soybean_crush": read_optional_csv(
            "mart_soybean_crush_monthly.csv",
            parse_dates=["month"],
            file_mtime=mart_mtime("mart_soybean_crush_monthly.csv"),
        ),
        "feed_residual": read_optional_csv(
            "mart_feed_residual_quarterly.csv",
            parse_dates=["quarter_start", "quarter_end", "stock_date", "prev_stock_date"],
            file_mtime=mart_mtime("mart_feed_residual_quarterly.csv"),
        ),
    }


def fmt_number(value: float | int | None, suffix: str = "", decimals: int = 1) -> str:
    if value is None or pd.isna(value):
        return "-"
    if abs(value) >= 1_000:
        return f"{value:,.0f}{suffix}"
    return f"{value:,.{decimals}f}{suffix}"


def fmt_signed_number(value: float | int | None, suffix: str = "", decimals: int = 1) -> str | None:
    if value is None or pd.isna(value):
        return None
    precision = 0 if abs(value) >= 1_000 else decimals
    rounded_value = round(float(value), precision)
    if rounded_value == 0:
        return None
    if abs(value) >= 1_000:
        return f"{rounded_value:+,.0f}{suffix}"
    return f"{rounded_value:+,.{decimals}f}{suffix}"


def fmt_date(value: object) -> str:
    date_value = pd.to_datetime(value, errors="coerce")
    if pd.isna(date_value):
        return "-"
    return date_value.strftime("%Y-%m-%d")


def fmt_change_detail(
    value: object,
    suffix: str,
    decimals: int,
    label: str,
) -> str:
    formatted = fmt_signed_number(value, suffix, decimals)
    return f"{formatted} {label}" if formatted else f"Flat {label}"


def signal_status_from_change(
    value: object,
    tight_when_positive: bool,
    threshold: float = 0.0,
) -> str:
    if value is None or pd.isna(value):
        return "neutral"

    numeric_value = float(value)
    if abs(numeric_value) <= threshold:
        return "neutral"

    if (numeric_value > 0 and tight_when_positive) or (
        numeric_value < 0 and not tight_when_positive
    ):
        return "tight"
    return "loose"


def signal_badge(status: str) -> str:
    return {
        "tight": "Tight",
        "loose": "Loose",
        "watch": "Watch",
        "neutral": "Neutral",
    }.get(status, "Neutral")


def signal_card(
    module: str,
    metric: str,
    value: str,
    detail: str,
    status: str = "neutral",
) -> dict[str, str]:
    return {
        "module": module,
        "metric": metric,
        "value": value,
        "detail": detail,
        "status": status if status in {"tight", "loose", "watch", "neutral"} else "neutral",
    }


def render_signal_cards(cards: list[dict[str, str]]) -> None:
    if not cards:
        st.info("No signal metrics are available for this filter.")
        return

    html_cards = []
    for card in cards:
        status = card.get("status", "neutral")
        html_cards.append(
            "<div class=\"signal-card signal-{status}\">"
            "<div class=\"signal-topline\">"
            "<span class=\"signal-module\">{module}</span>"
            "<span class=\"signal-badge\">{badge}</span>"
            "</div>"
            "<div class=\"signal-metric\">{metric}</div>"
            "<div class=\"signal-value\">{value}</div>"
            "<div class=\"signal-detail\">{detail}</div>"
            "</div>".format(
                status=escape(status),
                module=escape(card.get("module", "")),
                badge=escape(signal_badge(status)),
                metric=escape(card.get("metric", "")),
                value=escape(card.get("value", "-")),
                detail=escape(card.get("detail", "")),
            )
        )

    st.markdown(
        "<div class='signal-grid'>" + "".join(html_cards) + "</div>",
        unsafe_allow_html=True,
    )


def clamp(value: float | int | None, lower: float, upper: float) -> float:
    if value is None or pd.isna(value):
        return 0.0
    return min(max(float(value), lower), upper)


def optional_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column in df.columns:
        return df[column]
    return pd.Series(pd.NA, index=df.index)


def build_condition_adjustments(condition_df: pd.DataFrame, commodity: str) -> pd.DataFrame:
    cond = condition_df[
        condition_df["commodity"].eq(commodity)
        & condition_df["state_alpha"].eq("US")
        & condition_df["condition_index_0_100"].notna()
    ].copy()
    if cond.empty:
        return pd.DataFrame(columns=["commodity", "crop_year"])

    rule = YIELD_SIGNAL_RULES.get(commodity, YIELD_SIGNAL_RULES["CORN"])
    cond["season_week"] = cond["week_ending"].dt.isocalendar().week.astype(int)
    latest_rows = (
        cond.sort_values("week_ending")
        .groupby(["commodity", "year"], as_index=False)
        .tail(1)
    )

    rows = []
    for _, row in latest_rows.iterrows():
        hist = cond[
            cond["year"].between(int(row["year"]) - 5, int(row["year"]) - 1)
            & cond["season_week"].eq(row["season_week"])
        ]
        last_year = cond[
            cond["year"].eq(int(row["year"]) - 1)
            & cond["season_week"].eq(row["season_week"])
        ].sort_values("week_ending")
        five_year_avg = hist["condition_index_0_100"].mean()
        last_year_value = (
            last_year.iloc[-1]["condition_index_0_100"] if not last_year.empty else pd.NA
        )
        condition_gap = row["condition_index_0_100"] - five_year_avg
        raw_adjustment = condition_gap * rule["condition_coef"]
        condition_adjustment = clamp(
            raw_adjustment,
            -rule["condition_cap"],
            rule["condition_cap"],
        )
        rows.append(
            {
                "commodity": row["commodity"],
                "crop_year": int(row["year"]),
                "condition_signal_date": row["week_ending"],
                "condition_season_week": int(row["season_week"]),
                "condition_index": row["condition_index_0_100"],
                "condition_last_year": last_year_value,
                "condition_5y_avg": five_year_avg,
                "condition_gap": condition_gap,
                "condition_yield_adjustment": condition_adjustment,
            }
        )
    return pd.DataFrame(rows)


def build_state_production_weights(
    supply_df: pd.DataFrame,
    commodity: str,
    states: list[str],
    crop_years: list[int],
) -> pd.DataFrame:
    supply = supply_df[
        supply_df["commodity"].eq(commodity)
        & supply_df["state_alpha"].isin(states)
        & supply_df["production_mbu"].notna()
    ].copy()

    rows = []
    for crop_year in crop_years:
        hist = supply[supply["year"].between(crop_year - 5, crop_year - 1)]
        state_production = hist.groupby("state_alpha")["production_mbu"].mean()
        total_production = state_production.sum()

        if total_production and pd.notna(total_production):
            for state in states:
                production_5y = state_production.get(state, 0.0)
                rows.append(
                    {
                        "crop_year": crop_year,
                        "state_alpha": state,
                        "state_production_5y": production_5y,
                        "production_weight": production_5y / total_production,
                    }
                )
        else:
            equal_weight = 1 / len(states)
            for state in states:
                rows.append(
                    {
                        "crop_year": crop_year,
                        "state_alpha": state,
                        "state_production_5y": pd.NA,
                        "production_weight": equal_weight,
                    }
                )

    return pd.DataFrame(rows)


def build_weighted_drought_weekly(
    drought_df: pd.DataFrame,
    supply_df: pd.DataFrame,
    commodity: str,
) -> pd.DataFrame:
    states = KEY_DROUGHT_STATES.get(commodity, KEY_DROUGHT_STATES["CORN"])
    drought = drought_df[
        drought_df["state_alpha"].isin(states) & drought_df["dsci"].notna()
    ].copy()
    if drought.empty:
        return pd.DataFrame(columns=["crop_year"])

    drought["crop_year"] = drought["mapdate"].dt.year
    drought["season_week"] = drought["mapdate"].dt.isocalendar().week.astype(int)
    weights = build_state_production_weights(
        supply_df,
        commodity,
        states,
        sorted(drought["crop_year"].dropna().astype(int).unique()),
    )
    drought = drought.merge(weights, on=["crop_year", "state_alpha"], how="left")
    drought["production_weight"] = drought["production_weight"].fillna(1 / len(states))
    drought["weighted_dsci"] = drought["dsci"] * drought["production_weight"]

    drought_weekly = (
        drought.groupby(["crop_year", "mapdate", "season_week"], as_index=False)
        .agg(
            weighted_dsci_sum=("weighted_dsci", "sum"),
            weight_sum=("production_weight", "sum"),
            state_count=("state_alpha", "nunique"),
        )
    )
    drought_weekly["key_state_dsci"] = (
        drought_weekly["weighted_dsci_sum"] / drought_weekly["weight_sum"]
    )
    drought_weekly["drought_states"] = ", ".join(states)
    drought_weekly["drought_weight_method"] = "5Y production-weighted key states"
    return drought_weekly


def build_drought_adjustments(
    drought_df: pd.DataFrame,
    supply_df: pd.DataFrame,
    commodity: str,
) -> pd.DataFrame:
    drought_weekly = build_weighted_drought_weekly(drought_df, supply_df, commodity)
    if drought_weekly.empty:
        return pd.DataFrame(columns=["crop_year"])

    rule = YIELD_SIGNAL_RULES.get(commodity, YIELD_SIGNAL_RULES["CORN"])
    latest_rows = (
        drought_weekly.sort_values("mapdate")
        .groupby("crop_year", as_index=False)
        .tail(1)
    )

    rows = []
    for _, row in latest_rows.iterrows():
        hist = drought_weekly[
            drought_weekly["crop_year"].between(
                int(row["crop_year"]) - 5,
                int(row["crop_year"]) - 1,
            )
            & drought_weekly["season_week"].eq(row["season_week"])
        ]
        five_year_avg = hist["key_state_dsci"].mean()
        last_year = drought_weekly[
            drought_weekly["crop_year"].eq(int(row["crop_year"]) - 1)
            & drought_weekly["season_week"].eq(row["season_week"])
        ].sort_values("mapdate")
        last_year_value = (
            last_year.iloc[-1]["key_state_dsci"] if not last_year.empty else pd.NA
        )
        drought_gap = row["key_state_dsci"] - five_year_avg
        raw_adjustment = -drought_gap * rule["drought_coef"]
        drought_adjustment = clamp(
            raw_adjustment,
            -rule["drought_cap"],
            rule["drought_cap"],
        )
        rows.append(
            {
                "crop_year": int(row["crop_year"]),
                "drought_signal_date": row["mapdate"],
                "drought_season_week": int(row["season_week"]),
                "drought_states": row["drought_states"],
                "drought_weight_method": row["drought_weight_method"],
                "key_state_dsci": row["key_state_dsci"],
                "dsci_last_year": last_year_value,
                "dsci_5y_avg": five_year_avg,
                "dsci_gap": drought_gap,
                "drought_yield_adjustment": drought_adjustment,
            }
        )
    return pd.DataFrame(rows)


def trend_value(history: pd.DataFrame, year_col: str, value_col: str, target_year: int) -> float | None:
    hist = history.dropna(subset=[year_col, value_col]).sort_values(year_col).tail(10)
    if len(hist) < 3:
        return None
    x = hist[year_col].astype(float)
    y = hist[value_col].astype(float)
    x_mean = x.mean()
    denominator = ((x - x_mean) ** 2).sum()
    if denominator == 0:
        return None
    slope = ((x - x_mean) * (y - y.mean())).sum() / denominator
    intercept = y.mean() - slope * x_mean
    return float(intercept + slope * target_year)


def build_acreage_yield_baselines(supply_df: pd.DataFrame, commodity: str) -> pd.DataFrame:
    supply = supply_df[
        supply_df["commodity"].eq(commodity) & supply_df["state_alpha"].eq("US")
    ].copy()
    if supply.empty:
        return pd.DataFrame(columns=["commodity", "crop_year"])

    supply["harvest_ratio"] = supply["harvested_acres_mil"] / supply["planted_acres_mil"]
    rows = []
    for _, row in supply.sort_values("year").iterrows():
        crop_year = int(row["year"])
        hist = supply[
            supply["year"].between(crop_year - 5, crop_year - 1)
            & supply["harvest_ratio"].notna()
        ]
        planted_hist = supply[
            supply["year"].between(crop_year - 5, crop_year - 1)
            & supply["planted_acres_mil"].notna()
        ]
        planted_acres_5y = planted_hist["planted_acres_mil"].mean()
        harvest_ratio_5y = hist["harvest_ratio"].mean()
        trend_yield = trend_value(
            supply[supply["year"].lt(crop_year)],
            "year",
            "yield_bu_per_acre",
            crop_year,
        )
        rows.append(
            {
                "commodity": commodity,
                "crop_year": crop_year,
                "nass_planted_acres_mil": row["planted_acres_mil"],
                "nass_harvested_acres_mil": row["harvested_acres_mil"],
                "planted_acres_5y": planted_acres_5y,
                "harvest_ratio_5y": harvest_ratio_5y,
                "trend_yield": trend_yield,
            }
        )
    return pd.DataFrame(rows)


def build_production_model(
    wasde_df: pd.DataFrame,
    supply_df: pd.DataFrame,
    condition_df: pd.DataFrame,
    drought_df: pd.DataFrame,
    commodity: str,
    manual_yield_adjustment: float,
    manual_acres_adjustment: float,
) -> pd.DataFrame:
    if wasde_df.empty:
        return wasde_df.copy()

    model = wasde_df.copy()
    if "crop_year" not in model.columns:
        model["crop_year"] = model["marketing_year"].map(marketing_year_start)

    actual_production = supply_df[
        supply_df["state_alpha"].eq("US") & supply_df["production_mbu"].notna()
    ][["commodity", "year", "production_mbu"]].copy()
    actual_production = actual_production.rename(
        columns={
            "year": "crop_year",
            "production_mbu": "nass_production_mbu",
        }
    )

    model = model.merge(
        actual_production,
        on=["commodity", "crop_year"],
        how="left",
    )

    acreage_yield_baselines = build_acreage_yield_baselines(supply_df, commodity)
    if not acreage_yield_baselines.empty:
        model = model.merge(
            acreage_yield_baselines,
            on=["commodity", "crop_year"],
            how="left",
        )

    condition_adjustments = build_condition_adjustments(condition_df, commodity)
    if not condition_adjustments.empty:
        model = model.merge(
            condition_adjustments,
            on=["commodity", "crop_year"],
            how="left",
        )

    drought_adjustments = build_drought_adjustments(drought_df, supply_df, commodity)
    if not drought_adjustments.empty:
        model = model.merge(drought_adjustments, on="crop_year", how="left")

    for adjustment_col in ("condition_yield_adjustment", "drought_yield_adjustment"):
        if adjustment_col not in model.columns:
            model[adjustment_col] = 0.0
        else:
            model[adjustment_col] = model[adjustment_col].fillna(0.0)
    model["manual_yield_adjustment"] = manual_yield_adjustment
    model["manual_acres_adjustment"] = manual_acres_adjustment
    model["auto_yield_adjustment"] = (
        model["condition_yield_adjustment"] + model["drought_yield_adjustment"]
    )
    model["total_yield_adjustment"] = (
        model["auto_yield_adjustment"] + model["manual_yield_adjustment"]
    )

    model["yield_baseline"] = model["yield_per_harvested_acre"].combine_first(
        optional_series(model, "trend_yield")
    )
    model["yield_baseline_source"] = "WASDE yield"
    model.loc[
        model["yield_per_harvested_acre"].isna() & model["trend_yield"].notna(),
        "yield_baseline_source",
    ] = "10Y trend yield"

    model["planted_acres_baseline"] = model["area_planted"].combine_first(
        optional_series(model, "planted_acres_5y")
    )
    model["planted_acres_source"] = "WASDE planted acres"
    model.loc[
        model["area_planted"].isna() & optional_series(model, "planted_acres_5y").notna(),
        "planted_acres_source",
    ] = "5Y avg planted acres"

    fallback_harvested_acres = (
        model["planted_acres_baseline"] * optional_series(model, "harvest_ratio_5y")
    )
    model["harvested_acres_baseline"] = model["area_harvested"].combine_first(
        fallback_harvested_acres
    )
    model["harvested_acres_source"] = "WASDE harvested acres"
    model.loc[
        model["area_harvested"].isna() & fallback_harvested_acres.notna(),
        "harvested_acres_source",
    ] = "Planted acres * 5Y harvest ratio"

    model["my_yield"] = model["yield_baseline"]
    model["my_harvested_acres"] = model["harvested_acres_baseline"]
    model["production_source"] = "WASDE baseline"
    can_model = (
        model["nass_production_mbu"].isna()
        & model["yield_baseline"].notna()
        & model["harvested_acres_baseline"].notna()
    )
    model.loc[can_model, "my_yield"] = (
        model.loc[can_model, "yield_baseline"]
        + model.loc[can_model, "total_yield_adjustment"]
    )
    model.loc[can_model, "my_harvested_acres"] = (
        model.loc[can_model, "harvested_acres_baseline"] + manual_acres_adjustment
    ).clip(lower=0)
    model["my_production"] = model["production"]
    model.loc[can_model, "my_production"] = (
        model.loc[can_model, "my_harvested_acres"]
        * model.loc[can_model, "my_yield"]
    )
    model.loc[can_model, "production_source"] = "Production model V1"
    model.loc[model["nass_production_mbu"].notna(), "my_production"] = model.loc[
        model["nass_production_mbu"].notna(), "nass_production_mbu"
    ]
    model.loc[model["nass_production_mbu"].notna(), "production_source"] = "NASS actual"
    model["balance_label"] = (
        model["marketing_year"].astype(str)
        + " "
        + model["estimate_type"].astype(str)
        + " "
        + model["vintage"].astype(str)
    )
    model["balance_short_label"] = model.apply(
        lambda row: short_wasde_label(
            row["marketing_year"], row["estimate_type"], row["vintage"]
        ),
        axis=1,
    )
    model["yield_gap"] = model["my_yield"] - model["yield_per_harvested_acre"]
    model["harvested_acres_gap"] = model["my_harvested_acres"] - model["area_harvested"]
    model["production_gap"] = model["my_production"] - model["production"]
    return model


def build_balance_model(wasde_df: pd.DataFrame, production_model_df: pd.DataFrame) -> pd.DataFrame:
    if wasde_df.empty:
        return wasde_df.copy()

    model = wasde_df.copy()
    if "crop_year" not in model.columns:
        model["crop_year"] = model["marketing_year"].map(marketing_year_start)

    production_cols = [
        "commodity",
        "crop_year",
        "marketing_year",
        "estimate_type",
        "vintage",
        "nass_production_mbu",
        "my_production",
        "my_yield",
        "my_harvested_acres",
        "production_source",
        "yield_baseline",
        "yield_baseline_source",
        "planted_acres_baseline",
        "planted_acres_source",
        "planted_acres_5y",
        "harvested_acres_baseline",
        "harvested_acres_source",
        "nass_planted_acres_mil",
        "harvest_ratio_5y",
        "trend_yield",
        "condition_last_year",
        "condition_yield_adjustment",
        "dsci_last_year",
        "drought_weight_method",
        "drought_yield_adjustment",
        "manual_yield_adjustment",
        "manual_acres_adjustment",
        "auto_yield_adjustment",
        "total_yield_adjustment",
        "yield_gap",
        "harvested_acres_gap",
    ]
    available_production_cols = [
        col for col in production_cols if col in production_model_df.columns
    ]
    model = model.merge(
        production_model_df[available_production_cols],
        on=["commodity", "crop_year", "marketing_year", "estimate_type", "vintage"],
        how="left",
    )
    model["my_production"] = model["my_production"].combine_first(model["production"])
    model["production_source"] = model["production_source"].fillna("WASDE baseline")
    model["my_use_total"] = model["use_total"]
    model["use_source"] = "WASDE baseline"

    beginning_stocks_plus_imports = model["supply_total"] - model["production"]
    model["my_supply_total"] = beginning_stocks_plus_imports + model["my_production"]
    model["my_ending_stocks"] = model["my_supply_total"] - model["my_use_total"]
    model["my_ending_stocks"] = model["my_ending_stocks"].combine_first(
        model["ending_stocks"]
    )
    model["my_stocks_to_use_pct"] = (
        model["my_ending_stocks"] / model["my_use_total"] * 100
    ).combine_first(model["stocks_to_use_pct"])

    model["production_gap"] = model["my_production"] - model["production"]
    model["use_total_gap"] = model["my_use_total"] - model["use_total"]
    model["ending_stocks_gap"] = model["my_ending_stocks"] - model["ending_stocks"]
    model["stocks_to_use_pct_gap"] = (
        model["my_stocks_to_use_pct"] - model["stocks_to_use_pct"]
    )
    model["balance_label"] = (
        model["marketing_year"].astype(str)
        + " "
        + model["estimate_type"].astype(str)
        + " "
        + model["vintage"].astype(str)
    )
    model["balance_short_label"] = model.apply(
        lambda row: short_wasde_label(
            row["marketing_year"], row["estimate_type"], row["vintage"]
        ),
        axis=1,
    )
    return model


def build_production_reference(wasde_df: pd.DataFrame, supply_df: pd.DataFrame) -> pd.DataFrame:
    if wasde_df.empty:
        return wasde_df.copy()

    out = wasde_df.copy()
    if "crop_year" not in out.columns:
        out["crop_year"] = out["marketing_year"].map(marketing_year_start)

    actual_production = supply_df[
        supply_df["state_alpha"].eq("US") & supply_df["production_mbu"].notna()
    ][["commodity", "year", "production_mbu"]].copy()
    actual_production = actual_production.rename(
        columns={
            "year": "crop_year",
            "production_mbu": "nass_production_mbu",
        }
    )
    out = out.merge(actual_production, on=["commodity", "crop_year"], how="left")
    out["my_production"] = out["nass_production_mbu"].combine_first(out["production"])
    out["production_source"] = "WASDE baseline"
    out.loc[out["nass_production_mbu"].notna(), "production_source"] = "NASS actual"
    return out


def balance_comparison_table(row: pd.Series) -> pd.DataFrame:
    rows = [
        {
            "Metric": "Production",
            "My Model": fmt_number(row.get("my_production"), " mbu", 0),
            "WASDE": fmt_number(row.get("production"), " mbu", 0),
            "Difference": fmt_signed_number(row.get("production_gap"), " mbu", 0) or "-",
            "Model Source": row.get("production_source", "-"),
        },
        {
            "Metric": "Use Total",
            "My Model": fmt_number(row.get("my_use_total"), " mbu", 0),
            "WASDE": fmt_number(row.get("use_total"), " mbu", 0),
            "Difference": fmt_signed_number(row.get("use_total_gap"), " mbu", 0) or "-",
            "Model Source": row.get("use_source", "-"),
        },
        {
            "Metric": "Ending Stocks",
            "My Model": fmt_number(row.get("my_ending_stocks"), " mbu", 0),
            "WASDE": fmt_number(row.get("ending_stocks"), " mbu", 0),
            "Difference": fmt_signed_number(row.get("ending_stocks_gap"), " mbu", 0)
            or "-",
            "Model Source": "Balance formula",
        },
        {
            "Metric": "Ending Stocks-to-Use",
            "My Model": fmt_number(row.get("my_stocks_to_use_pct"), "%", 1),
            "WASDE": fmt_number(row.get("stocks_to_use_pct"), "%", 1),
            "Difference": fmt_signed_number(row.get("stocks_to_use_pct_gap"), " pp", 1)
            or "-",
            "Model Source": "Ending stocks / use",
        },
    ]
    return pd.DataFrame(rows)


def balance_gap_frame(row: pd.Series) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Metric": "Production", "Gap": row.get("production_gap")},
            {"Metric": "Use Total", "Gap": row.get("use_total_gap")},
            {"Metric": "Ending Stocks", "Gap": row.get("ending_stocks_gap")},
        ]
    ).dropna(subset=["Gap"])


def balance_snapshot_table(row: pd.Series, prior_row: pd.Series) -> pd.DataFrame:
    specs = [
        ("Production", "production", " mbu", 0, False, 5),
        ("Supply Total", "supply_total", " mbu", 0, False, 5),
        ("Total Use", "use_total", " mbu", 0, True, 5),
        ("Ending Stocks", "ending_stocks", " mbu", 0, False, 5),
        ("Ending Stocks-to-Use", "stocks_to_use_pct", "%", 1, False, 0.05),
        ("Average Farm Price", "avg_farmprice_bu", " $/bu", 2, True, 0.01),
    ]
    rows = []
    for metric, column, suffix, decimals, tight_when_positive, threshold in specs:
        change = row_change(row, prior_row, column)
        rows.append(
            {
                "Metric": metric,
                "Selected": fmt_number(row.get(column), suffix, decimals),
                "Prior WASDE": fmt_number(prior_row.get(column), suffix, decimals)
                if not prior_row.empty
                else "-",
                "Change": fmt_signed_number(
                    change,
                    " pp" if column == "stocks_to_use_pct" else suffix,
                    decimals,
                )
                or "-",
                "Marker": signal_badge(
                    signal_status_from_change(change, tight_when_positive, threshold)
                ),
            }
        )
    return pd.DataFrame(rows)


def production_signal_table(row: pd.Series) -> pd.DataFrame:
    rows = [
        {
            "Signal": "Crop Condition Index",
            "Basis": "US national",
            "Date": row.get("condition_signal_date"),
            "Latest": fmt_number(row.get("condition_index"), "", 1),
            "Last Year": fmt_number(row.get("condition_last_year"), "", 1),
            "5Y Avg": fmt_number(row.get("condition_5y_avg"), "", 1),
            "Gap": fmt_signed_number(row.get("condition_gap"), "", 1) or "-",
        },
        {
            "Signal": "Weighted DSCI",
            "Basis": row.get("drought_weight_method", "5Y production-weighted key states"),
            "Date": row.get("drought_signal_date"),
            "Latest": fmt_number(row.get("key_state_dsci"), "", 1),
            "Last Year": fmt_number(row.get("dsci_last_year"), "", 1),
            "5Y Avg": fmt_number(row.get("dsci_5y_avg"), "", 1),
            "Gap": fmt_signed_number(row.get("dsci_gap"), "", 1) or "-",
        },
    ]
    return pd.DataFrame(rows)


def latest_by_date(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
    if df.empty:
        return df
    return df[df[date_col].eq(df[date_col].max())].copy()


def line_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    color: str | None = None,
    height: int = 300,
    x_title: str | None = None,
    y_title: str | None = None,
    color_title: str | None = None,
    y_zero: bool | None = None,
    x_axis_format: str | None = None,
    x_tick_interval: str | None = None,
    x_label_angle: int | None = None,
    x_label_limit: int | None = None,
    x_sort_field: str | None = None,
    extra_tooltips: list[dict[str, object]] | None = None,
):
    x_type = (
        "temporal"
        if "date" in x
        or x in {"period", "week_ending", "mapdate", "stock_date", "month", "quarter_end"}
        else "ordinal"
    )
    x_axis = {"title": x_title or x}
    if x_label_angle is not None:
        x_axis["labelAngle"] = x_label_angle
    if x_label_limit is not None:
        x_axis["labelLimit"] = x_label_limit
    if x_type == "temporal":
        if x_axis_format:
            x_axis["format"] = x_axis_format
        if x_tick_interval:
            x_axis["tickCount"] = {"interval": x_tick_interval, "step": 1}
    x_encoding = {
        "field": x,
        "type": x_type,
        "axis": x_axis,
    }
    if x_type == "ordinal":
        if x_sort_field and x_sort_field in df.columns:
            x_encoding["sort"] = {
                "field": x_sort_field,
                "op": "min",
                "order": "ascending",
            }
        else:
            x_encoding["sort"] = None

    y_encoding = {"field": y, "type": "quantitative", "axis": {"title": y_title or y}}
    if y_zero is not None:
        y_encoding["scale"] = {"zero": y_zero}

    tooltips = [
        {"field": x, "type": x_type},
        {"field": y, "type": "quantitative", "format": ",.2f"},
    ]
    if extra_tooltips:
        tooltips.extend(
            tooltip
            for tooltip in extra_tooltips
            if str(tooltip.get("field")) in df.columns
        )

    encoding = {
        "x": x_encoding,
        "y": y_encoding,
        "tooltip": tooltips,
    }
    if color:
        encoding["color"] = {
            "field": color,
            "type": "nominal",
            "legend": {"title": color_title or color},
        }
        encoding["tooltip"].append({"field": color, "type": "nominal"})

    st.vega_lite_chart(
        df,
        {
            "height": height,
            "mark": {"type": "line", "point": False, "strokeWidth": 2},
            "encoding": encoding,
        },
        width="stretch",
    )


def metric_snapshot(
    df: pd.DataFrame,
    column: str,
    suffix: str = "",
    decimals: int = 1,
) -> tuple[str, str | None, int | None]:
    series = df.dropna(subset=[column]).sort_values("year")
    if series.empty:
        return "-", None, None

    current = series.iloc[-1]
    previous = series.iloc[-2] if len(series) > 1 else None
    delta = None
    if previous is not None:
        change = current[column] - previous[column]
        if pd.notna(change):
            delta_value = f"{change:+,.0f}" if decimals == 0 else f"{change:+,.{decimals}f}"
            delta = f"{delta_value}{suffix} YoY"

    return fmt_number(current[column], suffix, decimals), delta, int(current["year"])


def seasonal_week_frame(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    seasonal = df.dropna(subset=["week_ending", "year", value_col]).copy()
    if seasonal.empty:
        return seasonal

    seasonal["season_week"] = seasonal["week_ending"].dt.isocalendar().week.astype(int)
    seasonal["year_label"] = seasonal["year"].astype(str)
    return seasonal.sort_values(["year", "season_week"])


def seasonal_line_chart(
    df: pd.DataFrame,
    value_col: str,
    y_title: str,
    height: int = 360,
):
    plot = seasonal_week_frame(df, value_col)
    if plot.empty:
        st.info("No records for this filter.")
        return

    st.vega_lite_chart(
        plot,
        {
            "height": height,
            "mark": {"type": "line", "point": False, "strokeWidth": 2},
            "encoding": {
                "x": {
                    "field": "season_week",
                    "type": "quantitative",
                    "axis": {"title": "Week of Year", "tickMinStep": 1},
                    "scale": {"zero": False},
                },
                "y": {
                    "field": value_col,
                    "type": "quantitative",
                    "axis": {"title": y_title},
                },
                "color": {
                    "field": "year_label",
                    "type": "nominal",
                    "legend": {"title": "Year"},
                },
                "tooltip": [
                    {"field": "year", "type": "ordinal", "title": "Year"},
                    {"field": "week_ending", "type": "temporal", "title": "Week Ending"},
                    {"field": "season_week", "type": "quantitative", "title": "Week"},
                    {"field": value_col, "type": "quantitative", "format": ",.2f"},
                ],
            },
        },
        width="stretch",
    )


def default_stage_for_year(
    progress_df: pd.DataFrame,
    commodity_name: str,
    latest_year: int,
    stages: list[str],
) -> str:
    latest_year_stages = set(
        progress_df.loc[progress_df["year"].eq(latest_year), "stage"].dropna()
    )
    ordered_stages = STAGE_ORDER.get(commodity_name, [])
    for stage in reversed(ordered_stages):
        if stage in latest_year_stages:
            return stage
    return "harvested" if "harvested" in stages else stages[0]


def bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    color: str | None = None,
    height: int = 300,
    x_title: str | None = None,
    x_sort_field: str | None = None,
    x_label_angle: int | None = None,
    x_label_limit: int | None = None,
    extra_tooltips: list[dict[str, object]] | None = None,
):
    x_axis = {}
    if x_title is not None:
        x_axis["title"] = x_title
    if x_label_angle is not None:
        x_axis["labelAngle"] = x_label_angle
    if x_label_limit is not None:
        x_axis["labelLimit"] = x_label_limit

    x_encoding = {"field": x, "type": "nominal", "axis": x_axis}
    if x_sort_field and x_sort_field in df.columns:
        x_encoding["sort"] = {
            "field": x_sort_field,
            "op": "min",
            "order": "ascending",
        }
    else:
        x_encoding["sort"] = None

    tooltips = [
        {"field": x, "type": "nominal"},
        {"field": y, "type": "quantitative", "format": ",.2f"},
    ]
    if extra_tooltips:
        tooltips.extend(
            tooltip
            for tooltip in extra_tooltips
            if str(tooltip.get("field")) in df.columns
        )

    encoding = {
        "x": x_encoding,
        "y": {"field": y, "type": "quantitative"},
        "tooltip": tooltips,
    }
    if color:
        encoding["color"] = {"field": color, "type": "nominal"}
        encoding["tooltip"].append({"field": color, "type": "nominal"})

    st.vega_lite_chart(
        df,
        {
            "height": height,
            "mark": {"type": "bar", "cornerRadiusTopLeft": 2, "cornerRadiusTopRight": 2},
            "encoding": encoding,
        },
        width="stretch",
    )


def build_demand_components(wasde_df: pd.DataFrame, commodity_name: str) -> pd.DataFrame:
    demand = wasde_df.copy()
    if demand.empty:
        return pd.DataFrame(
            columns=[
                "period",
                "period_short",
                "marketing_year",
                "estimate_type",
                "vintage",
                "column_order",
                "use_total",
                "component",
                "mbu",
                "share_pct",
            ]
        )

    demand["period"] = (
        demand["marketing_year"].astype(str)
        + " "
        + demand["estimate_type"].astype(str)
        + " "
        + demand["vintage"].astype(str)
    )
    demand["period_short"] = demand.apply(
        lambda row: short_wasde_label(
            row["marketing_year"], row["estimate_type"], row["vintage"]
        ),
        axis=1,
    )
    if commodity_name == "CORN":
        demand["Feed & Residual"] = demand["feed_and_residual"]
        demand["Ethanol"] = demand["ethanol_and_by_products"]
        demand["Other FSI"] = (
            demand["food_seedand_industrial"] - demand["ethanol_and_by_products"]
        )
        demand["Exports"] = demand["exports"]
        components = ["Feed & Residual", "Ethanol", "Other FSI", "Exports"]
    else:
        demand["Crush"] = demand["crushings"]
        demand["Exports"] = demand["exports"]
        demand["Other Use"] = (
            demand["use_total"] - demand["crushings"] - demand["exports"]
        )
        components = ["Crush", "Exports", "Other Use"]

    long = demand.melt(
        id_vars=[
            "period",
            "period_short",
            "marketing_year",
            "estimate_type",
            "vintage",
            "column_order",
            "use_total",
        ],
        value_vars=components,
        var_name="component",
        value_name="mbu",
    ).dropna(subset=["mbu"])
    long["share_pct"] = long["mbu"] / long["use_total"] * 100
    long["period_order"] = long["column_order"].rank(method="dense").astype(int)
    return long.sort_values(["column_order", "component"])


def stacked_bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    color: str,
    height: int = 330,
    y_title: str | None = None,
    color_title: str | None = None,
    y_domain: list[int] | None = None,
    x_sort_field: str | None = None,
    x_label_angle: int | None = 0,
    x_label_limit: int | None = 80,
    period_tooltip_field: str | None = None,
):
    if df.empty:
        st.info("No demand records for this filter.")
        return

    x_encoding = {
        "field": x,
        "type": "nominal",
        "axis": {
            "title": None,
            "labelAngle": x_label_angle,
            "labelLimit": x_label_limit,
        },
    }
    if x_sort_field and x_sort_field in df.columns:
        x_encoding["sort"] = {
            "field": x_sort_field,
            "op": "min",
            "order": "ascending",
        }
    else:
        x_encoding["sort"] = None

    y_encoding = {
        "field": y,
        "type": "quantitative",
        "axis": {"title": y_title or y},
        "stack": "zero",
    }
    if y_domain is not None:
        y_encoding["scale"] = {"domain": y_domain}

    period_tooltip_field = period_tooltip_field or x
    tooltip = [
        {"field": period_tooltip_field, "type": "nominal", "title": "Period"},
        {"field": color, "type": "nominal", "title": color_title or color},
        {"field": "mbu", "type": "quantitative", "format": ",.0f", "title": "mbu"},
        {"field": "share_pct", "type": "quantitative", "format": ".1f", "title": "Share %"},
    ]

    st.vega_lite_chart(
        df,
        {
            "height": height,
            "mark": {"type": "bar", "cornerRadiusTopLeft": 2, "cornerRadiusTopRight": 2},
            "encoding": {
                "x": x_encoding,
                "y": y_encoding,
                "color": {
                    "field": color,
                    "type": "nominal",
                    "legend": {"title": color_title or color},
                },
                "order": {"field": color, "type": "nominal"},
                "tooltip": tooltip,
            },
        },
        width="stretch",
    )


def ethanol_monitor_frame(ethanol_df: pd.DataFrame) -> pd.DataFrame:
    ethanol = ethanol_df.sort_values("period").copy()
    ethanol["implied_corn_use_13w_avg"] = (
        ethanol["implied_corn_use_mbu"].rolling(13, min_periods=4).mean()
    )
    return ethanol


def component_row(df: pd.DataFrame, component_name: str) -> pd.Series:
    rows = df[df["component"].eq(component_name)]
    if rows.empty:
        return pd.Series(dtype="object")
    return rows.iloc[-1]


def forecast_component_label(component_name: str, share_pct: object) -> str:
    share_label = fmt_number(share_pct, "%", 1)
    return f"WASDE Forecast {component_name} ({share_label})"


def latest_actual_row(df: pd.DataFrame, date_col: str) -> pd.Series:
    if df.empty or date_col not in df.columns:
        return pd.Series(dtype="object")
    latest = df.dropna(subset=[date_col]).sort_values(date_col)
    if latest.empty:
        return pd.Series(dtype="object")
    return latest.iloc[-1]


def stock_month_label(value: object) -> str:
    if pd.isna(value):
        return "-"
    return STOCK_MONTH_LABELS.get(int(value), str(value))


def marketing_year_from_sep_stock(stock_date: object) -> str | None:
    date_value = pd.to_datetime(stock_date, errors="coerce")
    if pd.isna(date_value) or date_value.month != 9:
        return None
    start_year = date_value.year - 1
    return f"{start_year}/{str(start_year + 1)[-2:]}"


def latest_stock_context(stocks_df: pd.DataFrame) -> dict[str, object]:
    if stocks_df.empty:
        return {}
    stocks = stocks_df.dropna(subset=["stock_date", "stocks_mbu"]).sort_values("stock_date")
    if stocks.empty:
        return {}

    latest = stocks.iloc[-1]
    latest_month = latest["stock_month"]
    latest_date = latest["stock_date"]
    prior_same_month = stocks[
        stocks["stock_month"].eq(latest_month) & stocks["stock_date"].lt(latest_date)
    ].sort_values("stock_date")
    yoy_rows = prior_same_month[
        pd.to_datetime(prior_same_month["stock_date"]).dt.year.eq(latest_date.year - 1)
    ]
    yoy_value = yoy_rows.iloc[-1]["stocks_mbu"] if not yoy_rows.empty else pd.NA
    five_year_avg = prior_same_month.tail(5)["stocks_mbu"].mean()

    return {
        "latest": latest,
        "yoy_value": yoy_value,
        "yoy_change": latest["stocks_mbu"] - yoy_value if pd.notna(yoy_value) else pd.NA,
        "five_year_avg": five_year_avg,
        "five_year_gap": latest["stocks_mbu"] - five_year_avg if pd.notna(five_year_avg) else pd.NA,
    }


def stock_seasonal_frame(stocks_df: pd.DataFrame) -> pd.DataFrame:
    seasonal = stocks_df.dropna(subset=["stock_date", "stocks_mbu"]).copy()
    if seasonal.empty:
        return seasonal
    seasonal["stock_month_label"] = seasonal["stock_month"].map(stock_month_label)
    seasonal["year_label"] = seasonal["stock_date"].dt.year.astype(str)
    seasonal["stock_month_order"] = seasonal["stock_month"].map({3: 1, 6: 2, 9: 3, 12: 4})
    return seasonal.sort_values(["year_label", "stock_month_order"])


def stock_seasonal_chart(df: pd.DataFrame, height: int = 340):
    plot = stock_seasonal_frame(df)
    if plot.empty:
        st.info("No seasonal stock records for this filter.")
        return
    st.vega_lite_chart(
        plot,
        {
            "height": height,
            "mark": {"type": "line", "point": True, "strokeWidth": 2},
            "encoding": {
                "x": {
                    "field": "stock_month_label",
                    "type": "ordinal",
                    "sort": STOCK_MONTH_ORDER,
                    "axis": {"title": "Stock Report Date"},
                },
                "y": {
                    "field": "stocks_mbu",
                    "type": "quantitative",
                    "axis": {"title": "Stocks (mbu)"},
                },
                "color": {
                    "field": "year_label",
                    "type": "nominal",
                    "legend": {"title": "Calendar Year"},
                },
                "tooltip": [
                    {"field": "stock_date", "type": "temporal", "title": "Stock Date"},
                    {"field": "stocks_mbu", "type": "quantitative", "format": ",.1f", "title": "Stocks (mbu)"},
                    {"field": "on_farm_share_pct", "type": "quantitative", "format": ".1f", "title": "On-Farm Share %"},
                ],
            },
        },
        width="stretch",
    )


def build_wasde_stock_validation(stocks_df: pd.DataFrame, wasde_df: pd.DataFrame) -> pd.DataFrame:
    if stocks_df.empty or wasde_df.empty:
        return pd.DataFrame()
    sep_stocks = stocks_df[
        stocks_df["stock_month"].eq(9)
        & stocks_df["state_alpha"].eq("US")
        & stocks_df["stocks_mbu"].notna()
    ].copy()
    if sep_stocks.empty:
        return pd.DataFrame()
    sep_stocks["marketing_year"] = sep_stocks["stock_date"].map(marketing_year_from_sep_stock)

    latest_wasde_by_year = (
        wasde_df.dropna(subset=["ending_stocks"])
        .sort_values(["commodity", "marketing_year", "column_order"])
        .drop_duplicates(["commodity", "marketing_year"], keep="last")
    )
    validation = sep_stocks.merge(
        latest_wasde_by_year[
            [
                "commodity",
                "marketing_year",
                "estimate_type",
                "vintage",
                "ending_stocks",
                "stocks_to_use_pct",
            ]
        ],
        on=["commodity", "marketing_year"],
        how="inner",
    )
    validation["difference_mbu"] = validation["stocks_mbu"] - validation["ending_stocks"]
    validation["difference_pct"] = validation["difference_mbu"] / validation["ending_stocks"] * 100
    return validation.sort_values("stock_date", ascending=False)


def prior_balance_row(balance_model: pd.DataFrame, row: pd.Series) -> pd.Series:
    if balance_model.empty or pd.isna(row.get("column_order")):
        return pd.Series(dtype="object")

    prior = balance_model[
        balance_model["column_order"].lt(row.get("column_order"))
    ].sort_values("column_order")
    if prior.empty:
        return pd.Series(dtype="object")
    return prior.iloc[-1]


def row_change(row: pd.Series, prior_row: pd.Series, column: str) -> object:
    if prior_row.empty:
        return pd.NA
    value = row.get(column)
    prior_value = prior_row.get(column)
    if pd.isna(value) or pd.isna(prior_value):
        return pd.NA
    return value - prior_value


def matching_signal_row(
    production_signals: pd.DataFrame,
    balance_row: pd.Series,
) -> pd.Series:
    if production_signals.empty:
        return pd.Series(dtype="object")

    if "balance_label" in production_signals.columns:
        same_label = production_signals[
            production_signals["balance_label"].eq(balance_row.get("balance_label"))
        ]
        if not same_label.empty:
            return same_label.iloc[-1]

    if "crop_year" in production_signals.columns and pd.notna(balance_row.get("crop_year")):
        same_year = production_signals[
            production_signals["crop_year"].eq(balance_row.get("crop_year"))
        ].sort_values("column_order")
        if not same_year.empty:
            return same_year.iloc[-1]

    return pd.Series(dtype="object")


def latest_actual_vs_average(
    df: pd.DataFrame,
    date_col: str,
    value_col: str,
    average_window: int,
    min_periods: int,
) -> tuple[pd.Series, object]:
    if df.empty or date_col not in df.columns or value_col not in df.columns:
        return pd.Series(dtype="object"), pd.NA

    actuals = df.dropna(subset=[date_col, value_col]).sort_values(date_col).copy()
    if actuals.empty:
        return pd.Series(dtype="object"), pd.NA

    average_col = f"{value_col}_avg"
    actuals[average_col] = (
        actuals[value_col].rolling(average_window, min_periods=min_periods).mean()
    )
    latest = actuals.iloc[-1]
    if pd.isna(latest.get(average_col)):
        return latest, pd.NA
    return latest, latest.get(value_col) - latest.get(average_col)


def build_balance_signal_cards(
    balance_row: pd.Series,
    balance_model: pd.DataFrame,
    production_signals: pd.DataFrame,
    wasde_df: pd.DataFrame,
    data: dict[str, pd.DataFrame],
    commodity: str,
    years: tuple[int, int],
) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    prior_row = prior_balance_row(balance_model, balance_row)
    selected_label = balance_row.get("balance_short_label", "-")

    balance_specs = [
        ("Balance", "WASDE Production", "production", " mbu", 0, False, 5),
        ("Balance", "WASDE Total Use", "use_total", " mbu", 0, True, 5),
        ("Balance", "WASDE Ending Stocks", "ending_stocks", " mbu", 0, False, 5),
        ("Balance", "WASDE Ending Stocks-to-Use", "stocks_to_use_pct", "%", 1, False, 0.05),
    ]
    for module, metric, column, suffix, decimals, tight_when_positive, threshold in balance_specs:
        change = row_change(balance_row, prior_row, column)
        detail = (
            fmt_change_detail(change, " pp" if column == "stocks_to_use_pct" else suffix, decimals, "vs prior WASDE")
            if pd.notna(change)
            else f"{selected_label} selected"
        )
        cards.append(
            signal_card(
                module,
                metric,
                fmt_number(balance_row.get(column), suffix, decimals),
                detail,
                signal_status_from_change(change, tight_when_positive, threshold),
            )
        )

    signal_row = matching_signal_row(production_signals, balance_row)
    if not signal_row.empty and pd.notna(signal_row.get("condition_index")):
        condition_gap = signal_row.get("condition_gap")
        cards.append(
            signal_card(
                "Production",
                "Crop Condition Index",
                fmt_number(signal_row.get("condition_index"), "", 1),
                f"{fmt_change_detail(condition_gap, '', 1, 'vs 5Y')}; {fmt_date(signal_row.get('condition_signal_date'))}",
                signal_status_from_change(condition_gap, tight_when_positive=False, threshold=1.0),
            )
        )
    if not signal_row.empty and pd.notna(signal_row.get("key_state_dsci")):
        dsci_gap = signal_row.get("dsci_gap")
        cards.append(
            signal_card(
                "Field/Weather",
                "Weighted DSCI",
                fmt_number(signal_row.get("key_state_dsci"), "", 1),
                f"{fmt_change_detail(dsci_gap, '', 1, 'vs 5Y')}; {fmt_date(signal_row.get('drought_signal_date'))}",
                signal_status_from_change(dsci_gap, tight_when_positive=True, threshold=5.0),
            )
        )

    demand_components = build_demand_components(wasde_df, commodity)
    selected_demand = demand_components[
        demand_components["column_order"].eq(balance_row.get("column_order"))
    ].copy()
    if not selected_demand.empty:
        largest_component = selected_demand.sort_values("mbu").iloc[-1]
        cards.append(
            signal_card(
                "Demand",
                f"Largest End Use: {largest_component.get('component', '-')}",
                fmt_number(largest_component.get("mbu"), " mbu", 0),
                f"{fmt_number(largest_component.get('share_pct'), '%', 1)} of total use",
                "neutral",
            )
        )

        export_component = component_row(selected_demand, "Exports")
        prior_export_share = pd.NA
        prior_demand = demand_components[
            demand_components["column_order"].lt(balance_row.get("column_order"))
            & demand_components["component"].eq("Exports")
        ].sort_values("column_order")
        if not prior_demand.empty:
            prior_export_share = prior_demand.iloc[-1].get("share_pct")
        export_share_change = (
            export_component.get("share_pct") - prior_export_share
            if pd.notna(export_component.get("share_pct")) and pd.notna(prior_export_share)
            else pd.NA
        )
        cards.append(
            signal_card(
                "Demand",
                "Export Share",
                fmt_number(export_component.get("share_pct"), "%", 1),
                fmt_change_detail(export_share_change, " pp", 1, "vs prior WASDE")
                if pd.notna(export_share_change)
                else "WASDE end-use mix",
                signal_status_from_change(export_share_change, tight_when_positive=True, threshold=0.25),
            )
        )

    if commodity == "CORN":
        ethanol = ethanol_monitor_frame(data["ethanol"])
        latest_ethanol, ethanol_gap = latest_actual_vs_average(
            ethanol,
            "period",
            "implied_corn_use_13w_avg",
            average_window=52,
            min_periods=20,
        )
        if not latest_ethanol.empty:
            cards.append(
                signal_card(
                    "Actual Demand",
                    "Ethanol Corn Use 13W Avg",
                    fmt_number(latest_ethanol.get("implied_corn_use_13w_avg"), " mbu/wk", 1),
                    f"{fmt_change_detail(ethanol_gap, ' mbu/wk', 1, 'vs 52W avg')}; {fmt_date(latest_ethanol.get('period'))}"
                    if pd.notna(ethanol_gap)
                    else f"Latest week {fmt_date(latest_ethanol.get('period'))}",
                    signal_status_from_change(ethanol_gap, tight_when_positive=True, threshold=1.0),
                )
            )
    else:
        soybean_crush = data["soybean_crush"][
            data["soybean_crush"]["commodity"].eq("SOYBEANS")
        ].copy()
        latest_crush, crush_gap = latest_actual_vs_average(
            soybean_crush,
            "month",
            "soybean_crush_mbu",
            average_window=12,
            min_periods=6,
        )
        if not latest_crush.empty:
            cards.append(
                signal_card(
                    "Actual Demand",
                    "Soybean Crush",
                    fmt_number(latest_crush.get("soybean_crush_mbu"), " mbu/month", 1),
                    f"{fmt_change_detail(crush_gap, ' mbu/month', 1, 'vs 12M avg')}; {fmt_date(latest_crush.get('month'))}"
                    if pd.notna(crush_gap)
                    else f"Latest month {fmt_date(latest_crush.get('month'))}",
                    signal_status_from_change(crush_gap, tight_when_positive=True, threshold=2.0),
                )
            )

    export_sales = data["export_sales"][data["export_sales"]["commodity"].eq(commodity)]
    export_inspections = data["export_inspections"][
        data["export_inspections"]["commodity"].eq(commodity)
    ]
    if export_sales.empty and export_inspections.empty:
        cards.append(
            signal_card(
                "Actual Demand",
                "Export Actuals",
                "Pending",
                "Export sales/inspections data not loaded yet",
                "watch",
            )
        )

    us_stocks = data["stocks"][
        data["stocks"]["commodity"].eq(commodity)
        & data["stocks"]["state_alpha"].eq("US")
        & data["stocks"]["year"].between(years[0], years[1])
    ].copy()
    stock_context = latest_stock_context(us_stocks)
    latest_stock = stock_context.get("latest", pd.Series(dtype="object"))
    if not latest_stock.empty:
        five_year_gap = stock_context.get("five_year_gap")
        yoy_change = stock_context.get("yoy_change")
        cards.append(
            signal_card(
                "Stocks",
                f"Latest NASS Stocks ({stock_month_label(latest_stock.get('stock_month'))})",
                fmt_number(latest_stock.get("stocks_mbu"), " mbu", 0),
                fmt_change_detail(five_year_gap, " mbu", 0, "vs 5Y same report")
                if pd.notna(five_year_gap)
                else f"Report date {fmt_date(latest_stock.get('stock_date'))}",
                signal_status_from_change(five_year_gap, tight_when_positive=False, threshold=25.0),
            )
        )
        cards.append(
            signal_card(
                "Stocks",
                "Stocks YoY",
                fmt_signed_number(yoy_change, " mbu", 0) or "Flat",
                f"Same report month; {fmt_date(latest_stock.get('stock_date'))}",
                signal_status_from_change(yoy_change, tight_when_positive=False, threshold=25.0),
            )
        )

    validation = build_wasde_stock_validation(us_stocks, wasde_df)
    if not validation.empty:
        latest_validation = validation.iloc[0]
        validation_gap = latest_validation.get("difference_mbu")
        cards.append(
            signal_card(
                "Stocks",
                "Sep Stocks vs WASDE Ending",
                fmt_signed_number(validation_gap, " mbu", 0) or "Flat",
                f"{latest_validation.get('marketing_year', '-')} final stock validation",
                signal_status_from_change(validation_gap, tight_when_positive=False, threshold=10.0),
            )
        )

    feed_residual = data["feed_residual"][
        data["feed_residual"]["commodity"].eq(commodity)
        & data["feed_residual"]["crop_year"].between(years[0], years[1])
    ].copy()
    latest_disappearance = latest_actual_row(feed_residual, "quarter_end")
    if not latest_disappearance.empty:
        cards.append(
            signal_card(
                "Disappearance",
                "Latest Quarterly Disappearance",
                fmt_number(latest_disappearance.get("total_disappearance_mbu"), " mbu", 0),
                f"{latest_disappearance.get('quarter_label', '-')}; {latest_disappearance.get('coverage_status', '-')}",
                "watch"
                if "partial" in str(latest_disappearance.get("coverage_status", "")).lower()
                else "neutral",
            )
        )

    return cards


data = load_data()

st.title("U.S. Corn & Soybean Dashboard")

commodities = sorted(data["wasde"]["commodity"].dropna().unique())
with st.sidebar:
    commodity = st.selectbox("Commodity", commodities, index=0)
    state_options = sorted(
        state for state in data["supply"]["state_alpha"].dropna().unique() if state != "US"
    )
    state = st.selectbox("State", ["US"] + state_options, index=0)
    year_min = int(data["supply"]["year"].min())
    year_max = int(data["supply"]["year"].max())
    years = st.slider("Crop Years", year_min, year_max, (max(year_min, year_max - 10), year_max))

commodity_label = "Corn" if commodity == "CORN" else "Soybeans"
scope_label = "U.S." if state == "US" else state

wasde = data["wasde"]
wasde_c = wasde[wasde["commodity"].eq(commodity)].copy()
wasde_c["crop_year"] = wasde_c["marketing_year"].map(marketing_year_start)
wasde_c = wasde_c[
    wasde_c["crop_year"].isna() | wasde_c["crop_year"].between(years[0], years[1])
].sort_values("column_order")
latest_wasde = wasde_c.iloc[-1] if not wasde_c.empty else pd.Series(dtype="object")

supply_scope = data["supply"][
    data["supply"]["commodity"].eq(commodity)
    & data["supply"]["year"].between(years[0], years[1])
    & data["supply"]["state_alpha"].eq(state)
].copy()

condition_scope = data["condition"][
    data["condition"]["commodity"].eq(commodity)
    & data["condition"]["state_alpha"].eq(state)
    & data["condition"]["year"].between(years[0], years[1])
].copy()

stocks_scope = data["stocks"][
    data["stocks"]["commodity"].eq(commodity)
    & data["stocks"]["state_alpha"].eq(state)
    & data["stocks"]["year"].between(years[0], years[1])
].copy()

production_signals = build_production_model(
    wasde_c,
    data["supply"],
    data["condition"],
    data["drought"],
    commodity,
    0.0,
    0.0,
)
production_reference = build_production_reference(wasde_c, data["supply"])
balance_model = build_balance_model(wasde_c, production_reference)

(
    tab_balance,
    tab_production,
    tab_demand,
    tab_stocks,
    tab_field_weather,
    tab_wasde,
    tab_data,
) = st.tabs(
    [
        "Balance Cockpit",
        "Production",
        "Demand",
        "Stocks",
        "Field & Weather",
        "WASDE Benchmark",
        "Data Explorer",
    ]
)

with tab_balance:
    st.subheader(f"{commodity_label} Balance Cockpit")
    if state != "US":
        st.markdown(
            "<div class='small-muted'>Balance sheet metrics are national. "
            "The state selector affects the production, field, weather, and stocks detail tabs.</div>",
            unsafe_allow_html=True,
        )

    if balance_model.empty:
        st.info("No WASDE balance rows for this crop-year range.")
    else:
        balance_labels = balance_model["balance_label"].tolist()
        selected_balance_label = st.selectbox(
            "Marketing Year / WASDE Vintage",
            balance_labels,
            index=len(balance_labels) - 1,
            key="balance_model_row",
        )
        balance_row = balance_model[
            balance_model["balance_label"].eq(selected_balance_label)
        ].iloc[0]
        selected_prior_row = prior_balance_row(balance_model, balance_row)
        signal_cards = build_balance_signal_cards(
            balance_row,
            balance_model,
            production_signals,
            wasde_c,
            data,
            commodity,
            years,
        )

        tight_count = sum(card["status"] == "tight" for card in signal_cards)
        loose_count = sum(card["status"] == "loose" for card in signal_cards)
        watch_count = sum(card["status"] == "watch" for card in signal_cards)
        st.markdown(
            "<div class='small-muted'>Color marks: red = tighter / price-supportive, "
            "green = looser, amber = watch or incomplete coverage, gray = neutral. "
            f"Current mix: {tight_count} tight, {loose_count} loose, {watch_count} watch.</div>",
            unsafe_allow_html=True,
        )
        render_signal_cards(signal_cards)

        st.markdown(
            f"<div class='small-muted'>Balance logic: production uses "
            f"{balance_row.get('production_source', '-')}; demand uses "
            f"{balance_row.get('use_source', '-')}. Ending stocks and ending stocks-to-use are "
            "recalculated from projected marketing-year ending stocks and annual use.</div>",
            unsafe_allow_html=True,
        )

        left, right = st.columns([1.15, 1])
        with left:
            st.markdown("#### Selected Balance Sheet")
            st.dataframe(
                balance_snapshot_table(balance_row, selected_prior_row),
                width="stretch",
                hide_index=True,
            )
        with right:
            st.markdown("#### Signal Details")
            signal_table = pd.DataFrame(signal_cards)[
                ["module", "metric", "value", "detail", "status"]
            ].rename(
                columns={
                    "module": "Module",
                    "metric": "Metric",
                    "value": "Value",
                    "detail": "Detail",
                    "status": "Marker",
                }
            )
            signal_table["Marker"] = signal_table["Marker"].map(signal_badge)
            st.dataframe(signal_table, width="stretch", hide_index=True)

        st.markdown("#### Ending Stocks-to-Use Benchmark")
        st.markdown(
            "<div class='small-muted'>This is the balance-sheet ratio: "
            "marketing-year ending stocks divided by annual total use. It is not "
            "the same as the Stocks tab coverage ratio, which uses the latest "
            "reported NASS inventory date.</div>",
            unsafe_allow_html=True,
        )
        stu_history = balance_model[
            [
                "balance_label",
                "balance_short_label",
                "column_order",
                "my_stocks_to_use_pct",
                "stocks_to_use_pct",
            ]
        ].melt(
            id_vars=["balance_label", "balance_short_label", "column_order"],
            value_vars=["my_stocks_to_use_pct", "stocks_to_use_pct"],
            var_name="series",
            value_name="stocks_to_use_value",
        )
        stu_history["series"] = stu_history["series"].map(
            {
                "my_stocks_to_use_pct": "My Model",
                "stocks_to_use_pct": "WASDE",
            }
        )
        line_chart(
            stu_history.dropna(subset=["stocks_to_use_value"]),
            "balance_short_label",
            "stocks_to_use_value",
            "series",
            height=300,
            x_title="Marketing Year",
            y_title="Ending Stocks-to-Use (%)",
            color_title="Series",
            y_zero=False,
            x_label_angle=0,
            x_label_limit=80,
            x_sort_field="column_order",
            extra_tooltips=[
                {"field": "balance_label", "type": "nominal", "title": "Full Period"}
            ],
        )

with tab_production:
    st.subheader(f"U.S. {commodity_label} Production")
    st.markdown(
        "<div class='small-muted'>This page shows official WASDE projections, "
        "weekly field/weather signals, and NASS historical supply. No production "
        "forecast is calculated in this tab.</div>",
        unsafe_allow_html=True,
    )

    st.markdown("#### WASDE Projections")
    wasde_projection = wasde_c[wasde_c["estimate_type"].eq("projection")].copy()
    if wasde_projection.empty:
        st.info("No WASDE projection rows are available for this crop-year range.")
    else:
        latest_projection = wasde_projection.sort_values("column_order").iloc[-1]
        w1, w2, w3, w4 = st.columns(4)
        w1.metric("Planted Acres", fmt_number(latest_projection.get("area_planted"), " mil ac", 1))
        w2.metric("Harvested Acres", fmt_number(latest_projection.get("area_harvested"), " mil ac", 1))
        w3.metric("Yield", fmt_number(latest_projection.get("yield_per_harvested_acre"), " bu/ac", 1))
        w4.metric("Production", fmt_number(latest_projection.get("production"), " mbu", 0))

        projection_table = (
            wasde_projection.sort_values(["marketing_year", "column_order"])[
                [
                    "report_month",
                    "marketing_year",
                    "vintage",
                    "area_planted",
                    "area_harvested",
                    "yield_per_harvested_acre",
                    "production",
                ]
            ]
            .rename(
                columns={
                    "report_month": "Report Month",
                    "marketing_year": "Marketing Year",
                    "vintage": "Vintage",
                    "area_planted": "Planted Acres (mil)",
                    "area_harvested": "Harvested Acres (mil)",
                    "yield_per_harvested_acre": "Yield (bu/ac)",
                    "production": "Production (mbu)",
                }
            )
        )
        st.dataframe(projection_table, width="stretch", hide_index=True)
        st.markdown(
            "<div class='small-muted'>This mart table currently contains the projection "
            "vintages available in the downloaded WASDE file. A full month-by-month history "
            "requires saving each WASDE release as a separate snapshot.</div>",
            unsafe_allow_html=True,
        )

    st.divider()
    st.markdown("#### Weekly Signals")
    if production_signals.empty:
        st.info("No weekly signal rows are available for this crop-year range.")
    else:
        signal_labels = production_signals["balance_label"].tolist()
        selected_signal_label = st.selectbox(
            "Marketing Year / WASDE Vintage",
            signal_labels,
            index=len(signal_labels) - 1,
            key="production_signal_row",
        )
        signal_row = production_signals[
            production_signals["balance_label"].eq(selected_signal_label)
        ].iloc[0]
        st.dataframe(
            production_signal_table(signal_row),
            width="stretch",
            hide_index=True,
        )

    st.divider()
    st.subheader("U.S. Historical Supply")
    historical_supply_scope = data["supply"][
        data["supply"]["commodity"].eq(commodity)
        & data["supply"]["year"].between(years[0], years[1])
        & data["supply"]["state_alpha"].eq("US")
    ].copy()
    if historical_supply_scope.empty:
        st.info("No supply records for this filter.")
    else:
        s1, s2, s3, s4 = st.columns(4)
        production_value, production_delta, production_year = metric_snapshot(
            historical_supply_scope, "production_mbu", " mbu", 0
        )
        yield_value, yield_delta, yield_year = metric_snapshot(
            historical_supply_scope, "yield_bu_per_acre", " bu/ac", 1
        )
        planted_value, planted_delta, planted_year = metric_snapshot(
            historical_supply_scope, "planted_acres_mil", " mil ac", 1
        )
        harvested_value, harvested_delta, harvested_year = metric_snapshot(
            historical_supply_scope, "harvested_acres_mil", " mil ac", 1
        )

        s1.metric(
            f"Production ({production_year or '-'})",
            production_value,
            production_delta,
        )
        s2.metric(f"Yield ({yield_year or '-'})", yield_value, yield_delta)
        s3.metric(f"Planted ({planted_year or '-'})", planted_value, planted_delta)
        s4.metric(f"Harvested ({harvested_year or '-'})", harvested_value, harvested_delta)

        production_plot = historical_supply_scope.dropna(subset=["production_mbu"])
        yield_plot = historical_supply_scope.dropna(subset=["yield_bu_per_acre"])
        acres_long = historical_supply_scope.melt(
            id_vars=["commodity", "year", "state_alpha"],
            value_vars=["planted_acres_mil", "harvested_acres_mil"],
            var_name="metric",
            value_name="acres_mil",
        )
        acres_long["metric"] = acres_long["metric"].map(
            {
                "planted_acres_mil": "Planted",
                "harvested_acres_mil": "Harvested",
            }
        )

        supply_left, supply_right = st.columns([1, 1])
        with supply_left:
            st.markdown("#### Production")
            if production_plot.empty:
                st.info("No production records for this filter.")
            else:
                line_chart(
                    production_plot,
                    "year",
                    "production_mbu",
                    height=300,
                    x_title="Crop Year",
                    y_title="Production (mbu)",
                    y_zero=False,
                )
        with supply_right:
            st.markdown("#### Yield")
            if yield_plot.empty:
                st.info("No yield records for this filter.")
            else:
                line_chart(
                    yield_plot,
                    "year",
                    "yield_bu_per_acre",
                    height=300,
                    x_title="Crop Year",
                    y_title="Yield (bu/ac)",
                    y_zero=False,
                )

        st.markdown("#### Acreage")
        acres_plot = acres_long.dropna(subset=["acres_mil"])
        if acres_plot.empty:
            st.info("No acreage records for this filter.")
        else:
            line_chart(
                acres_plot,
                "year",
                "acres_mil",
                "metric",
                height=300,
                x_title="Crop Year",
                y_title="Acres (million)",
                color_title="Acreage",
                y_zero=False,
            )

        supply_table = (
            historical_supply_scope[
                [
                    "year",
                    "state_alpha",
                    "planted_acres_mil",
                    "harvested_acres_mil",
                    "yield_bu_per_acre",
                    "production_mbu",
                ]
            ]
            .sort_values("year", ascending=False)
            .rename(
                columns={
                    "year": "Year",
                    "state_alpha": "State",
                    "planted_acres_mil": "Planted Acres (mil)",
                    "harvested_acres_mil": "Harvested Acres (mil)",
                    "yield_bu_per_acre": "Yield (bu/ac)",
                    "production_mbu": "Production (mbu)",
                }
            )
        )
        st.dataframe(supply_table, width="stretch", hide_index=True)

with tab_field_weather:
    st.subheader(f"{scope_label} {commodity_label} Field & Weather Signals")
    st.markdown(
        "<div class='small-muted'>These signals provide field and weather context for "
        "the official production projections.</div>",
        unsafe_allow_html=True,
    )
    progress_scope = data["progress"][
        data["progress"]["commodity"].eq(commodity)
        & data["progress"]["state_alpha"].eq(state)
        & data["progress"]["year"].between(years[0], years[1])
    ].copy()
    crop_year_options = sorted(
        set(progress_scope["year"].dropna().astype(int))
        | set(condition_scope["year"].dropna().astype(int))
    )
    default_crop_years = crop_year_options[-5:]
    selected_crop_years = st.multiselect(
        "Comparison Years",
        crop_year_options,
        default=default_crop_years,
    )

    if not selected_crop_years:
        st.info("Select at least one comparison year.")
    else:
        progress_scope = progress_scope[progress_scope["year"].isin(selected_crop_years)]
        condition_plot_scope = condition_scope[condition_scope["year"].isin(selected_crop_years)]

        crop_left, crop_right = st.columns([1, 1])
        with crop_left:
            st.subheader("Progress")
            stages = sorted(progress_scope["stage"].dropna().unique())
            if stages:
                latest_progress_year = max(selected_crop_years)
                default_stage = default_stage_for_year(
                    progress_scope,
                    commodity,
                    latest_progress_year,
                    stages,
                )
                stage = st.selectbox("Stage", stages, index=stages.index(default_stage))
                progress_stage = progress_scope[progress_scope["stage"].eq(stage)]
                latest_progress = latest_by_date(
                    progress_stage[progress_stage["year"].eq(latest_progress_year)],
                    "week_ending",
                )
                latest_progress_row = (
                    latest_progress.iloc[-1] if not latest_progress.empty else pd.Series(dtype="object")
                )
                st.metric(
                    f"{latest_progress_year} {stage.title()}",
                    fmt_number(latest_progress_row.get("pct"), "%", 1),
                )
                seasonal_line_chart(progress_stage, "pct", "Progress (%)", height=360)
            else:
                st.info("No progress records for this filter.")

        with crop_right:
            st.subheader("Condition")
            if condition_plot_scope.empty:
                st.info("No condition records for this filter.")
            else:
                condition_metric = st.selectbox(
                    "Condition Metric",
                    ["good_excellent", "poor_very_poor", "condition_index_0_100"],
                    index=0,
                    format_func=CONDITION_LABELS.get,
                )
                condition_label = {
                    "good_excellent": "Good/Excellent (%)",
                    "poor_very_poor": "Poor/Very Poor (%)",
                    "condition_index_0_100": "Condition Index",
                }[condition_metric]
                condition_suffix = "" if condition_metric == "condition_index_0_100" else "%"
                latest_condition_year = max(selected_crop_years)
                latest_condition = latest_by_date(
                    condition_plot_scope[condition_plot_scope["year"].eq(latest_condition_year)],
                    "week_ending",
                )
                latest_condition_row = (
                    latest_condition.iloc[-1] if not latest_condition.empty else pd.Series(dtype="object")
                )
                st.metric(
                    f"{latest_condition_year} {condition_label}",
                    fmt_number(latest_condition_row.get(condition_metric), condition_suffix, 1),
                )
                seasonal_line_chart(
                    condition_plot_scope,
                    condition_metric,
                    condition_label,
                    height=360,
                )

    st.divider()
    st.subheader("Drought")
    default_drought_states = (
        [state]
        if state != "US"
        else KEY_DROUGHT_STATES.get(commodity, KEY_DROUGHT_STATES["CORN"])
    )
    d_states = st.multiselect(
        "States",
        sorted(data["drought"]["state_alpha"].dropna().unique()),
        default=default_drought_states,
    )
    drought_metric = st.selectbox(
        "Drought Metric", ["dsci", "d1_plus", "d2_plus", "d3_plus"], index=0
    )
    drought_plot = data["drought"][data["drought"]["state_alpha"].isin(d_states)].copy()
    drought_plot["series_label"] = drought_plot["state_alpha"]
    if drought_metric == "dsci":
        weighted_drought = build_weighted_drought_weekly(
            data["drought"],
            data["supply"],
            commodity,
        )
        if not weighted_drought.empty:
            weighted_drought_plot = weighted_drought.rename(
                columns={"key_state_dsci": "dsci"}
            ).copy()
            weighted_drought_plot["state_alpha"] = "US_WEIGHTED"
            weighted_drought_plot["series_label"] = f"{commodity_label} Weighted DSCI"
            drought_plot = pd.concat(
                [
                    drought_plot,
                    weighted_drought_plot[
                        ["mapdate", "state_alpha", "series_label", "dsci"]
                    ],
                ],
                ignore_index=True,
                sort=False,
            )
        st.markdown(
            f"<div class='small-muted'>Weighted DSCI uses "
            f"{', '.join(KEY_DROUGHT_STATES.get(commodity, []))} with prior 5-year "
            "state production weights.</div>",
            unsafe_allow_html=True,
        )
    if drought_plot.empty:
        st.info("No drought records for this filter.")
    else:
        line_chart(drought_plot, "mapdate", drought_metric, "series_label", height=390)
        latest_drought_table = (
            drought_plot.sort_values("mapdate")
            .groupby("series_label", as_index=False)
            .tail(1)
            .sort_values(drought_metric, ascending=False)
        )
        st.dataframe(latest_drought_table, width="stretch", hide_index=True)

with tab_stocks:
    st.subheader(f"{scope_label} {commodity_label} Stocks")
    st.markdown(
        "<div class='small-muted'>Quarterly NASS stocks show inventory pressure, "
        "seasonal tightness, and how reported inventories compare with the "
        "balance sheet.</div>",
        unsafe_allow_html=True,
    )
    if stocks_scope.empty:
        st.info("No stock records for this filter.")
    else:
        stock_context = latest_stock_context(stocks_scope)
        latest_stock = stock_context.get("latest", pd.Series(dtype="object"))
        latest_date = latest_stock.get("stock_date")
        us_stock_same_date = data["stocks"][
            data["stocks"]["commodity"].eq(commodity)
            & data["stocks"]["state_alpha"].eq("US")
            & data["stocks"]["stock_date"].eq(latest_date)
        ]
        state_share_pct = (
            latest_stock.get("stocks_mbu") / us_stock_same_date.iloc[-1]["stocks_mbu"] * 100
            if state != "US"
            and not us_stock_same_date.empty
            and pd.notna(us_stock_same_date.iloc[-1]["stocks_mbu"])
            else pd.NA
        )
        reported_stock_use_coverage_pct = (
            latest_stock.get("stocks_mbu") / latest_wasde.get("use_total") * 100
            if state == "US"
            and pd.notna(latest_stock.get("stocks_mbu"))
            and pd.notna(latest_wasde.get("use_total"))
            else pd.NA
        )

        k1, k2, k3, k4 = st.columns(4)
        k1.metric(
            f"Latest Stocks ({stock_month_label(latest_stock.get('stock_month'))})",
            fmt_number(latest_stock.get("stocks_mbu"), " mbu", 0),
            fmt_signed_number(stock_context.get("yoy_change"), " mbu YoY", 0),
        )
        k2.metric(
            "5Y Avg Same Report",
            fmt_number(stock_context.get("five_year_avg"), " mbu", 0),
            fmt_signed_number(stock_context.get("five_year_gap"), " mbu vs 5Y", 0),
        )
        k3.metric(
            "On-Farm Share",
            fmt_number(latest_stock.get("on_farm_share_pct"), "%", 1),
        )
        k4.metric(
            "Reported Stocks / Annual Use" if state == "US" else "State Share of U.S.",
            fmt_number(
                reported_stock_use_coverage_pct if state == "US" else state_share_pct,
                "%",
                1,
            ),
            help=(
                "Latest NASS reported stocks divided by latest WASDE annual total use. "
                "This is an inventory coverage ratio, not WASDE ending stocks-to-use."
            )
            if state == "US"
            else None,
        )

        stock_year_options = sorted(stocks_scope["stock_date"].dt.year.dropna().astype(int).unique())
        default_stock_years = stock_year_options[-6:]
        selected_stock_years = st.multiselect(
            "Comparison Years",
            stock_year_options,
            default=default_stock_years,
            key="stock_comparison_years",
        )
        stock_plot_scope = stocks_scope[
            stocks_scope["stock_date"].dt.year.isin(selected_stock_years)
        ].copy()

        stock_left, stock_right = st.columns([1.2, 0.8])
        with stock_left:
            st.markdown("#### Seasonal Stock Pattern")
            stock_seasonal_chart(stock_plot_scope, height=340)
        with stock_right:
            st.markdown("#### On / Off Farm Structure")
            on_off_plot = pd.DataFrame(
                [
                    {"Position": "On Farm", "Stocks": latest_stock.get("on_farm_stocks_mbu")},
                    {"Position": "Off Farm", "Stocks": latest_stock.get("off_farm_stocks_mbu")},
                ]
            ).dropna(subset=["Stocks"])
            if on_off_plot.empty:
                st.info("No on/off farm split is available for this filter.")
            else:
                bar_chart(on_off_plot, "Position", "Stocks", height=260)
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Stock Date": latest_stock.get("stock_date"),
                            "Total (mbu)": latest_stock.get("stocks_mbu"),
                            "On Farm (mbu)": latest_stock.get("on_farm_stocks_mbu"),
                            "Off Farm (mbu)": latest_stock.get("off_farm_stocks_mbu"),
                            "On Farm Share (%)": latest_stock.get("on_farm_share_pct"),
                        }
                    ]
                ),
                width="stretch",
                hide_index=True,
            )

        st.markdown("#### WASDE Ending Stocks Comparison")
        stock_validation_scope = data["stocks"][
            data["stocks"]["commodity"].eq(commodity)
            & data["stocks"]["state_alpha"].eq("US")
            & data["stocks"]["year"].between(years[0], years[1])
        ].copy()
        validation = build_wasde_stock_validation(stock_validation_scope, wasde_c)
        if validation.empty:
            st.info("No Sep 1 NASS stocks are available to compare with WASDE ending stocks.")
        else:
            validation_table = (
                validation[
                    [
                        "marketing_year",
                        "stock_date",
                        "stocks_mbu",
                        "ending_stocks",
                        "difference_mbu",
                        "difference_pct",
                        "estimate_type",
                        "vintage",
                    ]
                ]
                .rename(
                    columns={
                        "marketing_year": "Marketing Year",
                        "stock_date": "NASS Sep 1 Date",
                        "stocks_mbu": "NASS Sep 1 Stocks (mbu)",
                        "ending_stocks": "WASDE Ending Stocks (mbu)",
                        "difference_mbu": "Difference (mbu)",
                        "difference_pct": "Difference (%)",
                        "estimate_type": "WASDE Type",
                        "vintage": "Vintage",
                    }
                )
            )
            st.dataframe(validation_table, width="stretch", hide_index=True)

        st.markdown("#### State Stock Detail")
        latest_us_date = (
            data["stocks"][
                data["stocks"]["commodity"].eq(commodity)
                & data["stocks"]["state_alpha"].eq("US")
            ]["stock_date"].max()
        )
        state_latest = data["stocks"][
            data["stocks"]["commodity"].eq(commodity)
            & data["stocks"]["stock_date"].eq(latest_us_date)
            & ~data["stocks"]["state_alpha"].eq("US")
        ].copy()
        if state_latest.empty:
            st.info("No state stock detail is available for the latest report.")
        else:
            top_states = state_latest.sort_values("stocks_mbu", ascending=False).head(10)
            bar_chart(top_states, "state_alpha", "stocks_mbu", height=300)
            state_table = (
                state_latest.sort_values("stocks_mbu", ascending=False)[
                    [
                        "stock_date",
                        "state_alpha",
                        "state_name",
                        "stocks_mbu",
                        "on_farm_stocks_mbu",
                        "off_farm_stocks_mbu",
                        "on_farm_share_pct",
                    ]
                ]
                .rename(
                    columns={
                        "stock_date": "Stock Date",
                        "state_alpha": "State",
                        "state_name": "State Name",
                        "stocks_mbu": "Total Stocks (mbu)",
                        "on_farm_stocks_mbu": "On Farm (mbu)",
                        "off_farm_stocks_mbu": "Off Farm (mbu)",
                        "on_farm_share_pct": "On Farm Share (%)",
                    }
                )
            )
            st.dataframe(state_table, width="stretch", hide_index=True)

        st.markdown("#### Raw Stock Records")
        st.dataframe(
            stocks_scope.sort_values("stock_date", ascending=False),
            width="stretch",
            hide_index=True,
        )

with tab_demand:
    st.subheader(f"{commodity_label} Demand")
    st.markdown(
        "<div class='small-muted'>KPI cards use the latest WASDE forecast/estimate "
        "row, not realized demand. Available high-frequency actuals are shown "
        "separately below.</div>",
        unsafe_allow_html=True,
    )

    demand_components = build_demand_components(wasde_c, commodity)
    if demand_components.empty:
        st.info("No demand records for this crop-year range.")
    else:
        latest_order = demand_components["column_order"].max()
        latest_demand = demand_components[
            demand_components["column_order"].eq(latest_order)
        ].copy()
        largest_component = latest_demand.sort_values("mbu").iloc[-1]
        export_component = component_row(latest_demand, "Exports")
        fourth_component_name = "Ethanol" if commodity == "CORN" else "Other Use"
        fourth_component = component_row(latest_demand, fourth_component_name)

        d1, d2, d3, d4 = st.columns(4)
        d1.metric(
            "WASDE Forecast Total Use",
            fmt_number(latest_wasde.get("use_total"), " mbu", 0),
        )
        d2.metric(
            forecast_component_label(
                f"Largest: {largest_component['component']}",
                largest_component.get("share_pct"),
            ),
            fmt_number(largest_component.get("mbu"), " mbu", 0),
        )
        d3.metric(
            forecast_component_label("Exports", export_component.get("share_pct")),
            fmt_number(
                export_component.get("mbu"),
                " mbu",
                0,
            ),
        )
        d4.metric(
            forecast_component_label(fourth_component_name, fourth_component.get("share_pct")),
            fmt_number(
                fourth_component.get("mbu"),
                " mbu",
                0,
            ),
        )

        demand_left, demand_right = st.columns([1, 1])
        with demand_left:
            st.markdown("#### End-Use Composition")
            stacked_bar_chart(
                demand_components,
                "period_short",
                "mbu",
                "component",
                height=340,
                y_title="Demand (mbu)",
                color_title="End Use",
                x_sort_field="column_order",
                period_tooltip_field="period",
            )
        with demand_right:
            st.markdown("#### End-Use Share")
            stacked_bar_chart(
                demand_components,
                "period_short",
                "share_pct",
                "component",
                height=340,
                y_title="Share of Total Use (%)",
                color_title="End Use",
                y_domain=[0, 100],
                x_sort_field="column_order",
                period_tooltip_field="period",
            )

        demand_table = (
            demand_components.pivot_table(
                index=[
                    "period",
                    "marketing_year",
                    "estimate_type",
                    "vintage",
                    "column_order",
                    "use_total",
                ],
                columns="component",
                values="mbu",
                aggfunc="first",
            )
            .reset_index()
            .sort_values("column_order")
        )
        demand_table.columns.name = None
        demand_table = demand_table.drop(columns=["column_order"])
        st.dataframe(demand_table, width="stretch", hide_index=True)

    export_sales_scope = data["export_sales"][
        data["export_sales"]["commodity"].eq(commodity)
    ].copy()
    export_inspections_scope = data["export_inspections"][
        data["export_inspections"]["commodity"].eq(commodity)
    ].copy()
    if not export_sales_scope.empty or not export_inspections_scope.empty:
        st.markdown("#### Export Actual Monitor")
        latest_sales = latest_actual_row(export_sales_scope, "week_ending")
        latest_inspections = latest_actual_row(export_inspections_scope, "week_ending")
        x1, x2, x3, x4 = st.columns(4)
        x1.metric(
            "Net Sales",
            fmt_number(latest_sales.get("net_sales_mbu"), " mbu/wk", 1),
        )
        x2.metric(
            "Commitments",
            fmt_number(latest_sales.get("total_commitments_mbu"), " mbu", 0),
        )
        x3.metric(
            "Outstanding Sales",
            fmt_number(latest_sales.get("outstanding_sales_mbu"), " mbu", 0),
        )
        x4.metric(
            "Export Inspections",
            fmt_number(latest_inspections.get("weekly_inspections_mbu"), " mbu/wk", 1),
        )
        if not export_inspections_scope.empty:
            line_chart(
                export_inspections_scope,
                "week_ending",
                "weekly_inspections_mbu",
                height=280,
                y_title="Inspections (mbu/wk)",
                y_zero=False,
            )
    else:
        st.info(
            "Export sales and export inspections marts are ready, but no clean source "
            "data has been added yet."
        )

    if commodity == "CORN":
        st.markdown("#### Ethanol Actual Monitor")
        st.markdown(
            "<div class='small-muted'>Ethanol is separated because weekly EIA data "
            "is observable actual demand. Feed & residual is usually larger, but it "
            "is not directly observed in real time. The 13-week average smooths "
            "weekly holiday, outage, and maintenance noise into a quarterly run rate.</div>",
            unsafe_allow_html=True,
        )
        ethanol = ethanol_monitor_frame(data["ethanol"])
        if ethanol.empty:
            st.info("No ethanol records available.")
        else:
            latest_ethanol = ethanol.iloc[-1]
            e1, e2, e3, e4 = st.columns(4)
            e1.metric(
                "Production",
                fmt_number(latest_ethanol.get("ethanol_production_kbd"), " kbd", 0),
            )
            e2.metric(
                "Stocks",
                fmt_number(latest_ethanol.get("ethanol_stocks_kbbl"), " kbbl", 0),
            )
            e3.metric(
                "Implied Corn Use",
                fmt_number(latest_ethanol.get("implied_corn_use_mbu"), " mbu/wk", 1),
            )
            e4.metric(
                "13W Avg Run Rate",
                fmt_number(latest_ethanol.get("implied_corn_use_13w_avg"), " mbu/wk", 1),
            )

            ethanol_recent = ethanol.tail(156).copy()
            ethanol_long = ethanol_recent.melt(
                id_vars="period",
                value_vars=["implied_corn_use_mbu", "implied_corn_use_13w_avg"],
                var_name="series",
                value_name="mbu_per_week",
            ).dropna(subset=["mbu_per_week"])
            ethanol_long["series_label"] = ethanol_long["series"].map(
                {
                    "implied_corn_use_mbu": "Weekly implied corn use",
                    "implied_corn_use_13w_avg": "13W average",
                }
            )
            line_chart(
                ethanol_long,
                "period",
                "mbu_per_week",
                "series_label",
                height=330,
                x_title="Year",
                y_title="Corn Use (mbu/wk)",
                color_title="Series",
                y_zero=False,
                x_axis_format="%Y",
                x_tick_interval="year",
            )
            st.dataframe(
                ethanol.sort_values("period", ascending=False),
                width="stretch",
                hide_index=True,
            )
        st.markdown("#### Corn FSI Actual Monitor")
        corn_fsi_scope = data["corn_fsi"][
            data["corn_fsi"]["commodity"].eq("CORN")
        ].copy()
        if corn_fsi_scope.empty:
            st.info(
                "The corn FSI mart is ready, but no NASS monthly processing data "
                "has been fetched yet."
            )
        else:
            latest_fsi = latest_actual_row(corn_fsi_scope, "month")
            i1, i2, i3 = st.columns(3)
            i1.metric(
                "Fuel Alcohol",
                fmt_number(latest_fsi.get("fuel_alcohol_use_mbu"), " mbu/month", 1),
            )
            i2.metric(
                "Other FSI",
                fmt_number(latest_fsi.get("other_fsi_use_mbu"), " mbu/month", 1),
            )
            i3.metric(
                "Total FSI",
                fmt_number(latest_fsi.get("fsi_use_mbu"), " mbu/month", 1),
            )
            fsi_long = corn_fsi_scope.melt(
                id_vars="month",
                value_vars=[
                    "fuel_alcohol_use_mbu",
                    "other_fsi_use_mbu",
                    "fsi_use_mbu",
                ],
                var_name="series",
                value_name="mbu_per_month",
            ).dropna(subset=["mbu_per_month"])
            fsi_long["series_label"] = fsi_long["series"].map(
                {
                    "fuel_alcohol_use_mbu": "Fuel alcohol",
                    "other_fsi_use_mbu": "Other FSI",
                    "fsi_use_mbu": "Total FSI",
                }
            )
            line_chart(
                fsi_long,
                "month",
                "mbu_per_month",
                "series_label",
                height=300,
                y_title="Corn Use (mbu/month)",
                color_title="Series",
                y_zero=False,
            )
        st.markdown("#### Quarterly Disappearance / Feed Residual")
        feed_residual_scope = data["feed_residual"][
            data["feed_residual"]["commodity"].eq("CORN")
        ].copy()
        if feed_residual_scope.empty:
            st.info("No quarterly feed/residual records available.")
        else:
            latest_feed = latest_actual_row(feed_residual_scope, "quarter_end")
            f1, f2, f3 = st.columns(3)
            f1.metric(
                "Total Disappearance",
                fmt_number(latest_feed.get("total_disappearance_mbu"), " mbu/qtr", 0),
            )
            f2.metric(
                "Residual After Known Uses",
                fmt_number(latest_feed.get("residual_after_known_uses_mbu"), " mbu/qtr", 0),
            )
            f3.metric(
                f"WASDE Annual Feed & Residual ({latest_feed.get('marketing_year', '-')})",
                fmt_number(latest_feed.get("wasde_feed_residual_annual_mbu"), " mbu", 0),
            )
            line_chart(
                feed_residual_scope,
                "quarter_end",
                "total_disappearance_mbu",
                height=280,
                y_title="Total Disappearance (mbu/qtr)",
                y_zero=False,
            )
            st.dataframe(
                feed_residual_scope.sort_values("quarter_end", ascending=False),
                width="stretch",
                hide_index=True,
            )
    else:
        st.markdown("#### Soybean Crush Actual Monitor")
        soybean_crush_scope = data["soybean_crush"][
            data["soybean_crush"]["commodity"].eq("SOYBEANS")
        ].copy()
        if soybean_crush_scope.empty:
            st.info(
                "The soybean crush mart is ready, but no clean monthly crush source "
                "data has been added yet."
            )
        else:
            latest_crush = latest_actual_row(soybean_crush_scope, "month")
            c1, c2, c3 = st.columns(3)
            c1.metric(
                "Monthly Crush",
                fmt_number(latest_crush.get("soybean_crush_mbu"), " mbu", 1),
            )
            c2.metric(
                "Oil Stocks",
                fmt_number(latest_crush.get("soybean_oil_stocks_mlb"), " mlb", 0),
            )
            c3.metric(
                "Meal Production",
                fmt_number(
                    latest_crush.get("soybean_meal_production_short_tons"),
                    " short tons",
                    0,
                ),
            )
            line_chart(
                soybean_crush_scope,
                "month",
                "soybean_crush_mbu",
                height=280,
                y_title="Soybean Crush (mbu/month)",
                y_zero=False,
            )
            st.dataframe(
                soybean_crush_scope.sort_values("month", ascending=False),
                width="stretch",
                hide_index=True,
            )

with tab_wasde:
    st.subheader(f"{commodity_label} WASDE Benchmark")
    if wasde_c.empty:
        st.info("No WASDE rows for this crop-year range.")
    else:
        w1, w2, w3, w4 = st.columns(4)
        w1.metric("WASDE Production", fmt_number(latest_wasde.get("production"), " mbu", 0))
        w2.metric("WASDE Use Total", fmt_number(latest_wasde.get("use_total"), " mbu", 0))
        w3.metric("WASDE Ending Stocks", fmt_number(latest_wasde.get("ending_stocks"), " mbu", 0))
        w4.metric(
            "WASDE Ending Stocks-to-Use",
            fmt_number(latest_wasde.get("stocks_to_use_pct"), "%", 1),
        )

        st.markdown(
            f"<div class='small-muted'>WASDE {latest_wasde.get('report_month', '-')}; "
            f"{latest_wasde.get('marketing_year', '-')} {latest_wasde.get('estimate_type', '-')} "
            f"{latest_wasde.get('vintage', '-')} vintage.</div>",
            unsafe_allow_html=True,
        )

        wasde_plot = wasde_c.copy()
        wasde_plot["period"] = (
            wasde_plot["marketing_year"]
            + " "
            + wasde_plot["estimate_type"]
            + " "
            + wasde_plot["vintage"]
        )
        wasde_plot["period_short"] = wasde_plot.apply(
            lambda row: short_wasde_label(
                row["marketing_year"], row["estimate_type"], row["vintage"]
            ),
            axis=1,
        )
        wasde_long = wasde_plot.melt(
            id_vars=["period", "period_short", "column_order"],
            value_vars=["production", "use_total", "ending_stocks"],
            var_name="metric",
            value_name="mbu",
        )
        bar_chart(
            wasde_long.dropna(subset=["mbu"]),
            "period_short",
            "mbu",
            "metric",
            height=360,
            x_title="Marketing Year",
            x_sort_field="column_order",
            x_label_angle=0,
            x_label_limit=80,
            extra_tooltips=[
                {"field": "period", "type": "nominal", "title": "Full Period"}
            ],
        )

        st.dataframe(
            wasde_c.sort_values("column_order"),
            width="stretch",
            hide_index=True,
        )

with tab_data:
    st.subheader("Data Explorer")
    table_name = st.selectbox(
        "Table",
        [
            "mart_wasde_balance.csv",
            "mart_supply_annual.csv",
            "mart_crop_progress_weekly.csv",
            "mart_crop_condition_weekly.csv",
            "mart_stocks_quarterly.csv",
            "mart_drought_weekly.csv",
            "mart_ethanol_weekly.csv",
            "mart_corn_fsi_monthly.csv",
            "mart_export_sales_weekly.csv",
            "mart_export_inspections_weekly.csv",
            "mart_soybean_crush_monthly.csv",
            "mart_feed_residual_quarterly.csv",
        ],
    )
    table = (
        read_optional_csv(table_name)
        if table_name in OPTIONAL_MART_SCHEMAS
        else read_csv(table_name)
    )
    st.dataframe(table, width="stretch", hide_index=True)
