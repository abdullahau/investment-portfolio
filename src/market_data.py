# src/market_data.py

import os
import json
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import config
import pandas as pd

import yfinance as yf

class MarketData:
    """
    Default data provider using Yahoo Finance.
    A user can replace this class with their own data provider as long as
    it has the same methods and returns data in the same standardized format.
    """
    def get_metadata(self, symbol):
        """
        Fetches metadata for a single symbol.

        Returns:
            A dictionary with a standard set of keys, or None if the symbol is not found.
        """
        try:
            with open(os.devnull, 'w') as fnull:
                original_stderr = sys.stderr
                sys.stderr = fnull
                info = yf.Ticker(symbol).info
                sys.stderr = original_stderr

            if info and info.get('market') and info.get('regularMarketPrice') is not None:
                quote_type = info.get('quoteType')
                
                metadata = {
                    'Name': info.get('longName'),
                    'Exchange': info.gexet('fullExchangeName'),
                    'Currency': info.get('currency'),
                    'Type': quote_type.lower() if quote_type else 'N/A',
                    'Country': info.get('country'),
                    'Industry': info.get('industry') if quote_type == 'EQUITY' else None,
                    'Sector': info.get('sector') if quote_type == 'EQUITY' else None,
                }
                return metadata
            else:
                return None 
        except Exception:
            return None

    def get_history(self, symbol, start_date, last_market_day):
        """
        Fetches historical price data for a single symbol.

        Returns:
            A DataFrame with standardized columns, or an empty DataFrame if no data is found.
        """
        cache_file = config.CACHE_DIR / f"{symbol}.csv"
        if os.path.exists(cache_file):
            cached_data = pd.read_csv(cache_file, index_col="Date", parse_dates=True)
            if not cached_data.empty and cached_data.index.max().normalize() >= last_market_day:
                return cached_data

        end_date_for_api = last_market_day + pd.Timedelta(days=1)
        hist = yf.Ticker(symbol).history(start=start_date, end=end_date_for_api)

        if not hist.empty:
            hist.index = hist.index.tz_localize(None)
            hist.rename(columns={'Stock Splits': 'StockSplits'}, inplace=True)
            hist.to_csv(cache_file)

        return hist 
    
    def get_provider_name(self):
        """Returns the name of the data provider."""
        return "yfinance"