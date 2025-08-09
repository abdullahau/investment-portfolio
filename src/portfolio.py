# src/portfolio.py

import pandas as pd
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
        for name in [
            "trade",
            "price",
            "raw_splits",
            "holding",
            "value",
            "income",
            "cost_basis",
            "invested_capital",
            "unrealized_gains",
            "realized_gains",
        ]:
            self.holdings[name] = pd.DataFrame(
                0.0, index=self.date_range, columns=self.symbols
            )

    def _prepare_trade_log(self):
        """Populates the trade DataFrame from the transaction log."""
        trade_log = self.processor.get_log_for_action("trade")
        if not trade_log.empty:
            self.holdings["trade"].update(
                trade_log.groupby(["Date", "Symbol"])["Quantity"]
                .sum()
                .unstack(fill_value=0)
            )

    def _fetch_price_data(self):
        """Fetches and prepares price and split data for all symbols."""
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
        symbol_df = self.symbol_manager.get_unified_df()
        non_base_symbols = symbol_df[symbol_df["Currency"] != self.base_currency]

        unique_currencies = non_base_symbols["Currency"].dropna().unique()
        if len(unique_currencies) == 0:
            return

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

    def _get_converted_log(self, action):
        """
        Gets a transaction log for a specific action, computes quantity for
        numerical stability, and converts monetary values to the base currency.
        """
        log = self.processor.get_log_for_action(action).copy()

        if action == "trade":
            price_is_valid = (log["Price"].notna()) & (log["Price"] > 1e-16)
            buys = price_is_valid & (log["Amount"] < 0)
            log.loc[buys, "Quantity"] = abs(log.loc[buys, "Amount"]) / log.loc[buys, "Price"]
            sells = price_is_valid & (log["Amount"] > 0)
            log.loc[sells, "Quantity"] = -abs(log.loc[sells, "Amount"]) / log.loc[sells, "Price"]

        if "Trading Cost" not in log.columns:
            log["Trading Cost"] = 0.0
        log["Trading Cost"] = log["Trading Cost"].fillna(0.0)

        non_base_currencies = (
            log[log["Currency"] != self.base_currency]["Currency"].dropna().unique()
        )

        if len(non_base_currencies) > 0:
            currency_pairs = [
                (currency, self.base_currency) for currency in non_base_currencies
            ]
            fx_rates = self.data_provider.get_fx_rates(
                currency_pairs, self.date_range.min(), self.last_market_day
            )

            for currency in non_base_currencies:
                pair = (currency, self.base_currency)
                if pair in fx_rates:
                    is_currency = log["Currency"] == currency
                    conversion_rates = fx_rates[pair].reindex(
                        log[is_currency].index, method="ffill"
                    )

                    for col in ["Price", "Amount", "Trading Cost"]:
                        if col in log.columns:
                            log.loc[is_currency, col] *= conversion_rates
        return log

    def _calculate_income(self):
        """Calculates and aggregates all income transactions from the log."""
        income_log = self._get_converted_log("income")
        if not income_log.empty:
            income_pivot = (
                income_log.groupby([income_log.index, "Symbol"])["Amount"]
                .sum()
                .unstack(fill_value=0)
            )
            self.holdings["income"].update(income_pivot)

    def _cumulative_split_factors(self, split_series: pd.Series) -> pd.Series:
        """Computes cumulative split factors for retroactive holding adjustment."""
        factors = split_series.replace(0, 1)
        cumulative = factors[::-1].ffill().cumprod()[::-1].shift(-1)
        return cumulative.fillna(1.0)

    def _calculate_gains_and_returns(self):
        """Calculates cost basis, invested capital, and gains for each holding."""

        trade_log = self._get_converted_log("trade")

        for symbol in self.symbols:
            purchase_lots = []
            symbol_trades = trade_log[trade_log["Symbol"] == symbol]

            for date in self.date_range:
                if date > self.date_range.min():
                    prev_date = date - pd.Timedelta(days=1)
                    self.holdings["invested_capital"].loc[date, symbol] = self.holdings[
                        "invested_capital"
                    ].loc[prev_date, symbol]
                    self.holdings["realized_gains"].loc[date, symbol] = self.holdings[
                        "realized_gains"
                    ].loc[prev_date, symbol]

                self.holdings["unrealized_gains"].loc[date, symbol] = (
                    self.holdings["unrealized_gains"].loc[
                        date - pd.Timedelta(days=1), symbol
                    ]
                    if date > self.date_range.min()
                    else 0.0
                )

                if date in symbol_trades.index:
                    daily_trades = symbol_trades.loc[[date]]

                    buys_today = daily_trades[daily_trades["Quantity"] > 0]
                    for _, trade in buys_today.iterrows():
                        trading_cost = abs(trade.get("Trading Cost", 0.0))
                        cost_basis = abs(trade["Amount"]) + trading_cost
                        purchase_lots.append(
                            {"qty": trade["Quantity"], "cost": cost_basis}
                        )
                        self.holdings["invested_capital"].loc[date, symbol] += (
                            cost_basis
                        )

                    sells_today = daily_trades[daily_trades["Quantity"] < 0]
                    for _, trade in sells_today.iterrows():
                        qty_to_sell = abs(trade["Quantity"])
                        net_proceeds = trade["Amount"] - abs(
                            trade.get("Trading Cost", 0.0)
                        )

                        cost_of_sale = 0.0
                        remaining_lots = []
                        temp_qty_to_sell = qty_to_sell

                        for lot in purchase_lots:
                            if temp_qty_to_sell < 1e-9:
                                remaining_lots.append(lot)
                                continue

                            sell_from_lot_qty = min(temp_qty_to_sell, lot["qty"])

                            proportion_of_lot = (
                                sell_from_lot_qty / lot["qty"]
                                if lot["qty"] > 1e-9
                                else 0
                            )
                            cost_of_sale += proportion_of_lot * lot["cost"]

                            temp_qty_to_sell -= sell_from_lot_qty

                            remaining_qty = lot["qty"] - sell_from_lot_qty
                            if remaining_qty > 1e-9:
                                remaining_lots.append(
                                    {
                                        "qty": remaining_qty,
                                        "cost": lot["cost"] * (1 - proportion_of_lot),
                                    }
                                )

                        purchase_lots = remaining_lots

                        self.holdings["invested_capital"].loc[date, symbol] -= (
                            cost_of_sale
                        )
                        self.holdings["realized_gains"].loc[date, symbol] += (
                            net_proceeds - cost_of_sale
                        )

                current_holding_qty = self.holdings["holding"].loc[date, symbol]
                if current_holding_qty > 1e-9 and purchase_lots:
                    total_cost_of_holdings = sum(lot["cost"] for lot in purchase_lots)
                    current_market_value = self.holdings["value"].loc[date, symbol]

                    self.holdings["unrealized_gains"].loc[date, symbol] = (
                        current_market_value - total_cost_of_holdings
                    )
                else:
                    self.holdings["unrealized_gains"].loc[date, symbol] = 0.0

    def calculate_holdings_and_value(self):
        """
        Calculates daily holdings and market value for the entire portfolio.
        This is the main calculation engine.
        """
        self._prepare_trade_log()
        self._fetch_price_data()
        self._convert_prices_to_base_currency()
        self._calculate_income()

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

        self._calculate_gains_and_returns()

    def get_return_summary(self):
        """
        Returns a summary DataFrame of the total return contribution for each symbol.
        """
        summary = pd.DataFrame(index=self.symbols)
        summary["Income"] = self.holdings["income"].sum()
        summary["Realized Gains"] = self.holdings["realized_gains"].iloc[-1]
        summary["Unrealized Gains"] = self.holdings["unrealized_gains"].iloc[-1]
        summary["Total Return"] = (
            summary["Income"] + summary["Realized Gains"] + summary["Unrealized Gains"]
        )

        return summary.sort_values(by="Total Return", ascending=False)        

    def get_income(self):
        """Returns a time series of total income for the portfolio."""
        return self.holdings["income"].sum(axis=1)

    def get_monthly_income(self):
        """Returns a time series of total monthly income for the portfolio."""
        return self.holdings["income"].sum(axis=1).resample("ME").sum()

    def get_individual_value_history(self):
        """Returns a DataFrame of the daily market value for each individual holding."""
        return self.holdings["value"]

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

