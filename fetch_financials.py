#!/usr/bin/env python3
"""
Financial data fetcher for stock dashboard.
Reads config.json, pulls quarterly/annual financials via yfinance,
writes sankey.csv, trend.csv, estimates.csv into data/.
"""

import json, os
import yfinance as yf
import pandas as pd
from datetime import datetime

CONFIG_FILE = "config.json"
DATA_DIR    = "data"

# Sankey fields — includes R&D and SG&A breakout
SANKEY_FIELD_MAP = {
    "Total Revenue":                    "total_revenue",
    "Cost Of Revenue":                  "cost_of_revenue",
    "Gross Profit":                     "gross_profit",
    "Research And Development":         "rd_expense",
    "Selling General And Administration":"sga_expense",
    "Operating Expense":                "operating_expense",   # total opex (fallback)
    "Operating Income":                 "operating_income",
    "Interest Expense":                 "interest_expense",
    "Pretax Income":                    "pretax_income",
    "Tax Provision":                    "tax_provision",
    "Net Income":                       "net_income",
    "EBITDA":                           "ebitda",
    "Basic EPS":                        "eps_basic",
    "Diluted EPS":                      "eps_diluted",
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

def fuzzy_col(df, key):
    return next((c for c in df.columns if key.lower() in c.lower()), None)

def fetch_income_statement(sym: str, period: str) -> pd.DataFrame:
    tk = yf.Ticker(sym)
    raw = tk.quarterly_income_stmt if period == "quarterly" else tk.income_stmt
    if raw is None or raw.empty:
        print(f"  [WARN] No {period} income statement for {sym}")
        return pd.DataFrame()
    df = raw.T.copy()
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"
    return df.sort_index()

def fetch_estimates(sym: str) -> list:
    """
    Pull current analyst estimates from yfinance.
    Returns rows: {ticker, period_type, date, metric, estimate}
    yfinance provides earnings_estimate (EPS) and revenue_estimate.
    These are *current* estimates, not historical — labelled accordingly.
    """
    tk = yf.Ticker(sym)
    rows = []
    try:
        ee = tk.earnings_estimate   # index: 0q,+1q,0y,+1y
        re = tk.revenue_estimate
        for period_label, idx in [("quarterly", ["0q", "+1q"]), ("annual", ["0y", "+1y"])]:
            for i in idx:
                if ee is not None and i in ee.index:
                    avg = safe_val(ee.loc[i, "avg"]) if "avg" in ee.columns else None
                    if avg is not None:
                        rows.append({"ticker": sym.upper(), "period_type": period_label,
                                     "estimate_period": i, "metric": "eps_diluted", "estimate": avg})
                if re is not None and i in re.index:
                    avg = safe_val(re.loc[i, "avg"]) if "avg" in re.columns else None
                    if avg is not None:
                        rows.append({"ticker": sym.upper(), "period_type": period_label,
                                     "estimate_period": i, "metric": "total_revenue", "estimate": avg})
    except Exception as e:
        print(f"  [WARN] estimates fetch failed for {sym}: {e}")
    return rows

def collect_sankey_rows(sym: str, df_q: pd.DataFrame, df_a: pd.DataFrame) -> list:
    rows = []
    for period_type, df in [("quarterly", df_q), ("annual", df_a)]:
        if df.empty:
            continue
        for dt, row in df.iterrows():
            record = {"ticker": sym.upper(), "period_type": period_type,
                      "date": dt.strftime("%Y-%m-%d")}
            for src_col, dest_col in SANKEY_FIELD_MAP.items():
                matched = fuzzy_col(df, src_col)
                record[dest_col] = safe_val(row[matched]) if matched else None
            rows.append(record)
    return rows

def collect_trend_rows(sym: str, df_q: pd.DataFrame, df_a: pd.DataFrame) -> list:
    rows = []
    for period_type, df in [("quarterly", df_q), ("annual", df_a)]:
        if df.empty:
            continue
        for src_col, metric_key in TREND_METRICS_MAP.items():
            matched = fuzzy_col(df, src_col)
            if not matched:
                continue
            for dt, row in df.iterrows():
                v = safe_val(row[matched])
                if v is not None:
                    rows.append({"ticker": sym.upper(), "period_type": period_type,
                                 "date": dt.strftime("%Y-%m-%d"),
                                 "metric": metric_key, "value": v})
    return rows

def main():
    cfg = load_config()
    ensure_dir()
    tickers = cfg.get("tickers", [])
    print(f"Fetching data for: {tickers}")

    all_sankey, all_trend, all_estimates = [], [], []

    for sym in tickers:
        print(f"\n--- {sym} ---")
        df_q = fetch_income_statement(sym, "quarterly")
        df_a = fetch_income_statement(sym, "annual")
        all_sankey.extend(collect_sankey_rows(sym, df_q, df_a))
        all_trend.extend(collect_trend_rows(sym, df_q, df_a))
        all_estimates.extend(fetch_estimates(sym))

    pd.DataFrame(all_sankey).to_csv(os.path.join(DATA_DIR, "sankey.csv"),    index=False)
    pd.DataFrame(all_trend).to_csv(os.path.join(DATA_DIR,  "trend.csv"),     index=False)
    pd.DataFrame(all_estimates).to_csv(os.path.join(DATA_DIR, "estimates.csv"), index=False)

    for name, lst in [("sankey", all_sankey), ("trend", all_trend), ("estimates", all_estimates)]:
        print(f"Written: data/{name}.csv  ({len(lst)} rows)")

    meta = {"tickers": tickers, "updated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}
    with open(os.path.join(DATA_DIR, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(f"Written: data/meta.json")

if __name__ == "__main__":
    main()
