#!/usr/bin/env python3
"""
Financial data fetcher for stock dashboard.
Reads config.json, pulls income statement / balance sheet / cash flow via yfinance,
writes sankey.csv, trend.csv, estimates.csv, balance.csv, cashflow.csv into data/.
Full history since IPO is included (yfinance returns all available periods).
"""

import json, os
import yfinance as yf
import pandas as pd
from datetime import datetime

CONFIG_FILE = "config.json"
DATA_DIR    = "data"

# ── Income Statement ──────────────────────────────────────────────────────────

SANKEY_FIELD_MAP = {
    "Total Revenue":                     "total_revenue",
    "Cost Of Revenue":                   "cost_of_revenue",
    "Gross Profit":                      "gross_profit",
    "Research And Development":          "rd_expense",
    "Selling General And Administration":"sga_expense",
    "Operating Income":                  "operating_income",
    "Interest Expense":                  "interest_expense",
    "Pretax Income":                     "pretax_income",
    "Tax Provision":                     "tax_provision",
    "Net Income":                        "net_income",
    "EBITDA":                            "ebitda",
    "Basic EPS":                         "eps_basic",
    "Diluted EPS":                       "eps_diluted",
}

TREND_METRICS_MAP = {
    "Total Revenue":    "total_revenue",
    "Gross Profit":     "gross_profit",
    "Operating Income": "operating_income",
    "Net Income":       "net_income",
    "Diluted EPS":      "eps_diluted",
    "EBITDA":           "ebitda",
}

# ── Balance Sheet ─────────────────────────────────────────────────────────────

BALANCE_FIELD_MAP = {
    "Total Assets":                   "total_assets",
    "Total Liabilities Net Minority Interest": "total_liabilities",
    "Stockholders Equity":            "stockholders_equity",
    "Cash And Cash Equivalents":      "cash",
    "Total Debt":                     "total_debt",
    "Net Debt":                       "net_debt",
    "Current Assets":                 "current_assets",
    "Current Liabilities":            "current_liabilities",
    "Inventory":                      "inventory",
    "Accounts Receivable":            "accounts_receivable",
    "Retained Earnings":              "retained_earnings",
    "Common Stock Equity":            "common_equity",
    "Goodwill And Other Intangible Assets": "goodwill_intangibles",
}

# ── Cash Flow Statement ───────────────────────────────────────────────────────

CASHFLOW_FIELD_MAP = {
    "Operating Cash Flow":            "operating_cf",
    "Capital Expenditure":            "capex",
    "Free Cash Flow":                 "free_cash_flow",
    "Investing Cash Flow":            "investing_cf",
    "Financing Cash Flow":            "financing_cf",
    "Issuance Of Debt":               "debt_issuance",
    "Repayment Of Debt":              "debt_repayment",
    "Common Stock Issuance":          "stock_issuance",
    "Common Stock Repurchase":        "stock_repurchase",
    "Changes In Cash":                "net_change_cash",
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
    """Case-insensitive substring match on column names."""
    return next((c for c in df.columns if key.lower() in c.lower()), None)

def fetch_statement(sym: str, kind: str, period: str) -> pd.DataFrame:
    """
    kind: 'income' | 'balance' | 'cashflow'
    period: 'quarterly' | 'annual'
    Returns transposed DataFrame indexed by date, sorted ascending.
    yfinance returns all available periods (full history since IPO).
    """
    tk = yf.Ticker(sym)
    attr_map = {
        ("income",    "quarterly"): "quarterly_income_stmt",
        ("income",    "annual"):    "income_stmt",
        ("balance",   "quarterly"): "quarterly_balance_sheet",
        ("balance",   "annual"):    "balance_sheet",
        ("cashflow",  "quarterly"): "quarterly_cashflow",
        ("cashflow",  "annual"):    "cashflow",
    }
    attr = attr_map.get((kind, period))
    raw = getattr(tk, attr, None)
    if raw is None or raw.empty:
        print(f"  [WARN] No {period} {kind} for {sym}")
        return pd.DataFrame()
    df = raw.T.copy()
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"
    return df.sort_index()

def fetch_estimates(sym: str) -> list:
    """Current analyst EPS and revenue estimates (0q, +1q, 0y, +1y)."""
    tk = yf.Ticker(sym)
    rows = []
    try:
        ee = tk.earnings_estimate
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

def collect_rows_from_map(sym: str, df_q: pd.DataFrame, df_a: pd.DataFrame,
                          field_map: dict) -> list:
    """Generic row collector for any statement + field map."""
    rows = []
    for period_type, df in [("quarterly", df_q), ("annual", df_a)]:
        if df.empty:
            continue
        for dt, row in df.iterrows():
            record = {"ticker": sym.upper(), "period_type": period_type,
                      "date": dt.strftime("%Y-%m-%d")}
            for src_col, dest_col in field_map.items():
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
    all_balance, all_cashflow = [], []

    for sym in tickers:
        print(f"\n--- {sym} ---")

        # Income statement
        df_inc_q = fetch_statement(sym, "income",   "quarterly")
        df_inc_a = fetch_statement(sym, "income",   "annual")
        all_sankey.extend(collect_rows_from_map(sym, df_inc_q, df_inc_a, SANKEY_FIELD_MAP))
        all_trend.extend(collect_trend_rows(sym, df_inc_q, df_inc_a))
        all_estimates.extend(fetch_estimates(sym))

        # Balance sheet
        df_bal_q = fetch_statement(sym, "balance",  "quarterly")
        df_bal_a = fetch_statement(sym, "balance",  "annual")
        all_balance.extend(collect_rows_from_map(sym, df_bal_q, df_bal_a, BALANCE_FIELD_MAP))

        # Cash flow
        df_cf_q  = fetch_statement(sym, "cashflow", "quarterly")
        df_cf_a  = fetch_statement(sym, "cashflow", "annual")
        all_cashflow.extend(collect_rows_from_map(sym, df_cf_q, df_cf_a, CASHFLOW_FIELD_MAP))

    pd.DataFrame(all_sankey).to_csv(  os.path.join(DATA_DIR, "sankey.csv"),   index=False)
    pd.DataFrame(all_trend).to_csv(   os.path.join(DATA_DIR, "trend.csv"),    index=False)
    pd.DataFrame(all_estimates).to_csv(os.path.join(DATA_DIR, "estimates.csv"),index=False)
    pd.DataFrame(all_balance).to_csv( os.path.join(DATA_DIR, "balance.csv"),  index=False)
    pd.DataFrame(all_cashflow).to_csv(os.path.join(DATA_DIR, "cashflow.csv"), index=False)

    for name, lst in [("sankey", all_sankey), ("trend", all_trend),
                      ("estimates", all_estimates), ("balance", all_balance),
                      ("cashflow", all_cashflow)]:
        print(f"Written: data/{name}.csv  ({len(lst)} rows)")

    meta = {"tickers": tickers, "updated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}
    with open(os.path.join(DATA_DIR, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(f"Written: data/meta.json")

if __name__ == "__main__":
    main()
