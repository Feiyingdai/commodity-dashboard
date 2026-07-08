# Tableau Build Guide: U.S. Corn and Soybean Dashboard

This guide uses the CSV files in:

```text
/Users/Feiying/commodity/tableau/tableau_data/tables
```

## 1. Create The Data Source

In Tableau Desktop:

1. Open Tableau Desktop.
2. Connect to `Text File`.
3. Select:

```text
tableau/tableau_data/tables/mart_wasde_balance.csv
```

4. Add these additional CSV files to the same data source as separate logical
   tables:

```text
mart_supply_annual.csv
mart_crop_condition_weekly.csv
mart_crop_progress_weekly.csv
mart_stocks_quarterly.csv
mart_drought_weekly.csv
mart_ethanol_weekly.csv
dim_commodity.csv
dim_state.csv
```

Use logical relationships, not physical joins, to avoid row multiplication.

## 2. Recommended Relationships

Create relationships as follows:

| From | To | Relationship Fields |
| --- | --- | --- |
| `dim_commodity` | `mart_wasde_balance` | `commodity = commodity` |
| `dim_commodity` | `mart_supply_annual` | `commodity = commodity` |
| `dim_commodity` | `mart_crop_condition_weekly` | `commodity = commodity` |
| `dim_commodity` | `mart_crop_progress_weekly` | `commodity = commodity` |
| `dim_commodity` | `mart_stocks_quarterly` | `commodity = commodity` |
| `dim_state` | `mart_supply_annual` | `state_alpha = state_alpha` |
| `dim_state` | `mart_crop_condition_weekly` | `state_alpha = state_alpha` |
| `dim_state` | `mart_crop_progress_weekly` | `state_alpha = state_alpha` |
| `dim_state` | `mart_stocks_quarterly` | `state_alpha = state_alpha` |
| `dim_state` | `mart_drought_weekly` | `state_alpha = state_alpha` |

Leave `mart_ethanol_weekly` unrelated unless you build a date table. Ethanol is
corn-only and can be used in its own dashboard panel.

## 3. Global Filters

Create these dashboard filters:

- `commodity_label` from `dim_commodity`.
- `state_alpha` from `dim_state`.
- `year` from `mart_supply_annual`, `mart_crop_condition_weekly`, and
  `mart_crop_progress_weekly` as needed.
- `marketing_year` from `mart_wasde_balance`.
- `stage` from `mart_crop_progress_weekly`.

For the first dashboard version, use `CORN` and `SOYBEANS` as the commodity
filter values.

## 4. Calculated Fields

The file below lists formulas you can create manually in Tableau:

```text
tableau/tableau_data/tableau_calculated_fields.csv
```

Useful calculations:

### WASDE Latest Vintage

```text
[column_order] = { FIXED [commodity] : MAX([column_order]) }
```

### Latest Week

```text
[week_ending] = { FIXED [commodity], [state_alpha] : MAX([week_ending]) }
```

### Latest Drought Week

```text
[mapdate] = { FIXED [state_alpha] : MAX([mapdate]) }
```

## 5. Worksheets

### KPI: Production

Data table: `mart_wasde_balance`

- Filter: `WASDE Latest Vintage = True`
- Text: `SUM(production)`
- Detail: `commodity`, `marketing_year`
- Format: number, 0 decimals, suffix `mbu`

### KPI: Ending Stocks

Data table: `mart_wasde_balance`

- Filter: `WASDE Latest Vintage = True`
- Text: `SUM(ending_stocks)`
- Format: number, 0 decimals, suffix `mbu`

### KPI: Stocks-to-Use

Data table: `mart_wasde_balance`

- Filter: `WASDE Latest Vintage = True`
- Text: `AVG(stocks_to_use_pct)`
- Format: percentage-like number, 1 decimal

### WASDE Production And Stocks

Data table: `mart_wasde_balance`

- Columns: `marketing_year`, `vintage`
- Rows: `SUM(production)` and `SUM(ending_stocks)` using Measure Values
- Marks: bar
- Color: Measure Names

### Annual Supply Trend

Data table: `mart_supply_annual`

- Columns: `year`
- Rows: `SUM(production_mbu)`
- Color: `commodity`
- Filter: `state_alpha`

### Crop Condition Trend

Data table: `mart_crop_condition_weekly`

- Columns: `week_ending`
- Rows: `AVG(good_excellent)`
- Color: `year` or `commodity`
- Filter: `state_alpha`

### Crop Progress Trend

Data table: `mart_crop_progress_weekly`

- Columns: `week_ending`
- Rows: `AVG(pct)`
- Color: `year`
- Filter: `stage`, `state_alpha`, `commodity`

### Quarterly Stocks

Data table: `mart_stocks_quarterly`

- Columns: `stock_date`
- Rows: `SUM(stocks_mbu)`
- Color: `commodity`
- Filter: `state_alpha`

### Drought Severity

Data table: `mart_drought_weekly`

- Columns: `mapdate`
- Rows: `AVG(dsci)`
- Color: `state_alpha`

### Ethanol Demand

Data table: `mart_ethanol_weekly`

- Columns: `period`
- Rows: `SUM(implied_corn_use_mbu)`
- Add `ethanol_production_kbd` and `ethanol_stocks_kbbl` as optional secondary
  sheets.

## 6. Dashboard Layout

Recommended first version:

1. Top filter row:
   - Commodity
   - State
   - Crop year / marketing year
2. KPI row:
   - WASDE production
   - Ending stocks
   - Stocks-to-use
   - Good/excellent
3. Middle row:
   - WASDE production and stocks
   - Crop condition trend
4. Bottom row:
   - Annual supply trend
   - Drought severity
5. Demand tab:
   - Ethanol demand for corn
   - Crushings/exports for soybeans

Use separate dashboard tabs if a single page becomes crowded.

