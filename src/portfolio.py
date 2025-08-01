# src/portfolio.py

import pandas as pd
import numpy as np

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src import data_providers 
import config

class Portfolio:
    def __init__(self, trans_log, symbol_manager, date_range, last_market_day):
        """
        Initializes the Portfolio analysis engine.
        """
        self.trans_log = trans_log
        self.symbol_manager = symbol_manager
        self.date_range = date_range
        self.last_market_day = last_market_day
        self.symbols = trans_log['Symbol'].dropna().unique()
        
        # Initialize the holdings dictionary to store all DataFrames
        self.holdings = {}
        for name in ["trade", "price", "raw_splits", "holding", "value"]:
            self.holdings[name] = pd.DataFrame(
                0.0, index=self.date_range, columns=self.symbols
            )
            
        print("Portfolio object initialized.")

    def _prepare_trade_log(self):
        """Populates the trade DataFrame from the transaction log."""
        print("Preparing trade log...")
        self.holdings['trade'].update(
            self.trans_log[self.trans_log['Type'].isin(['buy', 'sell'])]
            .groupby(['Date', 'Symbol'])['Quantity'].sum().unstack(fill_value=0)
        )

    def _fetch_price_data(self):
        """Fetches and prepares price and split data for all symbols."""
        print("Fetching price and split data...")
        symbol_df = self.symbol_manager.get_unified_df()
        
        for symbol, row in symbol_df.iterrows():
            data_provider = row['DataProvider']
            hist = None
            
            if data_provider == 'yfinance':
                hist = data_providers.yf_hist(symbol, self.date_range.min(), self.last_market_day)
            elif data_provider == 'user_provided':
                price_file = config.MANUAL_DATA_DIR / f"{symbol}.csv"
                if price_file.exists():
                    hist = pd.read_csv(price_file, index_col='Date', parse_dates=True)
                else:
                    print(f"⚠️ Warning: Price CSV for user symbol '{symbol}' not found.")
                    continue

            if hist is not None and not hist.empty:
                self.holdings['price'][symbol] = hist['Close'].reindex(self.date_range).ffill()
                # Assume user-provided data might not have splits
                if 'Stock Splits' in hist.columns:
                    self.holdings['raw_splits'][symbol] = hist['Stock Splits'].reindex(self.date_range)

        self.holdings['raw_splits'] = self.holdings['raw_splits'].fillna(0.0)

    def _convert_prices_to_usd(self):
        """Converts all non-USD asset prices to USD using daily FX rates."""
        print("Converting prices to base currency (USD)...")
        symbol_df = self.symbol_manager.get_unified_df()
        non_usd_symbols = symbol_df[symbol_df['Currency'] != 'USD']
        
        # Fetch FX rates only if needed
        fx_tickers = [f"{currency}USD=X" for currency in non_usd_symbols['Currency'].unique()]
        fx_rates = {}
        for fx_ticker in fx_tickers:
            fx_hist = data_providers.yf_hist(fx_ticker, self.date_range.min(), self.last_market_day)
            fx_rates[fx_ticker[:3]] = fx_hist['Close'].reindex(self.date_range).ffill()

        for symbol, row in non_usd_symbols.iterrows():
            currency = row['Currency']
            if currency in fx_rates:
                self.holdings['price'][symbol] *= fx_rates[currency]

    def calculate_holdings_and_value(self):
        """
        Calculates daily holdings and market value for the entire portfolio.
        This is the main calculation engine.
        """
        self._prepare_trade_log()
        self._fetch_price_data()
        self._convert_prices_to_usd()

        print("Calculating daily holdings and value...")
        for symbol in self.symbols:
            split_series = self.holdings['raw_splits'][symbol].replace(0, 1)
            for i in range(len(self.date_range)):
                prev_holding = self.holdings['holding'].iloc[i - 1][symbol] if i > 0 else 0
                split_ratio = split_series.iloc[i]
                
                holding_after_split = prev_holding * split_ratio
                final_holding = holding_after_split + self.holdings['trade'].iloc[i][symbol]
                self.holdings['holding'].iloc[i, self.holdings['holding'].columns.get_loc(symbol)] = final_holding

        self.holdings['value'] = self.holdings['holding'] * self.holdings['price']
        self.holdings['Total Portfolio Value'] = self.holdings['value'].sum(axis=1)
        print("Calculations complete.")

    def get_current_holdings(self):
        """Returns a DataFrame of the most recent holdings and their market value."""
        current_date = self.last_market_day
        current_holdings = self.holdings['holding'].loc[current_date]
        current_value = self.holdings['value'].loc[current_date]
        
        summary = pd.DataFrame({
            'Shares': current_holdings,
            'Market Value (USD)': current_value
        })
        return summary[summary['Shares'] > 0]

    # You can continue to add methods for your other analysis points (b through f) here.
    # For example:
    def get_concentration(self, by='Sector'):
        """Calculates portfolio concentration by Industry or Sector."""
        current_holdings = self.get_current_holdings()
        symbol_df = self.symbol_manager.get_unified_df()
        
        # Merge with symbol metadata to get the concentration category
        merged = current_holdings.merge(symbol_df, left_index=True, right_index=True)
        concentration = merged.groupby(by)['Market Value (USD)'].sum()
        
        return (concentration / concentration.sum()) * 100
    
    
'''
The schematic idea is:
1) Take the transaction log and map the trade to a wide-form dataframe (symbols are columns, index is date, values are trades (quantity)
2) track holdings across time (full date range), account for splits (available in yfinanace but MAY not be available in user-provided data and if it is not provided, can be ignored), adjust holdings for splits
3) obtain closing prices for each symbol over the entire date range
4) compute value of adjusted holdings over time.
5) user-provided data can be of different lengths and different trading days. Ensure that all price data is forward filled from the last trading day and that not event data (dividends, splits, etc) are not forward filled.
6) information in the main notebook can be taken from the symbols_df
7) symbols which are user provided (missing from yfinance or marked as incorrect) price data should be found in config.MANUAL_DATA_DIR
8) All symbols and their price history will need to be converted to USD if they are in non-USD currency
9) the point of this class is not just to evaluate performance over time but also to look at the following:
    a) my current portfolio holdings
    b) total realized/unrealized gains for the portfolio and individual stock in my portfolio, split between capital gains and income earned for each holding and in aggregate (realized gain if the holding was sold and unrealized gains if unsold)
    c) my current holdings industry and sector concentration 
    d) geographic concentration (note that this metadata has not yet been added to `Symbols` and will be considered later.
    e) I would also like to look at total deposits and total return (gains/earnings) over the investment period.
    f) Then consider ways to evaluate returns that factor in cash outflows, inflows and unrealized earnings that accounts for time value of money
'''