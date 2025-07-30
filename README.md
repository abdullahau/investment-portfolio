# Personal Investment Portfolio Dashboard 

Separate the following steps:

1) Data handling
2) Analysis logic
3) Configuration


### Proposed Project Structure

A modular structure will make it easier to add new features and for others to use your code. Consider organizing your project files like this:

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
│       ├── usd_transactions.csv
│       └── aed_transactions.csv
│
├── notebooks/
│   └── main_analysis.ipynb # Your primary notebook for running analysis and plots
│
├── scripts/                  
│   ├── prepare_pdf_statements.py
│   ├── statement_to_json.py
│   └── create_transaction_log.py
│
└── src/
    ├── data_ingestion.py   # Module to load and merge transaction logs
    ├── data_providers.py   # All third-party API functions (yf, Twelve Data, ETFDB)
    └── portfolio.py        # Core logic for benchmark and holdings analysis
```

-----

### 1. Integrating Your AED Brokerage Account (Multi-Currency)

Your challenge is to combine transaction logs with different currencies and fetch market data from a new provider.

#### **Implementation Steps:**

1.  **Standardize and Merge Logs**:

      * In `src/data_ingestion.py`, create a function that reads both your USD and AED transaction CSVs.
      * This function should add a **`Currency`** column (`USD` or `AED`) to each log before merging them into a single `master_log` DataFrame. This is the most crucial step for handling multi-currency data.

2.  **Abstract Data Fetching**:

      * In `src/data_providers.py`, create new functions specifically for Twelve Data. You will need functions to get historical prices and, importantly, **foreign exchange (FX) rates**.
        ```python
        # In src/data_providers.py
        def get_twelve_data_history(api_key, symbol, exchange):
            # ... API call logic ...

        def get_forex_rate(api_key, from_currency, to_currency, date):
            # ... API call to get AED/USD rate for a specific day ...
        ```

3.  **Convert to a Base Currency**:

      * In your main analysis logic (`src/portfolio.py`), when you calculate the daily value of each asset, check its `Currency` column.
      * If the currency is `AED`, call your new `get_forex_rate` function to get the AED/USD rate for that day and convert the asset's price to USD. This ensures your entire portfolio value is calculated in a single, consistent currency.

-----

### 2. Building the ETF Deep-Dive Feature

This involves adding a new layer of analysis to break down your ETF holdings.

#### **Implementation Steps:**

1.  **Add an ETF Data Provider**:

      * In `src/data_providers.py`, add a function `get_etf_holdings(api_key, etf_symbol)` that uses `pyetf` or another service to fetch the underlying holdings, sectors, and country weights for a given ETF.

2.  **Create an Analysis Module**:

      * Inside `src/portfolio.py` (or a new `src/analysis.py` module), create a function `analyze_etf_exposure(holdings_df)`.
      * This function should:
          * Identify which symbols in your portfolio are ETFs (you can use your `holdings["Ticker Info"]` DataFrame for this).
          * For each ETF you hold, call `get_etf_holdings` to get its constituents.
          * Calculate the **weighted exposure**: For each underlying stock within an ETF, multiply its weight *in the ETF* by the ETF's weight *in your total portfolio*.
          * Aggregate these weighted exposures across all your ETFs to get a final, combined breakdown of your portfolio by **individual stock, sector, and country**.

-----

### 3. Securing Your API Keys

You should never commit API keys or other secrets directly into your code. The standard best practice is to use environment variables.

#### **Implementation Steps:**

1.  **Create a `.env` file**: In the root of your project, create a file named `.env`. Add your secret keys to it.
    ```
    # .env file
    TWELVE_DATA_API_KEY="your_key_here_123"
    ```
2.  **Add `.env` to `.gitignore`**: Make sure the `.env` file is listed in your `.gitignore` file so it is never uploaded to a public repository.
3.  **Load Keys in `config.py`**: Use the `python-dotenv` library to load these keys into your application.
    ```python
    # In config.py
    import os
    from dotenv import load_dotenv

    load_dotenv() # Reads the .env file

    # Now you can access keys as environment variables
    API_KEY_TWELVE_DATA = os.getenv("TWELVE_DATA_API_KEY")
    ```
4.  **Use the Config**: In your API functions in `src/data_providers.py`, import the key from your config file instead of hardcoding it.
    ```python
    # In src/data_providers.py
    import config

    def get_twelve_data_history(symbol, exchange):
        api_key = config.API_KEY_TWELVE_DATA
        # ... rest of the function ...
    ```

-----

### 4. Making the Code Portable for Others

The goal is to decouple your personal data preparation scripts from the core analysis engine.

#### **Implementation Steps:**

1.  **Define a Standard Format**: The most important step is to **document a standard CSV format** for the transaction log. Create a `README.md` file that clearly lists the required columns (e.g., `Date`, `Type`, `Symbol`, `Quantity`, `Price`, `Currency`, `Exchange`).
2.  **Separate Ingestion from Analysis**: Your new modular structure already achieves this. A user can completely ignore your `prepare-pdf-statements.py` scripts. They would simply need to:
      * Create their own CSV file(s) matching your documented format.
      * Place them in the `data/input/` directory.
      * Run your `main_analysis.ipynb`, which reads from that directory.

By adopting this structure, your project will be far more organized, secure, and powerful, allowing you to easily add new features and share your work with others.

### Folder Structure

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
│       ├── usd_transactions.csv
│       └── aed_transactions.csv
│
├── notebooks/
│   └── main_analysis.ipynb # Your primary notebook for running analysis and plots
│
├── tools/                  
│   ├── prepare_pdf_statements.py
│   ├── statement_to_json.py
│   └── create_transaction_log.py
│
└── src/
    ├── data_ingestion.py   # Module to load and merge transaction logs
    ├── data_providers.py   # All third-party API functions (yf, Twelve Data, ETFDB)
    └── portfolio.py        # Core logic for benchmark and holdings analysis
```