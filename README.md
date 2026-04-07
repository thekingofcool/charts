# Financial Dashboard — README

A minimal stock financial dashboard. The Python fetcher (`fetch_financials.py`) pulls data from yfinance and writes CSV/JSON files into `data/`. The frontend (`index.html`) reads those files and renders them with D3.

---

## File Structure

```
.
├── config.json            # Tickers and display defaults
├── fetch_financials.py    # Data fetcher (run locally or via GitHub Actions)
├── index.html             # Frontend dashboard
└── data/
    ├── meta.json          # Tickers list + last update timestamp
    ├── sankey.csv         # Income statement rows (for Revenue Breakdown chart)
    ├── trend.csv          # Long-form income metrics (for trend chart)
    ├── estimates.csv      # Analyst EPS + revenue estimates
    ├── balance.csv        # Balance sheet rows
    └── cashflow.csv       # Cash flow statement rows
```

---

## Data Source

All financial data is sourced from **[yfinance](https://github.com/ranaroussi/yfinance)**, which wraps Yahoo Finance's undocumented API.

- **Income statement**: `Ticker.quarterly_income_stmt` / `Ticker.income_stmt`
- **Balance sheet**: `Ticker.quarterly_balance_sheet` / `Ticker.balance_sheet`
- **Cash flow**: `Ticker.quarterly_cashflow` / `Ticker.cashflow`
- **Analyst estimates**: `Ticker.earnings_estimate` / `Ticker.revenue_estimate`

yfinance returns the full history available on Yahoo Finance (typically since IPO for income statement; fewer periods for balance sheet and cash flow). All available periods are written to CSV — no truncation.

Column matching is fuzzy (case-insensitive substring) to handle minor naming variations across tickers.

---

## Metrics Reference

### Income Statement (`sankey.csv`, `trend.csv`)

| Field | yfinance Source Column | Description |
|---|---|---|
| `total_revenue` | Total Revenue | Net revenue / top-line sales |
| `cost_of_revenue` | Cost Of Revenue | Direct cost of goods/services sold (COGS) |
| `gross_profit` | Gross Profit | Revenue − COGS |
| `rd_expense` | Research And Development | R&D spend |
| `sga_expense` | Selling General And Administration | Sales, marketing, and G&A costs |
| `operating_income` | Operating Income | Gross Profit − Operating Expenses (EBIT) |
| `interest_expense` | Interest Expense | Net interest paid on debt |
| `pretax_income` | Pretax Income | Operating Income − Interest Expense ± other |
| `tax_provision` | Tax Provision | Income tax expense (stored as positive) |
| `net_income` | Net Income | Bottom-line profit after tax |
| `ebitda` | EBITDA | Operating Income + D&A (reported by Yahoo) |
| `eps_basic` | Basic EPS | Net Income / basic shares outstanding |
| `eps_diluted` | Diluted EPS | Net Income / diluted shares outstanding |

### Balance Sheet (`balance.csv`)

| Field | yfinance Source Column | Description |
|---|---|---|
| `total_assets` | Total Assets | All assets owned |
| `total_liabilities` | Total Liabilities Net Minority Interest | All obligations |
| `stockholders_equity` | Stockholders Equity | Assets − Liabilities (book value) |
| `cash` | Cash And Cash Equivalents | Liquid cash on hand |
| `total_debt` | Total Debt | Short-term + long-term debt |
| `net_debt` | Net Debt | Total Debt − Cash (reported by Yahoo) |
| `current_assets` | Current Assets | Assets convertible to cash within 1 year |
| `current_liabilities` | Current Liabilities | Obligations due within 1 year |
| `inventory` | Inventory | Unsold goods (relevant for product companies) |
| `accounts_receivable` | Accounts Receivable | Revenue earned but not yet collected |
| `goodwill_intangibles` | Goodwill And Other Intangible Assets | Acquisition premiums + IP |
| `retained_earnings` | Retained Earnings | Cumulative net income not paid as dividends |
| `common_equity` | Common Stock Equity | Fallback for stockholders equity |

### Cash Flow (`cashflow.csv`)

| Field | yfinance Source Column | Description |
|---|---|---|
| `operating_cf` | Operating Cash Flow | Cash generated from core business operations |
| `capex` | Capital Expenditure | Cash spent on PP&E and infrastructure (negative value) |
| `free_cash_flow` | Free Cash Flow | Operating CF + CapEx (FCF = OCF − |CapEx|) |
| `investing_cf` | Investing Cash Flow | Cash from investing activities (acquisitions, asset sales) |
| `financing_cf` | Financing Cash Flow | Cash from debt and equity transactions |
| `debt_issuance` | Issuance Of Debt | New debt raised |
| `debt_repayment` | Repayment Of Debt | Debt principal paid back |
| `stock_issuance` | Common Stock Issuance | Shares sold (dilutive) |
| `stock_repurchase` | Common Stock Repurchase | Shares bought back (anti-dilutive) |
| `net_change_cash` | Changes In Cash | Net change in cash position for the period |

### Analyst Estimates (`estimates.csv`)

| Field | Description |
|---|---|
| `estimate_period` | `0q` = current quarter, `+1q` = next quarter, `0y` = current year, `+1y` = next year |
| `metric` | `eps_diluted` or `total_revenue` |
| `estimate` | Consensus analyst mean estimate |

---

## Derived Ratios (Computed in Frontend)

These are not stored in CSV; they are calculated at render time from the raw fields above.

| Ratio | Formula | Interpretation |
|---|---|---|
| **Gross Margin** | Gross Profit / Revenue | Pricing power and production efficiency |
| **Operating Margin** | Operating Income / Revenue | Core business profitability |
| **Net Margin** | Net Income / Revenue | Bottom-line after all costs and taxes |
| **Current Ratio** | Current Assets / Current Liabilities | Short-term liquidity (≥1.5 healthy) |
| **Quick Ratio** | (Current Assets − Inventory) / Current Liabilities | Stricter liquidity test (≥1.0 healthy) |
| **Debt / Equity** | Total Debt / Stockholders Equity | Financial leverage |
| **Net Debt / EBITDA** | Net Debt / EBITDA | Debt repayment capacity (≤2x comfortable) |
| **Return on Assets** | Net Income / Total Assets | How efficiently assets generate profit |
| **Return on Equity** | Net Income / Stockholders Equity | Return to shareholders on book value |
| **FCF Margin** | Free Cash Flow / Revenue | Cash generation efficiency relative to revenue |
| **FCF Conversion** | Free Cash Flow / Operating Cash Flow | How much operating CF converts to FCF after CapEx |

---

## Revenue Breakdown (Sankey) — Flow Logic

The Sankey diagram renders an acyclic directed graph. All flows must sum correctly at each node.

**Profitable at operating level (Operating Income ≥ 0):**
```
Revenue ──→ COGS
        └──→ Gross Profit ──→ R&D
                          ├──→ SG&A
                          └──→ Op. Income ──→ Interest
                                          ├──→ Tax
                                          └──→ Net Income / Net Loss
```
Accounting identity holds: `Revenue = COGS + Gross Profit`, `Gross Profit = R&D + SG&A + Op. Income`.

**Operating loss (Operating Income < 0):**
```
Revenue ──→ COGS
        └──→ Gross Profit ──→ R&D  (proportional share of Gross Profit)
                          ├──→ SG&A (proportional share of Gross Profit)
                          └──→ Op. Loss (residual = |Op. Income|)
```
Gross Profit is split proportionally across R&D and SG&A based on their relative sizes; the balance flows to the Op. Loss terminal node. This keeps the graph acyclic and flows numerically balanced.

**Why not show the full R&D and SG&A values when losing money?**  
In a Sankey diagram, every node's outflow must equal its inflow. When `R&D + SG&A > Gross Profit`, there is no upstream source to cover the excess without creating a cycle. The proportional allocation shows the correct economic picture: Gross Profit partially funds operations, and the net operating loss is the unrecovered deficit.

---

## Running the Fetcher

```bash
pip install yfinance pandas
python fetch_financials.py
```

Edit `config.json` to change tickers:

```json
{
  "tickers": ["AAPL", "MSFT"],
  "default_period": "quarterly",
  "default_metric": "total_revenue"
}
```

The fetcher writes all output to `data/`. Serve `index.html` with any static file server (e.g. `python -m http.server`) or deploy via Cloudflare Pages.

---

## GitHub Actions (Optional)

Schedule nightly data refresh:

```yaml
# .github/workflows/fetch.yml
on:
  schedule:
    - cron: '0 22 * * *'
  workflow_dispatch:

jobs:
  fetch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install yfinance pandas
      - run: python fetch_financials.py
      - uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "data: nightly update"
```
