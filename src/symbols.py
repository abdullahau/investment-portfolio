# src/symbols.py

import os
import json
import sys
import yfinance as yf
import pandas as pd
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

class Symbols:
    def __init__(self, trans_log) -> None:
        """
        Initializes the Symbols manager and loads all relevant data sources ONCE.
        """
        self.trans_log = trans_log
        self.symbols = trans_log['Symbol'].dropna().unique()
        self.cache = _load_json_cache(config.METADATA_CACHE)
        self.full_metadata_cache = _load_json_cache(config.FULL_METADATA_CACHE)
        self.user_metadata = _load_json_cache(config.USER_METADATA)
        self.unified_df = pd.DataFrame()

    def assess(self):
        """
        Checks symbols against the cache and yfinance, updating internal state.
        """
        symbols_changed = False
        for symbol in self.symbols:
            if symbol in self.cache:
                continue
            
            symbols_changed = True
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
                
                self.cache[symbol] = symbol_data
                self.full_metadata_cache[symbol] = info 

            else:
                self.cache[symbol] = {'DataProvider': 'missing'}
                self._user_metadata_template([symbol])
        
        if symbols_changed:
            _save_json_cache(config.METADATA_CACHE, self.cache)
            _save_json_cache(config.FULL_METADATA_CACHE, self.full_metadata_cache)

    def mark_as_user_provided(self, symbols_to_update):
        """
        Updates caches and templates for symbols the user marks as incorrect.
        """
        if not symbols_to_update:
            return
        
        print(f"Updating cache for incorrectly identified symbols: {symbols_to_update}")
        for symbol in symbols_to_update:
            self.cache[symbol] = {'DataProvider': 'user_provided', 'Type': 'user_provided'}
            if symbol in self.full_metadata_cache:
                del self.full_metadata_cache[symbol]
        
        _save_json_cache(config.METADATA_CACHE, self.cache)
        _save_json_cache(config.FULL_METADATA_CACHE, self.full_metadata_cache)
        print("Caches updated successfully.")
        
        self._user_metadata_template(symbols_to_update)

    def _user_metadata_template(self, symbols_to_process):
        """
        Internal helper to create or update the user metadata template IN MEMORY.
        """
        if not symbols_to_process:
            return

        os.makedirs(config.MANUAL_DATA_DIR, exist_ok=True)
        symbol_info = self.trans_log.dropna(subset=['Symbol', 'Exchange', 'Currency'])
        symbol_info = symbol_info.drop_duplicates(subset=['Symbol'], keep='first').set_index('Symbol')

        symbols_added = []
        for symbol in symbols_to_process:
            if symbol in self.user_metadata and self.user_metadata[symbol].get("Name") is not None:
                continue 

            try:
                exchange = symbol_info.loc[symbol, 'Exchange']
                currency = symbol_info.loc[symbol, 'Currency']
                self.user_metadata[symbol] = {
                    "Name": None, 
                    "Exchange": exchange, 
                    "Currency": currency,
                    "Type": None, 
                    "DataProvider": "user_provided",
                    "Industry": None, 
                    "Sector": None
                }
                symbols_added.append(symbol)
            except KeyError:
                self.user_metadata[symbol] = {
                    "Name": None, 
                    "Exchange": None, 
                    "Currency": None, 
                    "Type": None,
                    "DataProvider": "user_provided", 
                    "Industry": None, 
                    "Sector": None
                }
                symbols_added.append(symbol)

        if symbols_added:
            _save_json_cache(config.USER_METADATA, self.user_metadata)
            print(f"User metadata template created/updated for: {symbols_added}.")
            print(f"Please fill in the details in: {config.USER_METADATA}")

    def _build_unified_df(self):
        """
        Builds the unified symbol DataFrame from the class's IN-MEMORY data attributes.
        """
        yfinance_data = {s: d for s, d in self.cache.items() if d.get('DataProvider') == 'yfinance'}
        yfinance_df = pd.DataFrame.from_dict(yfinance_data, orient='index')

        user_df = pd.DataFrame.from_dict(self.user_metadata, orient='index')

        if not user_df.empty:
            self.unified_df = pd.concat([yfinance_df, user_df])
        else:
            self.unified_df = yfinance_df

        if not self.unified_df.empty:
            self.unified_df.index.name = 'Symbol'
            cols_order = ['Name', 'Type', 'Exchange', 'Currency', 'Industry', 'Sector', 'DataProvider']
            self.unified_df = self.unified_df.reindex(columns=cols_order)

        print("Successfully created unified symbols DataFrame.")

    def reload_user_metadata(self):
        """
        Reloads the user-provided metadata file from disk into the class instance.
        This allows the user to see their manual edits without restarting the session.
        """
        print("Reloading user-provided metadata from disk...")
        self.user_metadata = _load_json_cache(config.USER_METADATA)
        print("User metadata reloaded successfully.")        

    def get_unified_df(self):
        """
        Returns the single, unified DataFrame of symbol metadata.
        """
        self._build_unified_df()
        return self.unified_df
        
    def get_found(self):
        """
        Returns a DataFrame of symbols successfully found on yfinance.
        """
        found_symbols = {s: d for s, d in self.cache.items() if d['DataProvider'] == 'yfinance'}
        found_df = pd.DataFrame.from_dict(found_symbols, orient='index')
        if not found_df.empty:
            found_df.index.name = 'Symbol'
            cols_order = ['Name', 'Type', 'Exchange', 'Currency', 'Industry', 'Sector', 'DataProvider']
            found_df = found_df[[col for col in cols_order if col in found_df.columns]]
        return found_df
    
    def get_missing(self):
        """
        Returns a list of symbols not found on yfinance.
        """
        return [s for s, d in self.cache.items() if d['DataProvider'] == 'missing']