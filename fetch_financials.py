#!/usr/bin/env python3
import json, os
import yfinance as yf
import pandas as pd
from datetime import datetime

CONFIG_FILE = "config.json"
DATA_DIR    = "data"

def load_config():
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def fetch_data_for_ticker(sym):
    print(f"Fetching {sym}...")
    tk = yf.Ticker(sym)
    
    # 1. 获取利润表（优先使用最新接口）
    df = tk.quarterly_income_stmt
    if df is None or df.empty:
        df = tk.quarterly_financials
    
    if df is None or df.empty:
        return None, None

    # 强制日期排序（从旧到新），确保 2025/2026 数据在最后
    df.columns = pd.to_datetime(df.columns)
    df = df.reindex(sorted(df.columns), axis=1)
    
    # 2. 准备趋势数据 (Trend)
    trend_list = []
    for col in df.columns:
        date_str = col.strftime('%Y-%m-%d')
        # 提取核心指标
        rev = df.loc['Total Revenue', col] if 'Total Revenue' in df.index else 0
        eps = df.loc['Basic EPS', col] if 'Basic EPS' in df.index else 0
        
        trend_list.append({
            "ticker": sym.upper(),
            "date": date_str,
            "label": f"{col.year} Q{(col.month-1)//3 + 1}",
            "revenue": float(rev) / 1e9, # 单位：十亿美元
            "eps": float(eps)
        })

    # 3. 准备桑基图数据 (Sankey) - 取最新一个季度
    latest_col = df.columns[-1]
    l = df[latest_col]
    sankey_row = {
        "ticker": sym.upper(),
        "date": latest_col.strftime('%Y-%m-%d'),
        "total_revenue": float(l.get('Total Revenue', 0)),
        "cost_of_revenue": float(l.get('Cost Of Revenue', 0)),
        "gross_profit": float(l.get('Gross Profit', 0)),
        "rd_expense": float(l.get('Research And Development', 0)),
        "sga_expense": float(l.get('Selling General And Administration', 0)),
        "net_income": float(l.get('Net Income', 0))
    }
    
    return pd.DataFrame(trend_list), pd.DataFrame([sankey_row])

def main():
    cfg = load_config()
    ensure_dir()
    tickers = cfg.get("tickers", ["U", "APP"])
    
    all_trends = []
    all_sankeys = []

    for sym in tickers:
        t_df, s_df = fetch_data_for_ticker(sym)
        if t_df is not None:
            all_trends.append(t_df)
            all_sankeys.append(s_df)

    pd.concat(all_trends).to_csv(os.path.join(DATA_DIR, "trend.csv"), index=False)
    pd.concat(all_sankeys).to_csv(os.path.join(DATA_DIR, "sankey.csv"), index=False)
    print("Done. Data saved to /data.")

if __name__ == "__main__":
    main()
