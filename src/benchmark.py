# src/benchmark.py

import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
import config
from src.market_data import MarketData
from src.transaction_processor import TransactionProcessor


class Benchmark:
    def __init__(
        self,
        trans_log,
        date_range,
        last_market_day,
        benchmark_symbol=config.BENCHMARK_INDEX,
        data_provider=MarketData(),
    ):
        """
        Initializes the Benchmark simulation engine.
        """
        self.trans_log = trans_log
        self.date_range = date_range
        self.last_market_day = last_market_day
        self.data_provider = data_provider
        self.benchmark_symbol = benchmark_symbol  # TODO: Add feature to allow manual/user provided benchmark price data
        self.processor = TransactionProcessor(trans_log)

        self.simulation_df = pd.DataFrame(index=self.date_range)
        print("Benchmark object initialized.")

    def _buy_order(self, cash_to_invest):
        """Calculates buy transaction details based on config fees."""
        if cash_to_invest <= config.FLAT_FEE:
            return 0.0, 0.0

        net_investment = cash_to_invest / (1 + config.RATE)
        if net_investment >= config.FLAT_FEE / config.RATE:
            commission = cash_to_invest - net_investment
        else:
            commission = config.FLAT_FEE
            net_investment = cash_to_invest - commission
        return net_investment, commission

    def _sell_order(self, cash_needed):
        """Calculates sell transaction details based on config fees."""
        if cash_needed <= 0:
            return 0.0, 0.0

        if cash_needed > (config.FLAT_FEE / config.RATE) - config.FLAT_FEE:
            gross_sale = cash_needed / (1 - config.RATE)
            commission = gross_sale - cash_needed
        else:
            commission = config.FLAT_FEE
            gross_sale = cash_needed + commission
        return gross_sale, commission

    def _prepare_market_data(self):
        """
        Fetches and correctly prepares the historical data for the benchmark index.
        """
        print(f"Fetching market data for benchmark: {self.benchmark_symbol}...")
        hist = self.data_provider.get_history(
            self.benchmark_symbol, self.date_range.min(), self.last_market_day
        )

        # Assign historical data, creating NaNs on non-trading days
        self.simulation_df["Open"] = hist["Open"]
        self.simulation_df["Close"] = hist["Close"]
        self.simulation_df["Dividends"] = hist["Dividends"]

        # Mark only actual trading days as 'Open'
        self.simulation_df.loc[hist.index, "Market"] = "Open"
        self.simulation_df["Market"] = self.simulation_df["Market"].fillna("Closed")

        # Forward-fill only the price columns (Price/Volume)
        price_cols = ["Open", "Close"]
        self.simulation_df[price_cols] = self.simulation_df[price_cols].ffill()

        # Fill all remaining NaNs (e.g., for Dividends on non-trading days) with 0 (Events/Income)
        self.simulation_df.fillna(0, inplace=True)

    def _prepare_cash_flows(self):
        """
        Prepares the NetDeposit series by converting all cash flows to the base currency.
        """
        print(
            f"Preparing and converting cash flows to base currency ({config.BASE_CURRENCY})..."
        )
        cash_flow_log = self.processor.get_log_for_action("cash_flow").copy()

        non_base_currencies = (
            cash_flow_log[cash_flow_log["Currency"] != config.BASE_CURRENCY]["Currency"]
            .dropna()
            .unique()
        )

        if len(non_base_currencies) > 0:
            currency_pairs = [
                (currency, config.BASE_CURRENCY) for currency in non_base_currencies
            ]
            fx_rates = self.data_provider.get_fx_rates(
                currency_pairs, self.date_range.min(), self.last_market_day
            )

            for currency in non_base_currencies:
                pair = (currency, config.BASE_CURRENCY)
                if pair in fx_rates:
                    is_currency = cash_flow_log["Currency"] == currency
                    conversion_rates = fx_rates[pair].reindex(
                        cash_flow_log[is_currency].index, method="ffill"
                    )
                    cash_flow_log.loc[is_currency, "Amount"] *= conversion_rates

        net_deposits = cash_flow_log.groupby(cash_flow_log.index)["Amount"].sum()
        self.simulation_df["NetDeposit"] = net_deposits
        self.simulation_df["NetDeposit"] = self.simulation_df["NetDeposit"].fillna(0)

    def run_simulation(self):
        """
        Runs the day-by-day simulation of the benchmark portfolio.
        """
        self._prepare_market_data()
        self._prepare_cash_flows()

        for col in [
            "Shares",
            "DividendCash",
            "TradeCash",
            "Commission",
            "NetDividend",
            "PortfolioValue",
            "TotalValue",
        ]:
            self.simulation_df[col] = 0.0
        self.simulation_df["TradeTrigger"] = "None"

        if (
            not self.simulation_df["NetDeposit"].empty
            and self.simulation_df["NetDeposit"].ne(0).any()
        ):
            initial_deposit_index = self.simulation_df["NetDeposit"].ne(0).idxmax()
            if self.simulation_df.loc[initial_deposit_index, "NetDeposit"] > 0:
                self.simulation_df.loc[initial_deposit_index, "TradeCash"] = (
                    self.simulation_df.loc[initial_deposit_index, "NetDeposit"]
                )
                self.simulation_df.loc[initial_deposit_index, "TradeTrigger"] = "Buy"

        print("Running benchmark simulation...")
        for i in range(1, len(self.simulation_df)):
            today = self.simulation_df.index[i]
            yesterday = self.simulation_df.index[i - 1]

            for col in ["Shares", "DividendCash", "TradeCash", "TradeTrigger"]:
                self.simulation_df.loc[today, col] = self.simulation_df.loc[
                    yesterday, col
                ]

            if (
                self.simulation_df.loc[today, "Dividends"] > 0
                and self.simulation_df.loc[yesterday, "Shares"] > 0
            ):
                net_dividend = (
                    self.simulation_df.loc[today, "Dividends"]
                    * self.simulation_df.loc[yesterday, "Shares"]
                    * (1 - config.TAX_RATE)
                )
                self.simulation_df.loc[today, "NetDividend"] = net_dividend
                self.simulation_df.loc[today, "DividendCash"] += net_dividend

            if self.simulation_df.loc[today, "NetDeposit"] != 0:
                deposit_amount = self.simulation_df.loc[today, "NetDeposit"]
                self.simulation_df.loc[today, "TradeCash"] += deposit_amount
                if deposit_amount > 0:
                    self.simulation_df.loc[today, "TradeTrigger"] = "Buy"
                elif deposit_amount < 0:
                    self.simulation_df.loc[today, "TradeTrigger"] = "Sell"

            if (
                self.simulation_df.loc[today, "Market"] == "Open"
                and self.simulation_df.loc[today, "TradeTrigger"] != "None"
            ):
                trigger = self.simulation_df.loc[today, "TradeTrigger"]
                open_price = self.simulation_df.loc[today, "Open"]

                if trigger == "Buy":
                    cash_to_invest = (
                        self.simulation_df.loc[today, "TradeCash"]
                        + self.simulation_df.loc[today, "DividendCash"]
                    )
                    if cash_to_invest > 1.0 and open_price > 0:
                        net_investment, commission = self._buy_order(cash_to_invest)
                        shares_bought = net_investment / open_price
                        self.simulation_df.loc[today, "Shares"] += shares_bought
                        self.simulation_df.loc[today, "Commission"] = commission
                        self.simulation_df.loc[today, "TradeCash"] = 0.0
                        self.simulation_df.loc[today, "DividendCash"] = 0.0
                    self.simulation_df.loc[today, "TradeTrigger"] = "None"

                elif trigger == "Sell":
                    cash_needed = abs(self.simulation_df.loc[today, "NetDeposit"])
                    cash_from_dividends = min(
                        cash_needed, self.simulation_df.loc[today, "DividendCash"]
                    )
                    self.simulation_df.loc[today, "DividendCash"] -= cash_from_dividends

                    cash_needed_from_sale = cash_needed - cash_from_dividends
                    if cash_needed_from_sale > 0 and open_price > 0:
                        gross_sale, commission = self._sell_order(cash_needed_from_sale)
                        shares_to_sell = gross_sale / open_price
                        shares_sold = min(
                            shares_to_sell, self.simulation_df.loc[today, "Shares"]
                        )
                        cash_raised = (shares_sold * open_price) - commission
                        self.simulation_df.loc[today, "TradeCash"] += cash_raised
                        self.simulation_df.loc[today, "Shares"] -= shares_sold
                        self.simulation_df.loc[today, "Commission"] = commission
                    self.simulation_df.loc[today, "TradeTrigger"] = "None"

            total_cash = (
                self.simulation_df.loc[today, "TradeCash"]
                + self.simulation_df.loc[today, "DividendCash"]
            )
            self.simulation_df.loc[today, "PortfolioValue"] = (
                self.simulation_df.loc[today, "Shares"]
                * self.simulation_df.loc[today, "Close"]
            )
            self.simulation_df.loc[today, "TotalValue"] = (
                self.simulation_df.loc[today, "PortfolioValue"] + total_cash
            )

        print("Benchmark simulation complete.")

    def get_results(self):
        """Returns the completed simulation DataFrame."""
        return self.simulation_df

    def get_income(self):
        """Returns a time series of total income for the benchmark."""
        return self.simulation_df["NetDividend"]

    def get_monthly_income(self):
        """Returns a time series of total monthly income for the benchmark."""
        return self.simulation_df["NetDividend"].resample("ME").sum()