Date, Type, Symbol, Quantity, Price, Amount, Trading Cost, Currency, Description, Exchange, Source

There are quite a few variations we can expect in "Type" of transactions. One this is for sure, this cannot be an empty field.

In my case, for example, I have the following Types: 'Net Deposit', 'buy', 'Net Dividend', 'sell', 'Qualified interest income reallocation for 2023', 'Credit/Margin Interest', 'Merger/Acquisition', 'Stock Split', 'High-Yield Cash Sweep'.

I have a small custom script to clean up data and removing useless entries like warrants and inter-account transfer of funds between equity and crypto.

But generally, I would like to enforce the following for all users:
1) Deposits and withdrawals should be Net deposits. If cash was deposited, ensure it is positive `Amount`. If cash was withdrawn, ensure it is negative `Amount`.
2) All dividend income should be net of taxes.
3)  `Credit/Margin Interest` income should be net of taxes too.
4) `buy`, `sell` should be separated for purchase Amount spent and Trading Cost paid.

Everything else is a bit of an accounting standard employed in the preperation.

My transactions log has two entries for a Stock Split event for any stock that has been split. On the same date there is a negative of quantity and positive of quantity to reflect the update in holdings. While this can be ignored entirely if the symbol has a prop data provider like yfinance or others where `get_history` call will return a price, dividend, and stock split history. But this may not be true for manually entered price histories. 

In my transaction log, I also have two entries of a single symbol of type 'Merger/Acquisition'. This is where the one symbol was acquired so one entry shows a reduction in the quantity of that symbol and another entry showing an inflow of 'Amount'. While this isn't "income", it is capital returned (either with some gain or with some loss), how should this amount be treated? Does it affect how we simulate benchmark? Or should it be ignored in benchmark simulation? How do we show gains and losses?

'High-Yield Cash Sweep' entries are just inflows and outflows of funds from cash account to a FIDIC insured cash pool.

'Qualified interest income reallocation for 2023' is just an accounting anomaly that can be ignored for all intents and purposes of this analysis. 

How can I work with a broad diversity of entry types? Can we abstract away and categorize entry types into ones that affect holdings, cash-flow, and income or some combination of the three?

Because these entry names won't be consistent, how can I also allow the user to categorize their unique entry names (or different cases) to what the basic operation needs to be taken while preparing the trade log or performing functions with this log?
"""
