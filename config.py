# config.py

import pandas as pd
import yfinance as yf
from os import getenv
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # Reads the .env file

# --- API Keys & Secrets ---
API_KEY_TWELVE_DATA = getenv("TWELVE_DATA_API_KEY")
ACCOUNT_NUM = getenv("ACCOUNT_NUM")
ACCOUNT_NAME = getenv("ACCOUNT_NAME")

# --- Path Management ---
# Root directory
ROOT_DIR = Path(__file__).resolve().parent
# Folders
SRC_DIR = ROOT_DIR / "src"
DATA_DIR = ROOT_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
TRANS_LOG_DIR = DATA_DIR / "transaction-log"
MANUAL_DATA_DIR = DATA_DIR / "manual-source"
TOOLS_DIR = ROOT_DIR / "tools"
DOCS_DIR = ROOT_DIR / "docs"
NOTEBOOKS_DIR = ROOT_DIR / "notebooks"
RAW_DATA_DIR = TOOLS_DIR / "raw-data"
# Cache
PRICE_CACHE = CACHE_DIR / "prices"
USER_PRICE_CACHE = MANUAL_DATA_DIR / "prices"
# Metadata
METADATA_CACHE = CACHE_DIR / "metadata/metadata.json"
USER_METADATA = MANUAL_DATA_DIR / "metadata/metadata.json"
# Transaction Mapping
TRANSACTION_MAP_FILE = TRANS_LOG_DIR / "transaction_map.json"

# --- User-Defined Settings ---
BENCHMARK_INDEX = "VOO"
BASE_CURRENCY = "USD"
TAX_RATE = 0.30
# Fees for the benchmark simulation
FLAT_FEE = 1.0
RATE = 0.0025
MANUAL_DATA_ENTRY = "manual"


# --- Function to Compute Derived Variables ---
def project_dates(log_dates):
    """Computes dynamic date variables based on the transaction log."""
    start_date = log_dates.min()
    today = pd.Timestamp.today().normalize()
    end_date = today - pd.Timedelta(days=1)

    date_range = pd.Series(
        pd.date_range(start=start_date, end=end_date, freq="D"), name="Date"
    )

    hist_recent = yf.Ticker(BENCHMARK_INDEX).history(period="10d")
    hist_recent.index = hist_recent.index.tz_localize(None).normalize()  # pyright: ignore

    completed_market_days = hist_recent[hist_recent.index < today]

    last_market_day = completed_market_days.index.max()

    return start_date, end_date, date_range, last_market_day
