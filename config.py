# config.py

import os
import pandas as pd
import yfinance as yf
from pathlib import Path
from dotenv import load_dotenv

load_dotenv() # Reads the .env file

# --- API Keys & Secrets ---
API_KEY_TWELVE_DATA = os.getenv("TWELVE_DATA_API_KEY")
ACCOUNT_NUM = os.getenv("ACCOUNT_NUM")
ACCOUNT_NAME = os.getenv("ACCOUNT_NAME")

# --- Path Management ---
# Absolute path to the project's root directory
ROOT_DIR = Path(__file__).resolve().parent
# Important directories relative to the root
SRC_DIR = ROOT_DIR / "src"
DATA_DIR = ROOT_DIR / "data"
INPUT_DATA_DIR = DATA_DIR / "input"
TOOLS_DIR = ROOT_DIR / "tools"
DOCS_DIR = ROOT_DIR / "docs"
NOTEBOOKS_DIR = ROOT_DIR / "notebooks"
RAW_DATA_DIR = TOOLS_DIR / "raw-data"

# --- User-Defined Settings ---
BENCHMARK_INDEX = 'VOO'
TAX_RATE = 0.30
# Fees for the benchmark simulation
FLAT_FEE = 1.0
RATE = 0.0025

# --- Function to Compute Derived Variables ---
def project_dates(log_dates):
    """Computes dynamic date variables based on the transaction log."""
    start_date = log_dates.min()
    end_date = pd.Timestamp.today().normalize() - pd.Timedelta(days=1)
    
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    
    # Get the last market day for caching purposes
    last_market_day = (
        yf.Ticker(BENCHMARK_INDEX)
        .history(period="5d")
        .index.max()
        .tz_localize(None)
        .normalize()
    )
    
    return start_date, end_date, date_range, last_market_day
