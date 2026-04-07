#!/usr/bin/env python3
"""
Financial data fetcher for stock dashboard.
Reads config.json, pulls quarterly/annual financials via yfinance,
writes two merged CSVs (sankey.csv, trend.csv) with a ticker column.
"""

import json
import os
import yfinance as yf
import pandas as pd
from datetime import datetime

CONFIG_FILE = "config.json"
DATA_DIR    = "data"

SANKEY_FIELD_MAP = {
    "Total Revenue":           "total_revenue",
    "Cost Of Revenue":         "cost_of_revenue",
    "Gross Profit":            "gross_profit",
    "Operating Expense":       "operating_expense",
    "Operating Income":        "operating_income",
    "Interest Expense":        "interest_expense",
    "Pretax Income":           "pretax_income",
    "Tax Provision":           "tax_provision",
    "Net Income":              "net_income",
    "EBITDA":                  "ebitda",
    "Reconciled Depreciation": "depreciation",
    "Basic EPS":               "eps_basic",
    "Diluted EPS":             "eps_diluted",
}

TREND_METRICS_MAP = {
    "Total Revenue":    "total_revenue",
    "Gross Profit":     "gross_profit",
    "Operating Income": "operating_income",
    "Net Income":       "net_income",
    "Diluted EPS":      "eps_diluted",
    "EBITDA":           "ebitda",
}


def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)


def ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def safe_val(val):
    try:
        v = float(val)
        return None if pd.isna(v) else v
    except (TypeError, ValueError):
        return None


def fetch_income_statement(ticker_sym: str, period: str) -> pd.DataFrame:
    tk = yf.Ticker(ticker_sym)
    raw = tk.quarterly_income_stmt if period == "quarterly" else tk.income_stmt
    if raw is None or raw.empty:
        print(f"  [WARN] No {period} income statement for {ticker_sym}")
        return pd.DataFrame()
    df = raw.T.copy()
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"
    return df.sort_index()


def collect_sankey_rows(sym: str, df_q: pd.DataFrame, df_a: pd.DataFrame) -> list:
    rows = []
    for period_type, df in [("quarterly", df_q), ("annual", df_a)]:
        if df.empty:
            continue
        for dt, row in df.iterrows():
            record = {"ticker": sym.upper(), "period_type": period_type, "date": dt.strftime("%Y-%m-%d")}
            for src_col, dest_col in SANKEY_FIELD_MAP.items():
                matched = next((c for c in df.columns if src_col.lower() in c.lower()), None)
                record[dest_col] = safe_val(row[matched]) if matched else None
            rows.append(record)
    return rows


def collect_trend_rows(sym: str, df_q: pd.DataFrame, df_a: pd.DataFrame) -> list:
    rows = []
    for period_type, df in [("quarterly", df_q), ("annual", df_a)]:
        if df.empty:
            continue
        for src_col, metric_key in TREND_METRICS_MAP.items():
            matched = next((c for c in df.columns if src_col.lower() in c.lower()), None)
            if not matched:
                continue
            for dt, row in df.iterrows():
                v = safe_val(row[matched])
                if v is not None:
                    rows.append({
                        "ticker":      sym.upper(),
                        "period_type": period_type,
                        "date":        dt.strftime("%Y-%m-%d"),
                        "metric":      metric_key,
                        "value":       v,
                    })
    return rows


def main():
    cfg = load_config()
    ensure_dir()
    tickers = cfg.get("tickers", [])
    print(f"Fetching data for: {tickers}")

    all_sankey, all_trend = [], []

    for sym in tickers:
        print(f"\n--- {sym} ---")
        df_q = fetch_income_statement(sym, "quarterly")
        df_a = fetch_income_statement(sym, "annual")
        all_sankey.extend(collect_sankey_rows(sym, df_q, df_a))
        all_trend.extend(collect_trend_rows(sym, df_q, df_a))

    sankey_path = os.path.join(DATA_DIR, "sankey.csv")
    trend_path  = os.path.join(DATA_DIR, "trend.csv")

    pd.DataFrame(all_sankey).to_csv(sankey_path, index=False)
    pd.DataFrame(all_trend).to_csv(trend_path,  index=False)
    print(f"\nWritten: {sankey_path} ({len(all_sankey)} rows)")
    print(f"Written: {trend_path}  ({len(all_trend)} rows)")

    meta = {"tickers": tickers, "updated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}
    with open(os.path.join(DATA_DIR, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(f"Written: {DATA_DIR}/meta.json")


if __name__ == "__main__":
    main()
