# Investment Portfolio Analyzer

This project provides a simple toolkit for analyzing personal investment portfolios. It is designed to be flexible and extensible, allowing users to track their performance against a benchmark, analyze portfolio composition, and handle transactions from multiple brokerages and in multiple currencies.

## Features

- **Multi-Source Transaction Logging**: Combine transaction logs from various sources into a single, unified format.
- **Automated Symbol Assessment**: Uses Yahoo Finance to automatically fetch metadata (name, currency, sector, etc.) for your holdings.
- **User-Guided Data Correction**: A robust workflow allows you to correct any automatically fetched data and provide your own data for symbols not found on free APIs.
- **Comprehensive Portfolio Analysis**:
  - Track the daily value of your portfolio over time.
  - Calculate and view your current holdings.
  - Analyze portfolio concentration by sector, industry, or country.
- **Flexible Benchmarking**: Simulate a benchmark portfolio (e.g., S\&P 500) based on your personal cash flows to accurately compare your performance.
- **Modular and Extensible**: The object-oriented design allows users to easily swap out the default data provider (`yfinance`) with their own.

## Project Structure

```
investment-portfolio/
│
├── .env                  # For secret API keys and account numbers.
├── config.py             # Central hub for all settings and file paths.
│
├── data/
│   ├── cache/            # Caches for API calls to improve performance.
│       ├── metadata/     
│       └── prices/       
│   ├── transaction-log/  # Location for your standardized transaction logs.
│   │   └── transaction_map.json # User-defined mapping for transaction types.
│   └── manual-data/      # For user-provided data.
│       ├── metadata/     # Manually entered symbol metadata.
│       └── prices/       # Manually provided price history CSVs.
│
├── notebooks/
│   └── main.ipynb        # The primary notebook for running the analysis.
│
└── src/
    ├── __init__.py
    ├── data_ingestion.py # Module to load transaction logs.    
    ├── market_data.py    # Abstraction layer for market data providers (defaults to yfinance).
    ├── transaction_processor.py # Contains the TransactionProcessor class.    
    ├── symbols.py        # Contains the Symbols class for managing metadata.
    ├── benchmark.py      # Contains the Benchmark class.
    └── portfolio.py      # Contains the Portfolio class.
```

## Getting Started

### 1\. Setup

Clone the repository and install the required packages:

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root to store any necessary API keys (though none are required for the default `yfinance` provider).

### 2\. Prepare Your Transaction Log

This is the most crucial step. Your analysis will be based on a standardized transaction log.

#### Transaction Log Structure

You must provide your transaction history as one or more CSV files in the `data/transaction-log/` directory. Each CSV file **must** have the following columns:

| Column | Type | Description |
| :--- | :--- | :--- |
| `Date` | Date | The date of the transaction (e.g., `YYYY-MM-DD`). |
| `Type` | String | The type of transaction (e.g., `buy`, `sell`, `Net Deposit`). |
| `Symbol` | String | The ticker symbol for the asset (e.g., `VOO`, `TSLA`). Can be blank for cash flows not specific to a symbol. |
| `Quantity` | Float | The number of shares traded. Positive for buys, negative for sells. |
| `Price` | Float | The price per share of the transaction. |
| `Amount` | Float | The total cash effect of the transaction. **Negative for cash outflows (buys, withdrawals), positive for cash inflows (sells, deposits, dividends).** |
| `Commission` | Float | Any commission paid on the transaction. |
| `Currency` | String | The 3-letter currency code of the transaction (e.g., `USD`, `AED`). |
| `Description`| String | A brief description of the transaction. |
| `Exchange` | String | The exchange where the asset is traded (e.g., `NYSE`, `ADX`). |
| `Source` | String | The source of the transaction data (e.g., `Brokerage Statement`). |

**Example:**

```csv
Date,Type,Symbol,Quantity,Price,Amount,Commission,Currency,Description,Exchange,Source
2023-02-16,Net Deposit,,,,271.57,,USD,Monthly Deposit,CASH,Brokerage
2023-02-17,buy,VOO,0.2189,-372.07,-81.47,,USD,Trade,NYSE,Brokerage
2023-03-29,Net Dividend,VOO,,,,0.24,,USD,Dividend,NYSE,Brokerage
```

### 3\. Configure the Transaction Map

Because different brokers use different names for transaction types, you must tell the application how to interpret your log.

Inside the `data/transaction-log/` directory, edit the `transaction_map.json` file. Map your custom `Type` strings from your CSV to one of the standard actions.

#### Standard Actions

- `trade`: A transaction that changes the quantity of a symbol held (e.g., buy, sell, merger).
- `cash_flow`: A transaction that changes the cash balance but not holdings (e.g., deposit, withdrawal).
- `income`: Cash received from an asset you own (e.g., dividends, interest).
- `corporate_action`: A non-cash event affecting holdings (e.g., stock split).
- `ignore`: For transaction types to be completely disregarded.

**Example `transaction_map.json`:**

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
  "Qualified interest income reallocation": { "action": "ignore" }
}
```

### 4\. Run the Analysis

Open and run the `notebooks/main.ipynb` notebook. The notebook is divided into clear, sequential steps:

1. **Setup and Imports**: Loads all necessary modules.
2. **Load Transaction Data**: Ingests and combines all your transaction logs from the `data/transaction-log/` directory.
3. **Assess Symbols**:
   - The `Symbols` class will check each unique symbol in your log against the default data provider (`yfinance`).
   - It will display a table of symbols it found and a list of symbols it could not find.
4. **User Correction**:
   - Review the table of found symbols. If any are incorrect, add their tickers to the `incorrectly_identified_symbols` list in the notebook.
   - The application will then generate a template file at `data/manual-source/metadata.json` for all missing or incorrect symbols.
5. **Manual Data Entry (User Task)**:
   - Pause the notebook.
   - Open `data/manual-source/metadata.json` and fill in the `null` values for each symbol.
   - For each of these symbols, add a price history CSV file to the `data/manual-source/prices/` directory. The CSV must have the columns: `Date,Open,High,Low,Close,Volume,Dividends,StockSplits`.
6. **Reload and Unify**: Run the cell to reload your manual edits and create a final, unified metadata DataFrame for all symbols.
7. **Run Portfolio and Benchmark Analysis**: Initialize the `Portfolio` and `Benchmark` classes and run their main calculation methods.
8. **View Results**: The final cells will display your current holdings, portfolio concentration, and performance charts.
