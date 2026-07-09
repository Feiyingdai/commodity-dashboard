#!/usr/bin/env python3
"""Fetch starter datasets for a U.S. corn and soybean dashboard.

The script intentionally uses only Python standard library modules, pandas,
and python-dotenv, because the bundled runtime in this workspace does not
include requests.

Required for NASS:
    export NASS_API_KEY="..."

Optional for EIA:
    export EIA_API_KEY="..."

Optional for AMS/MARS export inspections:
    export AMS_API_KEY="..."

Example:
    python3 data_pipeline/fetch_us_grains_data.py --start-year 2015
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

import pandas as pd
from dotenv import load_dotenv


load_dotenv()


NASS_API_GET = "https://quickstats.nass.usda.gov/api/api_GET/"
NASS_API_COUNT = "https://quickstats.nass.usda.gov/api/get_counts/"
NASS_MAX_ROWS = 50_000
WASDE_PAGE = (
    "https://www.usda.gov/about-usda/general-information/staff-offices/"
    "office-chief-economist/commodity-markets/wasde-report"
)
WASDE_HISTORICAL_PAGE = "https://www.usda.gov/historical-wasde-report-data-3"
USDM_BASE = "https://usdmdataservices.unl.edu/api"
EIA_SERIES_URL = "https://api.eia.gov/v2/seriesid"
FAS_EXPORT_SALES_HISTORICAL_URLS = {
    "CORN": "https://apps.fas.usda.gov/export-sales/h401.htm",
    "SOYBEANS": "https://apps.fas.usda.gov/export-sales/h801.htm",
}
MT_TO_BUSHELS = {
    "CORN": 2204.62262185 / 56,
    "SOYBEANS": 2204.62262185 / 60,
}

COMMODITIES = ("CORN", "SOYBEANS")
SUPPLY_STATS = ("AREA PLANTED", "AREA HARVESTED", "YIELD", "PRODUCTION")
PROGRESS_STATS = ("PROGRESS", "CONDITION")
STOCK_STATS = ("STOCKS",)

ANNUAL_SUPPLY_SHORT_DESCS = {
    "CORN": (
        "CORN - ACRES PLANTED",
        "CORN, GRAIN - ACRES HARVESTED",
        "CORN, GRAIN - YIELD, MEASURED IN BU / ACRE",
        "CORN, GRAIN - PRODUCTION, MEASURED IN BU",
    ),
    "SOYBEANS": (
        "SOYBEANS - ACRES PLANTED",
        "SOYBEANS - ACRES HARVESTED",
        "SOYBEANS - YIELD, MEASURED IN BU / ACRE",
        "SOYBEANS - PRODUCTION, MEASURED IN BU",
    ),
}

STOCKS_SHORT_DESCS = {
    "CORN": (
        "CORN, GRAIN - STOCKS, MEASURED IN BU",
        "CORN, ON FARM, GRAIN - STOCKS, MEASURED IN BU",
        "CORN, OFF FARM, GRAIN - STOCKS, MEASURED IN BU",
    ),
    "SOYBEANS": (
        "SOYBEANS - STOCKS, MEASURED IN BU",
        "SOYBEANS, ON FARM - STOCKS, MEASURED IN BU",
        "SOYBEANS, OFF FARM - STOCKS, MEASURED IN BU",
    ),
}

CORN_FSI_SHORT_DESCS = (
    "CORN, FOR ALCOHOL & OTHER PRODUCTS - USAGE, MEASURED IN BU",
    "CORN, FOR ALCOHOL - USAGE, MEASURED IN BU",
    "CORN, FOR BEVERAGE ALCOHOL - USAGE, MEASURED IN BU",
    "CORN, FOR FUEL ALCOHOL - USAGE, MEASURED IN BU",
    "CORN, FOR INDUSTRIAL ALCOHOL - USAGE, MEASURED IN BU",
    "CORN, FOR OTHER PRODUCTS (EXCL ALCOHOL) - USAGE, MEASURED IN BU",
)

SOYBEAN_CRUSH_SHORT_DESCS = (
    "SOYBEANS - CRUSHED, MEASURED IN TONS",
    "CAKE & MEAL, SOYBEAN - PRODUCTION, MEASURED IN TONS",
    "OIL, SOYBEAN, CRUDE - PRODUCTION, MEASURED IN LB",
    "OIL, SOYBEAN, CRUDE - STOCKS, MEASURED IN LB",
)

# Large corn/soybean states. Keep this broad enough for weather and maps.
TOP_STATE_ALPHAS = (
    "IA",
    "IL",
    "IN",
    "MN",
    "NE",
    "SD",
    "ND",
    "OH",
    "MO",
    "KS",
    "WI",
    "MI",
    "AR",
)

STATE_FIPS = {
    "AR": "05",
    "IA": "19",
    "IL": "17",
    "IN": "18",
    "KS": "20",
    "MI": "26",
    "MN": "27",
    "MO": "29",
    "ND": "38",
    "NE": "31",
    "OH": "39",
    "SD": "46",
    "WI": "55",
}

# EIA legacy series IDs. These are convenient for MVP-level ethanol monitoring.
EIA_ETHANOL_SERIES = {
    "ethanol_production_kbd": "PET.W_EPOOXE_YOP_NUS_MBBLD.W",
    "ethanol_stocks_kbbl": "PET.W_EPOOXE_SAE_NUS_MBBL.W",
}

WASDE_VALUE_COLUMNS = (
    {
        "marketing_year": "2024/25",
        "estimate_type": "reported",
        "vintage": "current",
        "column_order": 1,
    },
    {
        "marketing_year": "2025/26",
        "estimate_type": "estimate",
        "vintage": "current",
        "column_order": 2,
    },
    {
        "marketing_year": "2026/27",
        "estimate_type": "projection",
        "vintage": "May",
        "column_order": 3,
    },
    {
        "marketing_year": "2026/27",
        "estimate_type": "projection",
        "vintage": "Jun",
        "column_order": 4,
    },
)

WASDE_UNIT_LABELS = {
    "Million Acres",
    "Metric Tons",
    "Million Metric Tons",
    "Bushels",
    "Million Bushels",
    "Million Pounds",
    "Thousand Short Tons",
}

WASDE_NUMBER_RE = re.compile(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?\*?")
FAS_EXPORT_ROW_RE = re.compile(r"^\s*(\d{2}/\d{2}/\d{4})\s+(.+)$")
FAS_EXPORT_NUMBER_RE = re.compile(r"\(\d[\d,]*\)|[-+]?\d[\d,]*")


@dataclass
class FetchResult:
    name: str
    path: Path | None
    rows: int | None = None
    skipped: bool = False
    note: str = ""


def fetch_bytes(url: str, timeout: int = 30, retries: int = 2) -> bytes:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; us-grains-dashboard-data-pipeline/0.1)"
        ),
        "Accept": "*/*",
    }
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout) as response:
                return response.read()
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace").strip()
            detail = f"HTTP Error {exc.code}: {exc.reason}"
            if body:
                detail = f"{detail} - {body[:500]}"
            last_error = RuntimeError(detail)
            if attempt < retries:
                time.sleep(1.5 * attempt)
        except (URLError, TimeoutError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * attempt)
    safe_url = re.sub(r"([?&]key=)[^&]+", r"\1<redacted>", url)
    raise RuntimeError(f"Failed to fetch {safe_url}: {last_error}") from last_error


def fetch_text(url: str) -> str:
    return fetch_bytes(url).decode("utf-8", errors="replace")


def ensure_dirs(root: Path) -> dict[str, Path]:
    dirs = {
        "raw": root / "raw",
        "clean": root / "clean",
        "nass": root / "raw" / "nass",
        "wasde": root / "raw" / "wasde",
        "usdm": root / "raw" / "usdm",
        "eia": root / "raw" / "eia",
        "fas": root / "raw" / "fas",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def clean_numeric_value(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text in {"(D)", "(NA)", "(Z)"}:
        return None
    text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def clean_wasde_value(value: str) -> float | None:
    text = value.strip().replace(",", "").replace("*", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def clean_fas_number(value: str) -> float | None:
    text = value.strip().replace(",", "")
    if not text:
        return None
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    try:
        return float(text)
    except ValueError:
        return None


def normalize_metric_name(metric: str) -> str:
    metric = re.sub(r"\s+\d+/$", "", metric.strip())
    metric = metric.replace("&", "and")
    metric = re.sub(r"[^A-Za-z0-9]+", "_", metric).strip("_").lower()
    return metric


def marketing_year_from_date(value: object) -> str | None:
    period = pd.to_datetime(value, errors="coerce")
    if pd.isna(period):
        return None
    start_year = period.year if period.month >= 9 else period.year - 1
    return f"{start_year}/{str(start_year + 1)[-2:]}"


def infer_wasde_unit(metric: str, current_unit: str | None) -> str | None:
    if "$/bu" in metric:
        return "$/bu"
    if "$/s.t." in metric:
        return "$/short ton"
    if "c/lb" in metric:
        return "cents/lb"
    return current_unit


def read_csv_bytes(payload: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(payload), dtype=str)


def build_quickstats_query(api_key: str, params: dict[str, str]) -> dict[str, str]:
    query = {
        "key": api_key,
        "source_desc": "SURVEY",
        "sector_desc": "CROPS",
        "group_desc": "FIELD CROPS",
    }
    query.update(params)
    return query


def quickstats_count(api_key: str, params: dict[str, str]) -> int:
    query = build_quickstats_query(api_key, params)
    url = f"{NASS_API_COUNT}?{urlencode(query)}"
    payload = fetch_bytes(url)
    data = json.loads(payload.decode("utf-8"))
    return int(data.get("count", 0))


def quickstats_csv_raw(api_key: str, params: dict[str, str]) -> pd.DataFrame:
    query = build_quickstats_query(api_key, params)
    query["format"] = "CSV"
    url = f"{NASS_API_GET}?{urlencode(query)}"
    payload = fetch_bytes(url)
    if payload.strip().startswith(b"{"):
        # QuickStats returns JSON error messages even if format=CSV.
        message = payload.decode("utf-8", errors="replace")
        raise RuntimeError(f"NASS returned an error for {params}: {message}")
    return read_csv_bytes(payload)


def quickstats_csv(api_key: str, params: dict[str, str]) -> pd.DataFrame:
    count = quickstats_count(api_key, params)
    if count == 0:
        return pd.DataFrame()
    if count <= NASS_MAX_ROWS:
        return quickstats_csv_raw(api_key, params)

    if "year__GE" not in params:
        raise RuntimeError(
            f"NASS query would return {count:,} rows and cannot be split safely: {params}"
        )

    print(f"NASS query has {count:,} rows; splitting by year: {params}")
    frames: list[pd.DataFrame] = []
    start_year = int(params["year__GE"])
    for year in range(start_year, date.today().year + 1):
        split_params = params.copy()
        split_params.pop("year__GE", None)
        split_params["year"] = str(year)
        frames.append(quickstats_csv(api_key, split_params))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def clean_quickstats(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out.columns = [c.strip() for c in out.columns]
    if "Value" in out.columns:
        out["value_num"] = out["Value"].map(clean_numeric_value)
    if "year" in out.columns:
        out["year"] = pd.to_numeric(out["year"], errors="coerce").astype("Int64")
    if "week_ending" in out.columns:
        out["week_ending"] = pd.to_datetime(out["week_ending"], errors="coerce")
    if "load_time" in out.columns:
        out["load_time"] = pd.to_datetime(out["load_time"], errors="coerce")
    return out


def fetch_nass_annual_supply(
    api_key: str, start_year: int, dirs: dict[str, Path]
) -> FetchResult:
    frames: list[pd.DataFrame] = []
    for commodity in COMMODITIES:
        for short_desc in ANNUAL_SUPPLY_SHORT_DESCS[commodity]:
            for level in ("NATIONAL", "STATE"):
                params = {
                    "commodity_desc": commodity,
                    "short_desc": short_desc,
                    "agg_level_desc": level,
                    "year__GE": str(start_year),
                    "freq_desc": "ANNUAL",
                }
                frames.append(quickstats_csv(api_key, params))

    raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    raw_path = dirs["nass"] / "annual_supply_raw.csv"
    raw.to_csv(raw_path, index=False)

    clean = clean_quickstats(raw)
    keep_cols = [
        "commodity_desc",
        "statisticcat_desc",
        "unit_desc",
        "short_desc",
        "agg_level_desc",
        "state_alpha",
        "state_name",
        "year",
        "reference_period_desc",
        "Value",
        "value_num",
        "load_time",
    ]
    clean = clean[[c for c in keep_cols if c in clean.columns]]
    clean_path = dirs["clean"] / "nass_annual_supply.csv"
    clean.to_csv(clean_path, index=False)
    return FetchResult("NASS annual supply", clean_path, len(clean))


def fetch_nass_crop_progress_condition(
    api_key: str, start_year: int, dirs: dict[str, Path]
) -> FetchResult:
    frames: list[pd.DataFrame] = []
    for commodity in COMMODITIES:
        for stat in PROGRESS_STATS:
            for level in ("NATIONAL", "STATE"):
                params = {
                    "commodity_desc": commodity,
                    "statisticcat_desc": stat,
                    "agg_level_desc": level,
                    "year__GE": str(start_year),
                    "freq_desc": "WEEKLY",
                }
                frames.append(quickstats_csv(api_key, params))

    raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    raw_path = dirs["nass"] / "crop_progress_condition_raw.csv"
    raw.to_csv(raw_path, index=False)

    clean = clean_quickstats(raw)
    keep_cols = [
        "commodity_desc",
        "statisticcat_desc",
        "unit_desc",
        "short_desc",
        "agg_level_desc",
        "state_alpha",
        "state_name",
        "year",
        "week_ending",
        "reference_period_desc",
        "Value",
        "value_num",
        "load_time",
    ]
    clean = clean[[c for c in keep_cols if c in clean.columns]]
    clean_path = dirs["clean"] / "nass_crop_progress_condition.csv"
    clean.to_csv(clean_path, index=False)
    return FetchResult("NASS crop progress/condition", clean_path, len(clean))


def fetch_nass_stocks(
    api_key: str, start_year: int, dirs: dict[str, Path]
) -> FetchResult:
    frames: list[pd.DataFrame] = []
    for commodity in COMMODITIES:
        for short_desc in STOCKS_SHORT_DESCS[commodity]:
            for level in ("NATIONAL", "STATE"):
                params = {
                    "commodity_desc": commodity,
                    "short_desc": short_desc,
                    "agg_level_desc": level,
                    "year__GE": str(start_year),
                }
                frames.append(quickstats_csv(api_key, params))

    raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    raw_path = dirs["nass"] / "stocks_raw.csv"
    raw.to_csv(raw_path, index=False)

    clean = clean_quickstats(raw)
    keep_cols = [
        "commodity_desc",
        "statisticcat_desc",
        "unit_desc",
        "short_desc",
        "agg_level_desc",
        "state_alpha",
        "state_name",
        "year",
        "freq_desc",
        "reference_period_desc",
        "Value",
        "value_num",
        "load_time",
    ]
    clean = clean[[c for c in keep_cols if c in clean.columns]]
    clean_path = dirs["clean"] / "nass_stocks.csv"
    clean.to_csv(clean_path, index=False)
    return FetchResult("NASS stocks", clean_path, len(clean))


def fetch_nass_corn_fsi(
    api_key: str, start_year: int, dirs: dict[str, Path]
) -> FetchResult:
    frames: list[pd.DataFrame] = []
    for short_desc in CORN_FSI_SHORT_DESCS:
        params = {
            "commodity_desc": "CORN",
            "short_desc": short_desc,
            "agg_level_desc": "NATIONAL",
            "year__GE": str(start_year),
            "freq_desc": "MONTHLY",
        }
        frames.append(quickstats_csv(api_key, params))

    raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    raw_path = dirs["nass"] / "corn_fsi_raw.csv"
    raw.to_csv(raw_path, index=False)

    clean = clean_quickstats(raw)
    keep_cols = [
        "commodity_desc",
        "statisticcat_desc",
        "unit_desc",
        "short_desc",
        "prodn_practice_desc",
        "util_practice_desc",
        "agg_level_desc",
        "state_alpha",
        "state_name",
        "year",
        "freq_desc",
        "begin_code",
        "end_code",
        "reference_period_desc",
        "Value",
        "value_num",
        "load_time",
    ]
    clean = clean[[c for c in keep_cols if c in clean.columns]]
    clean_path = dirs["clean"] / "nass_corn_fsi_monthly.csv"
    clean.to_csv(clean_path, index=False)
    return FetchResult("NASS corn FSI monthly", clean_path, len(clean))


def fetch_nass_soybean_crush(
    api_key: str, start_year: int, dirs: dict[str, Path]
) -> FetchResult:
    frames: list[pd.DataFrame] = []
    for short_desc in SOYBEAN_CRUSH_SHORT_DESCS:
        params = {
            "short_desc": short_desc,
            "agg_level_desc": "NATIONAL",
            "year__GE": str(start_year),
            "freq_desc": "MONTHLY",
        }
        frames.append(quickstats_csv(api_key, params))

    raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    raw_path = dirs["nass"] / "soybean_crush_raw.csv"
    raw.to_csv(raw_path, index=False)

    clean = clean_quickstats(raw)
    keep_cols = [
        "commodity_desc",
        "statisticcat_desc",
        "unit_desc",
        "short_desc",
        "prodn_practice_desc",
        "util_practice_desc",
        "agg_level_desc",
        "state_alpha",
        "state_name",
        "year",
        "freq_desc",
        "begin_code",
        "end_code",
        "reference_period_desc",
        "Value",
        "value_num",
        "load_time",
    ]
    clean = clean[[c for c in keep_cols if c in clean.columns]]
    clean_path = dirs["clean"] / "nass_soybean_crush_monthly.csv"
    clean.to_csv(clean_path, index=False)
    return FetchResult("NASS soybean crush monthly", clean_path, len(clean))


def find_file_links(html: str, base_url: str, suffixes: Iterable[str]) -> list[str]:
    suffix_pattern = "|".join(re.escape(s) for s in suffixes)
    hrefs = re.findall(
        rf'href=["\']([^"\']+\.({suffix_pattern})(?:\?[^"\']*)?)["\']',
        html,
        flags=re.IGNORECASE,
    )
    links = []
    for href, _suffix in hrefs:
        links.append(urljoin(base_url, href))
    return list(dict.fromkeys(links))


def safe_filename_from_url(url: str) -> str:
    filename = url.rsplit("/", 1)[-1].split("?", 1)[0]
    filename = re.sub(r"[^A-Za-z0-9._-]+", "_", filename)
    return filename or "downloaded_file"


def download_links(links: Iterable[str], out_dir: Path) -> int:
    count = 0
    for link in links:
        out_path = out_dir / safe_filename_from_url(link)
        print(f"Downloading {link}")
        payload = fetch_bytes(link)
        out_path.write_bytes(payload)
        count += 1
    return count


def parse_report_month(text: str) -> str | None:
    match = re.search(r"WASDE\s*-\s*\d+\s*-\s*\d+\s+([A-Za-z]+ \d{4})", text)
    return match.group(1) if match else None


def parse_wasde_value_columns(block_lines: list[str]) -> list[dict[str, str]]:
    for idx, line in enumerate(block_lines[:12]):
        year_matches = list(re.finditer(r"\d{4}/\d{2}", line))
        if len(year_matches) < 2:
            continue

        columns: list[dict[str, str]] = []
        for pos, match in enumerate(year_matches):
            end = year_matches[pos + 1].start() if pos + 1 < len(year_matches) else len(line)
            label_tail = line[match.end() : end]
            if "Proj" in label_tail:
                estimate_type = "projection"
            elif "Est" in label_tail:
                estimate_type = "estimate"
            else:
                estimate_type = "reported"
            columns.append(
                {
                    "marketing_year": match.group(0),
                    "estimate_type": estimate_type,
                    "vintage": "current",
                    "column_order": pos + 1,
                }
            )

        month_line = block_lines[idx + 1] if idx + 1 < len(block_lines) else ""
        month_labels = re.findall(
            r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b",
            month_line,
        )
        if month_labels and len(month_labels) <= len(columns):
            for column, month in zip(columns[-len(month_labels) :], month_labels):
                column["vintage"] = month
        return columns

    return [dict(column) for column in WASDE_VALUE_COLUMNS]


def extract_wasde_commodity_block(
    lines: list[str], title: str, commodity_header: str, stop_headers: set[str]
) -> list[str]:
    title_idx = next((i for i, line in enumerate(lines) if title in line), None)
    if title_idx is None:
        raise RuntimeError(f"Could not find WASDE section: {title}")

    commodity_idx = next(
        (
            i
            for i in range(title_idx, len(lines))
            if lines[i].strip().upper() == commodity_header.upper()
        ),
        None,
    )
    if commodity_idx is None:
        raise RuntimeError(f"Could not find commodity header: {commodity_header}")

    header_start = max(title_idx, commodity_idx - 8)
    end_idx = len(lines)
    for i in range(commodity_idx + 1, len(lines)):
        stripped = lines[i].strip().upper()
        if stripped in stop_headers:
            end_idx = i
            break
        if stripped.startswith("====") and i > commodity_idx + 4:
            end_idx = i
            break
    return lines[header_start:end_idx]


def parse_wasde_block(
    block_lines: list[str], commodity: str, report_month: str | None, source_file: Path
) -> pd.DataFrame:
    columns = parse_wasde_value_columns(block_lines)
    current_unit: str | None = None
    in_commodity = False
    rows: list[dict[str, object]] = []

    for line in block_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("="):
            continue
        if stripped in WASDE_UNIT_LABELS:
            current_unit = stripped
            continue
        if stripped.upper() == commodity.upper():
            in_commodity = True
            continue
        if not in_commodity:
            continue

        matches = list(WASDE_NUMBER_RE.finditer(line))
        if len(matches) < len(columns):
            continue

        value_matches = matches[-len(columns) :]
        metric = line[: value_matches[0].start()].strip()
        metric = re.sub(r"\s+\d+/$", "", metric)
        if not metric:
            continue

        for column, value_match in zip(columns, value_matches):
            rows.append(
                {
                    "source_file": str(source_file),
                    "report_month": report_month,
                    "commodity": commodity.upper(),
                    "marketing_year": column["marketing_year"],
                    "estimate_type": column["estimate_type"],
                    "vintage": column["vintage"],
                    "column_order": column["column_order"],
                    "metric": metric,
                    "metric_key": normalize_metric_name(metric),
                    "unit": infer_wasde_unit(metric, current_unit),
                    "value": clean_wasde_value(value_match.group(0)),
                }
            )

    return pd.DataFrame(rows)


def parse_wasde_us_balance(txt_path: Path, clean_dir: Path) -> tuple[Path, Path, int]:
    text = txt_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    report_month = parse_report_month(text)

    corn_block = extract_wasde_commodity_block(
        lines,
        "U.S. Feed Grain and Corn Supply and Use",
        "CORN",
        stop_headers={"SORGHUM"},
    )
    soybean_block = extract_wasde_commodity_block(
        lines,
        "U.S. Soybeans and Products Supply and Use",
        "SOYBEANS",
        stop_headers={"SOYBEAN OIL"},
    )

    long_df = pd.concat(
        [
            parse_wasde_block(corn_block, "CORN", report_month, txt_path),
            parse_wasde_block(soybean_block, "SOYBEANS", report_month, txt_path),
        ],
        ignore_index=True,
    )

    long_path = clean_dir / "wasde_us_balance_long.csv"

    id_cols = [
        "source_file",
        "report_month",
        "commodity",
        "marketing_year",
        "estimate_type",
        "vintage",
        "column_order",
    ]
    wide_df = (
        long_df.pivot_table(
            index=id_cols,
            columns="metric_key",
            values="value",
            aggfunc="first",
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )
    if {"ending_stocks", "use_total"}.issubset(wide_df.columns):
        wide_df["stocks_to_use"] = wide_df["ending_stocks"] / wide_df["use_total"]

    long_df = long_df.sort_values(
        ["commodity", "column_order", "metric_key"], ignore_index=True
    )
    long_df.to_csv(long_path, index=False)

    wide_df = wide_df.sort_values(["commodity", "column_order"], ignore_index=True)
    wide_path = clean_dir / "wasde_us_balance_wide.csv"
    wide_df.to_csv(wide_path, index=False)
    return long_path, wide_path, len(wide_df)


def parse_latest_wasde_txt(dirs: dict[str, Path]) -> FetchResult:
    txt_files = sorted((dirs["wasde"] / "latest").glob("*.txt"))
    if not txt_files:
        return FetchResult(
            "WASDE parser",
            None,
            skipped=True,
            note="No WASDE .txt file found under data/raw/wasde/latest.",
        )
    latest_txt = max(txt_files, key=lambda path: path.stat().st_mtime)
    long_path, wide_path, rows = parse_wasde_us_balance(latest_txt, dirs["clean"])
    note = f"long={long_path.name}; wide={wide_path.name}"
    return FetchResult("WASDE parser", wide_path, rows, note=note)


def fetch_wasde_files(dirs: dict[str, Path], historical_years: int = 0) -> FetchResult:
    wasde_dir = dirs["wasde"]
    latest_dir = wasde_dir / "latest"
    historical_dir = wasde_dir / "historical"
    latest_dir.mkdir(parents=True, exist_ok=True)
    historical_dir.mkdir(parents=True, exist_ok=True)

    latest_html = fetch_text(WASDE_PAGE)
    latest_links = find_file_links(latest_html, WASDE_PAGE, ("pdf", "xml", "xls", "xlsx", "txt"))
    # Usually the latest report appears before the previous month on the page.
    latest_downloads = download_links(latest_links[:4], latest_dir)

    historical_downloads = 0
    if historical_years > 0:
        historical_html = fetch_text(WASDE_HISTORICAL_PAGE)
        csv_links = find_file_links(historical_html, WASDE_HISTORICAL_PAGE, ("csv",))

        current_year = date.today().year
        min_year = current_year - historical_years + 1
        selected_csv_links = [
            link
            for link in csv_links
            if any(str(year) in link for year in range(min_year, current_year + 1))
        ]
        historical_downloads = download_links(selected_csv_links, historical_dir)

    note = f"{latest_downloads} latest files; {historical_downloads} historical CSV files"
    parse_result = parse_latest_wasde_txt(dirs)
    if not parse_result.skipped:
        note = f"{note}; parsed {parse_result.rows} balance rows"
    return FetchResult("WASDE files", wasde_dir, None, note=note)



def fetch_usdm_state_drought(
    start_year: int, dirs: dict[str, Path], state_alphas: Iterable[str] = TOP_STATE_ALPHAS
) -> FetchResult:
    start = f"1/1/{start_year}"
    end = date.today().strftime("%-m/%-d/%Y") if sys.platform != "win32" else date.today().strftime("%#m/%#d/%Y")
    frames: list[pd.DataFrame] = []

    for alpha in state_alphas:
        fips = STATE_FIPS[alpha]
        params = urlencode(
            {
                "aoi": fips,
                "startdate": start,
                "enddate": end,
                "statisticsType": "1",
            }
        )
        url = (
            f"{USDM_BASE}/StateStatistics/"
            f"GetDroughtSeverityStatisticsByAreaPercent?{params}"
        )
        print(f"Fetching USDM drought data for {alpha}")
        payload = fetch_bytes(url)
        raw_path = dirs["usdm"] / f"drought_{alpha}.csv"
        raw_path.write_bytes(payload)
        frame = read_csv_bytes(payload)
        frame["state_alpha"] = alpha
        frames.append(frame)

    raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    clean = raw.copy()
    clean.columns = [c.strip().lower().replace(" ", "_") for c in clean.columns]
    for col in clean.columns:
        if col not in {"mapdate", "state_alpha"}:
            numeric = pd.to_numeric(clean[col], errors="coerce")
            if numeric.notna().any():
                clean[col] = numeric
    if "mapdate" in clean.columns:
        clean["mapdate"] = pd.to_datetime(clean["mapdate"], errors="coerce")

    clean_path = dirs["clean"] / "usdm_drought_state.csv"
    clean.to_csv(clean_path, index=False)
    return FetchResult("USDM drought by state", clean_path, len(clean))


def fetch_eia_ethanol(api_key: str | None, dirs: dict[str, Path]) -> FetchResult:
    if not api_key:
        return FetchResult(
            "EIA ethanol",
            None,
            skipped=True,
            note="Set EIA_API_KEY to fetch ethanol series.",
        )

    frames: list[pd.DataFrame] = []
    for name, series_id in EIA_ETHANOL_SERIES.items():
        params = urlencode({"api_key": api_key})
        payload = fetch_bytes(f"{EIA_SERIES_URL}/{series_id}?{params}")
        raw_path = dirs["eia"] / f"{name}.json"
        raw_path.write_bytes(payload)
        data = json.loads(payload.decode("utf-8"))

        if "response" in data:
            response = data["response"]
            rows = response.get("data", [])
            frame = pd.DataFrame(rows)
            series_name = response.get("series-description", name)
            if "series-description" in frame.columns:
                series_name = frame["series-description"].dropna().iloc[0]
            keep_cols = [col for col in ("period", "value", "units") if col in frame.columns]
            frame = frame[keep_cols]
        else:
            # Backward-compatible parser for the old API response shape.
            series = data.get("series", [{}])[0]
            rows = series.get("data", [])
            frame = pd.DataFrame(rows, columns=["period", "value"])
            series_name = series.get("name", name)

        frame["metric"] = name
        frame["series_id"] = series_id
        frame["name"] = series_name
        frames.append(frame)

    clean = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not clean.empty:
        clean["value"] = pd.to_numeric(clean["value"], errors="coerce")
    clean_path = dirs["clean"] / "eia_ethanol.csv"
    clean.to_csv(clean_path, index=False)
    return FetchResult("EIA ethanol", clean_path, len(clean))


def parse_fas_export_sales_html(
    html: str,
    commodity: str,
    source_url: str,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    mt_to_bushels = MT_TO_BUSHELS[commodity]
    for line in html.splitlines():
        match = FAS_EXPORT_ROW_RE.match(line)
        if not match:
            continue
        week_ending = pd.to_datetime(match.group(1), errors="coerce")
        if pd.isna(week_ending):
            continue
        values = [
            clean_fas_number(token)
            for token in FAS_EXPORT_NUMBER_RE.findall(match.group(2))
        ]
        if len(values) < 6:
            continue
        (
            current_week_exports_mt,
            accumulated_exports_mt,
            net_sales_mt,
            outstanding_sales_mt,
            next_marketing_year_net_sales_mt,
            next_marketing_year_outstanding_sales_mt,
        ) = values[:6]

        row = {
            "commodity": commodity,
            "marketing_year": marketing_year_from_date(week_ending),
            "week_ending": week_ending,
            "country": "TOTAL",
            "current_week_exports_mt": current_week_exports_mt,
            "accumulated_exports_mt": accumulated_exports_mt,
            "net_sales_mt": net_sales_mt,
            "outstanding_sales_mt": outstanding_sales_mt,
            "next_marketing_year_net_sales_mt": next_marketing_year_net_sales_mt,
            "next_marketing_year_outstanding_sales_mt": next_marketing_year_outstanding_sales_mt,
            "source_url": source_url,
        }
        for col in (
            "current_week_exports",
            "accumulated_exports",
            "net_sales",
            "outstanding_sales",
            "next_marketing_year_net_sales",
            "next_marketing_year_outstanding_sales",
        ):
            row[f"{col}_mbu"] = row[f"{col}_mt"] * mt_to_bushels / 1_000_000
        row["total_commitments_mbu"] = (
            row["accumulated_exports_mbu"] + row["outstanding_sales_mbu"]
        )
        rows.append(row)

    return pd.DataFrame(rows)


def fetch_fas_export_sales(dirs: dict[str, Path]) -> FetchResult:
    frames: list[pd.DataFrame] = []
    notes: list[str] = []
    for commodity, url in FAS_EXPORT_SALES_HISTORICAL_URLS.items():
        print(f"Fetching FAS export sales historical data for {commodity}")
        try:
            html = fetch_text(url)
        except RuntimeError as exc:
            notes.append(f"{commodity}: {exc}")
            continue
        raw_path = dirs["fas"] / f"export_sales_{commodity.lower()}.htm"
        raw_path.write_text(html, encoding="utf-8")
        frames.append(parse_fas_export_sales_html(html, commodity, url))

    clean = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    clean_path = dirs["clean"] / "export_sales_weekly.csv"
    clean.to_csv(clean_path, index=False)
    note = "; ".join(notes)
    return FetchResult("FAS export sales", clean_path, len(clean), note=note)


def print_result(result: FetchResult) -> None:
    if result.skipped:
        print(f"SKIP  {result.name}: {result.note}")
        return
    row_text = "" if result.rows is None else f" ({result.rows:,} rows)"
    note_text = "" if not result.note else f" - {result.note}"
    print(f"OK    {result.name}: {result.path}{row_text}{note_text}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument("--skip-nass", action="store_true")
    parser.add_argument(
        "--skip-nass-processing",
        action="store_true",
        help="Skip NASS monthly corn FSI and soybean crush processing datasets.",
    )
    parser.add_argument("--skip-wasde", action="store_true")
    parser.add_argument(
        "--parse-existing-wasde",
        action="store_true",
        help="Parse the latest local WASDE .txt file without downloading new WASDE files.",
    )
    parser.add_argument("--skip-usdm", action="store_true")
    parser.add_argument("--skip-eia", action="store_true")
    parser.add_argument(
        "--fetch-fas-export-sales",
        action="store_true",
        help=(
            "Fetch USDA FAS weekly historical export-sales pages for corn and "
            "soybeans into data/clean/export_sales_weekly.csv."
        ),
    )
    parser.add_argument(
        "--wasde-historical-years",
        type=int,
        default=0,
        help=(
            "How many recent calendar years of WASDE historical CSV files to download. "
            "Default is 0 because the current WASDE files are enough for first setup."
        ),
    )
    args = parser.parse_args()

    dirs = ensure_dirs(args.out_dir)
    results: list[FetchResult] = []

    nass_key = os.getenv("NASS_API_KEY")
    eia_key = os.getenv("EIA_API_KEY")
    if args.skip_nass:
        results.append(FetchResult("NASS", None, skipped=True, note="--skip-nass"))
    elif not nass_key:
        results.append(
            FetchResult(
                "NASS",
                None,
                skipped=True,
                note="Set NASS_API_KEY to fetch QuickStats datasets.",
            )
        )
    else:
        results.append(fetch_nass_annual_supply(nass_key, args.start_year, dirs))
        results.append(fetch_nass_crop_progress_condition(nass_key, args.start_year, dirs))
        results.append(fetch_nass_stocks(nass_key, args.start_year, dirs))
        if args.skip_nass_processing:
            results.append(
                FetchResult(
                    "NASS processing",
                    None,
                    skipped=True,
                    note="--skip-nass-processing",
                )
            )
        else:
            results.append(fetch_nass_corn_fsi(nass_key, args.start_year, dirs))
            results.append(fetch_nass_soybean_crush(nass_key, args.start_year, dirs))

    if args.parse_existing_wasde:
        results.append(parse_latest_wasde_txt(dirs))
    elif args.skip_wasde:
        results.append(FetchResult("WASDE", None, skipped=True, note="--skip-wasde"))
    else:
        results.append(fetch_wasde_files(dirs, args.wasde_historical_years))

    if args.skip_usdm:
        results.append(FetchResult("USDM drought", None, skipped=True, note="--skip-usdm"))
    else:
        results.append(fetch_usdm_state_drought(args.start_year, dirs))

    if args.skip_eia:
        results.append(FetchResult("EIA ethanol", None, skipped=True, note="--skip-eia"))
    else:
        results.append(fetch_eia_ethanol(eia_key, dirs))

    if args.fetch_fas_export_sales:
        results.append(fetch_fas_export_sales(dirs))
    else:
        results.append(
            FetchResult(
                "FAS export sales",
                None,
                skipped=True,
                note="Add --fetch-fas-export-sales to fetch weekly historical data.",
            )
        )

    print("\nFetch summary")
    print("-------------")
    for result in results:
        print_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
