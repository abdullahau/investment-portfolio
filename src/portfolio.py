# src/portfolio.py

import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
import config
from src.market_data import MarketData
from src.transaction_processor import TransactionProcessor


class Portfolio:
    def __init__(
        self,
        trans_log,
        symbol_manager,
        date_range,
        last_market_day,
        base_currency=config.BASE_CURRENCY,
        data_provider=MarketData(),
    ):
        """
        Initializes the Portfolio analysis engine.
        """
        self.trans_log = trans_log
        self.symbol_manager = symbol_manager
        self.date_range = date_range
        self.last_market_day = last_market_day
        self.data_provider = data_provider
        self.base_currency = base_currency
        self.symbols = trans_log["Symbol"].dropna().unique()
        self.processor = TransactionProcessor(trans_log)
        self.fx_rates = None

        # Initialize the holdings dictionary to store all DataFrames
        self.holdings = {}
        for name in ["trade", "price", "raw_splits", "holding", "value", "income"]:
            self.holdings[name] = pd.DataFrame(
                0.0, index=self.date_range, columns=self.symbols
            )

        print("Portfolio object initialized.")

    def _prepare_trade_log(self):
        """Populates the trade DataFrame from the transaction log."""
        print("Preparing trade log...")
        trade_log = self.processor.get_log_for_action("trade")
        self.holdings["trade"].update(
            trade_log.groupby(["Date", "Symbol"])["Quantity"]
            .sum()
            .unstack(fill_value=0)
        )

    def _fetch_price_data(self):
        """Fetches and prepares price and split data for all symbols."""
        print("Fetching price and split data...")
        symbol_df = self.symbol_manager.get_unified_df()

        for symbol, row in symbol_df.iterrows():
            provider_name = row["DataProvider"]
            hist = None

            if provider_name == self.data_provider.get_provider_name():
                hist = self.data_provider.get_history(
                    symbol, self.date_range.min(), self.last_market_day
                )
            elif provider_name == config.MANUAL_DATA_ENTRY:
                price_file = config.USER_PRICE_CACHE / f"{symbol}.csv"
                if price_file.exists():
                    hist = pd.read_csv(price_file, index_col="Date", parse_dates=True)
                else:
                    print(f"⚠️ Warning: Price CSV for user symbol '{symbol}' not found.")
                    continue

            if hist is not None and not hist.empty:
                self.holdings["price"][symbol] = (
                    hist["Close"].reindex(self.date_range).ffill()
                )
                if "StockSplits" in hist.columns:
                    self.holdings["raw_splits"][symbol] = hist["StockSplits"].reindex(
                        self.date_range
                    )

        self.holdings["raw_splits"] = self.holdings["raw_splits"].fillna(0.0)

    def _convert_prices_to_base_currency(self):
        """
        Converts all non-base currency asset prices using the data provider.
        """
        print(f"Converting prices to base currency ({self.base_currency})...")
        symbol_df = self.symbol_manager.get_unified_df()
        non_base_symbols = symbol_df[symbol_df["Currency"] != self.base_currency]

        unique_currencies = non_base_symbols["Currency"].dropna().unique()
        if len(unique_currencies) == 0:
            return

        # Create a list of currency pairs to fetch, e.g., [('AED', 'USD')]
        currency_pairs = [
            (currency, self.base_currency) for currency in unique_currencies
        ]

        fx_rates = self.data_provider.get_fx_rates(
            currency_pairs, self.date_range.min(), self.last_market_day
        )
        self.fx_rates = fx_rates

        for symbol, row in non_base_symbols.iterrows():
            currency = row["Currency"]
            pair = (currency, self.base_currency)
            if pair in fx_rates:
                self.holdings["price"][symbol] *= (
                    fx_rates[pair].reindex(self.date_range).ffill()
                )

    def _cumulative_split_factors(self, split_series: pd.Series) -> pd.Series:
        """
        Computes cumulative split factors for retroactive holding adjustment.
        """
        factors = split_series.replace(0, 1)
        cumulative = factors[::-1].ffill().cumprod()[::-1].shift(-1)
        return cumulative.fillna(1.0)
    
    def _calculate_income(self):
        """
        Calculates and aggregates all income transactions from the log,
        converting them to the base currency.
        """
        print("Calculating portfolio income...")
        income_log = self.processor.get_log_for_action('income').copy()
        
        non_base_currencies = income_log[income_log['Currency'] != self.base_currency]['Currency'].dropna().unique()
        if len(non_base_currencies) > 0:
            currency_pairs = [(currency, self.base_currency) for currency in non_base_currencies]
            fx_rates = self.data_provider.get_fx_rates(
                currency_pairs, self.date_range.min(), self.last_market_day
            )
            for currency in non_base_currencies:
                pair = (currency, self.base_currency)
                if pair in fx_rates:
                    is_currency = income_log['Currency'] == currency
                    conversion_rates = fx_rates[pair].reindex(income_log.loc[is_currency].index, method='ffill')
                    income_log.loc[is_currency, 'Amount'] *= conversion_rates
        
        income_pivot = income_log.groupby(['Date', 'Symbol'])['Amount'].sum().unstack(fill_value=0)
        self.holdings['income'].update(income_pivot)

    def calculate_holdings_and_value(self):
        """
        Calculates daily holdings and market value for the entire portfolio.
        This is the main calculation engine.
        """
        self._prepare_trade_log()
        self._fetch_price_data()
        self._convert_prices_to_base_currency()
        self._calculate_income()

        print("Calculating daily holdings and value...")
        for symbol in self.symbols:
            split_series = self.holdings["raw_splits"][symbol].replace(0, 1)
            for i in range(len(self.date_range)):
                prev_holding = (
                    self.holdings["holding"].iloc[i - 1][symbol] if i > 0 else 0
                )
                split_ratio = split_series.iloc[i]

                holding_after_split = prev_holding * split_ratio
                final_holding = (
                    holding_after_split + self.holdings["trade"].iloc[i][symbol]
                )
                self.holdings["holding"].iloc[
                    i, self.holdings["holding"].columns.get_loc(symbol)
                ] = final_holding

        print("Calculating split-adjusted holdings and market value...")
        self.holdings["adj holding"] = self.holdings["holding"].copy()
        self.holdings["cumulative splits"] = pd.DataFrame(
            1.0, index=self.date_range, columns=self.symbols
        )

        for symbol in self.symbols:
            split_factors = self._cumulative_split_factors(
                self.holdings["raw_splits"][symbol]
            )
            self.holdings["cumulative splits"][symbol] = split_factors

            self.holdings["adj holding"][symbol] = (
                self.holdings["holding"][symbol] * split_factors
            )

        self.holdings["value"] = self.holdings["adj holding"] * self.holdings["price"]
        self.holdings["Total Portfolio Value"] = self.holdings["value"].sum(axis=1)

        print("Calculations complete.")

    def get_income(self):
        """Returns a time series of total income for the portfolio."""
        return self.holdings['income'].sum(axis=1)

    def get_monthly_income(self):
        """Returns a time series of total monthly income for the portfolio."""
        return self.holdings['income'].sum(axis=1).resample('ME').sum()

    def get_individual_value_history(self):
        """Returns a DataFrame of the daily market value for each individual holding."""
        return self.holdings['value']

    def get_current_holdings(self):
        """Returns a DataFrame of the most recent holdings and their market value."""
        current_date = self.last_market_day
        current_holdings = self.holdings["holding"].loc[current_date]
        current_value = self.holdings["value"].loc[current_date]

        summary = pd.DataFrame(
            {"Shares": current_holdings, "Market Value (USD)": current_value}
        )
        return summary[summary["Shares"] > 0]

    def get_total_value_history(self):
        """
        Returns the 'Total Portfolio Value' time series.
        This is the primary output for performance charting.
        """
        if "Total Portfolio Value" in self.holdings:
            return self.holdings["Total Portfolio Value"]
        else:
            print(
                "⚠️ Warning: Total Portfolio Value has not been calculated yet. Run calculate_holdings_and_value() first."
            )
            return None

    def get_holdings_dict(self):
        """
        Returns the entire dictionary of holdings DataFrames.
        Useful for deeper, custom analysis.
        """
        return self.holdings

    # You can continue to add methods for your other analysis points (b through f) here.
    # For example:
    def get_concentration(self, by="Sector"):
        """Calculates portfolio concentration by Industry or Sector."""
        current_holdings = self.get_current_holdings()
        symbol_df = self.symbol_manager.get_unified_df()

        # Merge with symbol metadata to get the concentration category
        merged = current_holdings.merge(symbol_df, left_index=True, right_index=True)
        concentration = merged.groupby(by)["Market Value (USD)"].sum()

        return (concentration / concentration.sum()) * 100


