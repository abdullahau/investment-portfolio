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

def _load_json_cache(file_path):
    """Generic helper function to load a JSON cache file."""
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return {}

def _save_json_cache(file_path, data):
    """Generic helper function to save data to a JSON cache file."""
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

def assess_symbols_with_cache(symbols):
    """
    Checks symbols against a local cache first, then yfinance.
    """
    cache = _load_json_cache(config.METADATA_CACHE)
    full_metadata_cache = _load_json_cache(config.FULL_METADATA_CACHE)
    
    for symbol in symbols:
        if symbol in cache:
            continue

        print(f"Checking new symbol '{symbol}' with yfinance...")
        
        with open(os.devnull, 'w') as fnull:
            original_stderr = sys.stderr
            sys.stderr = fnull
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
            except Exception as e:
                info = {}
            finally:
                sys.stderr = original_stderr
        
        if info and info.get('market') and info.get('regularMarketPrice') is not None:
            quote_type = info.get('quoteType')
            
            symbol_data = {
                'Name': info.get('longName'),
                'Exchange': info.get('fullExchangeName'),
                'Currency': info.get('currency'),
                'Type': quote_type.lower() if quote_type else 'N/A',
                'DataProvider': 'yfinance'
            }
            
            if quote_type == 'EQUITY':
                symbol_data['Industry'] = info.get('industry')
                symbol_data['Sector'] = info.get('sector')
            else: 
                symbol_data['Industry'] = None
                symbol_data['Sector'] = None
            
            cache[symbol] = symbol_data
            full_metadata_cache[symbol] = info 

        else:
            cache[symbol] = {'DataProvider': 'missing'}
            
    _save_json_cache(config.METADATA_CACHE, cache)
    _save_json_cache(config.FULL_METADATA_CACHE, full_metadata_cache)
    
    found_symbols = {s: d for s, d in cache.items() if d['DataProvider'] == 'yfinance'}
    missing_symbols = [s for s, d in cache.items() if d['DataProvider'] == 'missing']
    
    found_df = pd.DataFrame.from_dict(found_symbols, orient='index')
    if not found_df.empty:
        cols_order = ['Name', 'Type', 'Exchange', 'Currency', 'Industry', 'Sector', 'DataProvider']
        found_df = found_df[[col for col in cols_order if col in found_df.columns]]

    return found_df, missing_symbols

def mark_symbols_as_user_defined(symbols_to_update):
    """
    Updates the cache to mark specified symbols as requiring user-provided data.
    """
    if not symbols_to_update:
        return
        
    cache = _load_json_cache(config.METADATA_CACHE)
    print(f"Updating cache for incorrectly identified symbols: {symbols_to_update}")
    for symbol in symbols_to_update:
        cache[symbol] = {'DataProvider': 'user_defined', 'Type': 'user_defined'}
    
    _save_json_cache(config.METADATA_CACHE, cache)
    print("Cache updated successfully.")

def create_user_metadata_template(master_log, symbols_to_process):
    """
    Creates or updates a metadata.json template for symbols that need
    user-provided data. It pre-fills details from the transaction log.
    """
    if not symbols_to_process:
        print("No symbols require user-defined metadata.")
        return

    os.makedirs(config.USER_DATA_DIR, exist_ok=True)

    metadata_template = _load_json_cache(config.USER_METADATA)

    symbol_info = master_log.dropna(subset=['Symbol', 'Market', 'Currency'])
    symbol_info = symbol_info.drop_duplicates(subset=['Symbol'], keep='first').set_index('Symbol')

    symbols_added = []
    for symbol in symbols_to_process:
        if symbol in metadata_template:
            continue

        try:
            market = symbol_info.loc[symbol, 'Market']
            currency = symbol_info.loc[symbol, 'Currency']

            metadata_template[symbol] = {
                "Name": None,
                "Exchange": market,
                "Currency": currency,
                "Type": None,
                "DataProvider": "user_defined",
                "Industry": None,
                "Sector": None
            }
            symbols_added.append(symbol)
        except KeyError:
            print(f"Warning: Could not find Market/Currency for '{symbol}' in the log. Creating a blank template.")
            metadata_template[symbol] = {
                "Name": None, "Exchange": None, "Currency": None, "Type": None,
                "DataProvider": "user_defined", "Industry": None, "Sector": None
            }
            symbols_added.append(symbol)

    if symbols_added:
        _save_json_cache(config.USER_METADATA, metadata_template)
        print(f"Created/updated metadata template for: {symbols_added}")
        print(f"Please fill in the details in the file: {config.USER_METADATA}")
    else:
        print("User metadata template is already up to date.")

# --- Yahoo Finance ---
def yf_hist(ticker_symbol, start_date, last_market_day):

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
