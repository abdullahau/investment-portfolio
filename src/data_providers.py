# src/data_providers.py

import os
import json
import yfinance as yf
import pandas as pd
import numpy as np

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import config

# --- Yahoo Finance ---
def yf_hist(ticker_symbol, start_date, last_market_day):
    """
    Fetches historical data from yfinance, using a local cache.
    """
    cache_file = config.CACHE_DIR / f"{ticker_symbol}.csv"

    if os.path.exists(cache_file):
        cached_data = pd.read_csv(cache_file, index_col="Date", parse_dates=True)
        if (
            not cached_data.empty
            and cached_data.index.max().normalize() >= last_market_day
        ):
            return cached_data

    ticker = yf.Ticker(ticker_symbol)
    end_date_for_api = last_market_day + pd.Timedelta(days=1)
    hist = ticker.history(start=start_date, end=end_date_for_api)    

    if not hist.empty:
        hist.index = hist.index.tz_localize(None)
        hist.to_csv(cache_file)

    return hist


def yf_info(ticker_symbol):
    
    cache_file = config.CACHE_DIR / "ticker_info_cache.json"
    
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            info_cache = json.load(f)
    else:
        info_cache = {}

    if ticker_symbol in info_cache:
        return info_cache[ticker_symbol]

    ticker = yf.Ticker(ticker_symbol)
    info = ticker.info

    info_cache[ticker_symbol] = info

    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    with open(cache_file, "w") as f:
        json.dump(info_cache, f, indent=4)

    return info


def get_forex_rate(api_key, from_currency, to_currency, date):
    # ... API call to get AED/USD rate for a specific day ...
    pass