"""
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
    
There are a few important facts to keep in mind about information inside the transaction/master logs

Firstly it is mandatory to structure all transaction logs with the following headers:

Date, Type, Symbol, Quantity, Price, Amount, Commission, Currency, Description, Exchange, Source

There are quite a few variations we can expect in "Type" of transactions. One this is for sure, this cannot be an empty field.

In my case, for example, I have the following Types: 'Net Deposit', 'buy', 'Net Dividend', 'sell', 'Qualified interest income reallocation for 2023', 'Credit/Margin Interest', 'Merger/Acquisition', 'Stock Split', 'High-Yield Cash Sweep'.

I have a small custom script to clean up data and removing useless entries like warrants and inter-account transfer of funds between equity and crypto.

But generally, I would like to enforce the following for all users:
1) Deposits and withdrawals should be Net deposits. If cash was deposited, ensure it is positive `Amount`. If cash was withdrawn, ensure it is negative `Amount`.
2) All dividend income should be net of taxes.
3)  `Credit/Margin Interest` income should be net of taxes too.
4) `buy`, `sell` should be separated for purchase Amount spent and commission paid.

Everything else is a bit of an accounting standard employed in the preperation.

My transactions log has two entries for a Stock Split event for any stock that has been split. On the same date there is a negative of quantity and positive of quantity to reflect the update in holdings. While this can be ignored entirely if the symbol has a prop data provider like yfinance or others where `get_history` call will return a price, dividend, and stock split history. But this may not be true for manually entered price histories. 

In my transaction log, I also have two entries of a single symbol of type 'Merger/Acquisition'. This is where the one symbol was acquired so one entry shows a reduction in the quantity of that symbol and another entry showing an inflow of 'Amount'. While this isn't "income", it is capital returned (either with some gain or with some loss), how should this amount be treated? Does it affect how we simulate benchmark? Or should it be ignored in benchmark simulation? How do we show gains and losses?

'High-Yield Cash Sweep' entries are just inflows and outflows of funds from cash account to a FIDIC insured cash pool.

'Qualified interest income reallocation for 2023' is just an accounting anomaly that can be ignored for all intents and purposes of this analysis. 

How can I work with a broad diversity of entry types? Can we abstract away and categorize entry types into ones that affect holdings, cash-flow, and income or some combination of the three?

Because these entry names won't be consistent, how can I also allow the user to categorize their unique entry names (or different cases) to what the basic operation needs to be taken while preparing the trade log or performing functions with this log?
"""
