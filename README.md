# Personal Investment Portfolio Dashboard 

### Project Structure


```
portfolio-analyzer/
│
├── .env                  # For secret API keys (Requirement C)
├── .gitignore            # To ignore .env, cache files, etc.
├── config.py             # Loads settings and API keys
│
├── data/
│   ├── cache/            # Cache for API calls
│   └── input/
│       ├── us_mkt_transactions.csv
│       └── exus_mkt_transactions.csv
│
├── notebooks/
│   └── main_analysis.ipynb # Your primary notebook for running analysis and plots
│
├── tools/ 
|   ├── raw-data     
│   ├── prepare-pdf-statements.py
│   ├── statement-to-json.py
│   ├── create-transaction-log.py
│   └── fetch-UAE-market-date.ipynb
│
└── src/
    ├── data_ingestion.py   # Module to load and merge transaction logs
    ├── data_providers.py   # All third-party API functions (yf, Twelve Data, ETFDB)
    ├── benchmark.py        # Logic for the benchmark simulation
    └── portfolio.py        # Logic for your personal portfolio holdings and value
```

-----

## Transaction Log

### Transaction Log Structure

write about the design/shape of the transaction log, show an example, and where it needs to be placed.

### The Transaction Mapping System

Inside the configuration file, `transaction_map.json` the user needs to define how their transaction types should be treated.

#### Standard Actions

Fundamental actions inside a transaction log:

- `trade`: A transaction that changes the quantity of a symbol held (e.g., buy, sell, merger).
- `cash_flow`: A transaction that changes the cash balance but not holdings (e.g., deposit, withdrawal, cash sweep).
- `income`: Cash received from an asset you own (e.g., dividends, interest). This is treated separately from general cash flow for performance analysis.
- `corporate_action`: A non-cash event that changes the quantity of a symbol (e.g., stock split).
- `ignore`: For transaction types that should be completely disregarded by the analysis.

Example: 

```json
{
  "buy": { "action": "trade" },
  "sell": { "action": "trade" },
  "Net Deposit": { "action": "cash_flow" },
  "Net Dividend": { "action": "income" },
  "Credit/Margin Interest": { "action": "income" },
  "High-Yield Cash Sweep": { "action": "ignore" },
  "Merger/Acquisition": { "action": "trade" },
  "Stock Split": { "action": "corporate_action" },
  "Qualified interest income reallocation for 2023": { "action": "ignore" }
}
```
