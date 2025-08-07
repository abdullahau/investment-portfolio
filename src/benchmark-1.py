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
        self.benchmark_symbol = benchmark_symbol
        self.processor = TransactionProcessor(trans_log)
        self.fx_rates = None  # To store fx_rates

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

        self.simulation_df["Open"] = hist["Open"]
        self.simulation_df["Close"] = hist["Close"]
        self.simulation_df["Dividends"] = hist["Dividends"]

        self.simulation_df.loc[hist.index, "Market"] = "Open"
        self.simulation_df["Market"] = self.simulation_df["Market"].fillna("Closed")

        price_cols = ["Open", "Close"]
        self.simulation_df.loc[:, price_cols] = self.simulation_df[price_cols].ffill()
        self.simulation_df.fillna(0, inplace=True)

    def _prepare_cash_flows(self):
        """
        Prepares the NetDeposit series by robustly converting all cash flows
        to the base currency.
        """
        print(
            f"Preparing and converting cash flows to base currency ({config.BASE_CURRENCY})..."
        )
        cash_flow_log = self.processor.get_log_for_action("cash_flow").copy()

        if cash_flow_log.empty:
            self.simulation_df["NetDeposit"] = 0.0
            return

        cash_flow_log["Amount"] = pd.to_numeric(
            cash_flow_log["Amount"], errors="coerce"
        )
        cash_flow_log.dropna(subset=["Amount"], inplace=True)

        non_base_mask = cash_flow_log["Currency"] != config.BASE_CURRENCY
        if non_base_mask.any():
            non_base_currencies = cash_flow_log.loc[non_base_mask, "Currency"].unique()
            currency_pairs = [(c, config.BASE_CURRENCY) for c in non_base_currencies]

            if self.fx_rates is None:
                self.fx_rates = self.data_provider.get_fx_rates(
                    currency_pairs, self.date_range.min(), self.last_market_day
                )

            cash_flow_log["Date_Only"] = cash_flow_log.index.date.astype(
                "datetime64[ns]"
            )

            for currency in non_base_currencies:
                pair = (currency, config.BASE_CURRENCY)
                if pair in self.fx_rates:
                    currency_mask = cash_flow_log["Currency"] == currency
                    rate_map = self.fx_rates[pair].reindex(self.date_range).ffill()
                    conversion_factors = cash_flow_log.loc[
                        currency_mask, "Date_Only"
                    ].map(rate_map)

                    cash_flow_log.loc[currency_mask, "Amount"] = cash_flow_log.loc[
                        currency_mask, "Amount"
                    ].mul(conversion_factors, axis=0)
                else:
                    print(
                        f"⚠️ Warning: FX rate for {pair} not found in benchmark conversion."
                    )

            cash_flow_log.drop(columns=["Date_Only"], inplace=True)

        net_deposits = cash_flow_log.groupby(cash_flow_log.index.date)["Amount"].sum()
        self.simulation_df["NetDeposit"] = net_deposits
        self.simulation_df["NetDeposit"].fillna(0.0, inplace=True)

    def run_simulation(self):
        """
        Runs the day-by-day simulation of the benchmark portfolio. This version
        is refactored to prevent the SettingWithCopyWarning.
        """
        self._prepare_market_data()
        self._prepare_cash_flows()

        # Initialize lists to hold the daily simulation values
        dates = self.simulation_df.index
        num_days = len(dates)

        shares = [0.0] * num_days
        dividend_cash = [0.0] * num_days
        trade_cash = [0.0] * num_days
        commission = [0.0] * num_days
        net_dividend = [0.0] * num_days
        portfolio_value = [0.0] * num_days
        total_value = [0.0] * num_days
        trade_trigger = ["None"] * num_days

        # Handle initial deposit to correctly set up the first trade
        if (
            not self.simulation_df["NetDeposit"].empty
            and self.simulation_df["NetDeposit"].ne(0).any()
        ):
            first_deposit_day = self.simulation_df["NetDeposit"].ne(0).idxmax()
            idx_pos = self.simulation_df.index.get_loc(first_deposit_day)
            initial_deposit = self.simulation_df.loc[first_deposit_day, "NetDeposit"]

            if initial_deposit > 0:
                trade_cash[idx_pos] = initial_deposit
                trade_trigger[idx_pos] = "Buy"

        print("Running benchmark simulation...")
        for i in range(1, num_days):
            # --- Carry forward values from the previous day ---
            shares[i] = shares[i - 1]
            dividend_cash[i] = dividend_cash[i - 1]
            trade_cash[i] = trade_cash[i - 1]
            trade_trigger[i] = trade_trigger[i - 1]

            # --- Process events for today ---
            # Dividends
            if self.simulation_df["Dividends"].iloc[i] > 0 and shares[i - 1] > 0:
                div = (
                    self.simulation_df["Dividends"].iloc[i]
                    * shares[i - 1]
                    * (1 - config.TAX_RATE)
                )
                net_dividend[i] = div
                dividend_cash[i] += div

            # Deposits/Withdrawals
            deposit_amount = self.simulation_df["NetDeposit"].iloc[i]
            if deposit_amount != 0:
                trade_cash[i] += deposit_amount
                trade_trigger[i] = "Buy" if deposit_amount > 0 else "Sell"

            # --- Process Trades ---
            if (
                self.simulation_df["Market"].iloc[i] == "Open"
                and trade_trigger[i] != "None"
            ):
                trigger = trade_trigger[i]
                open_price = self.simulation_df["Open"].iloc[i]

                if trigger == "Buy":
                    cash_to_invest = trade_cash[i] + dividend_cash[i]
                    if cash_to_invest > 1.0 and open_price > 0:
                        net_investment, comm = self._buy_order(cash_to_invest)
                        shares_bought = net_investment / open_price
                        shares[i] += shares_bought
                        commission[i] = comm
                        trade_cash[i] = 0.0
                        dividend_cash[i] = 0.0
                    trade_trigger[i] = "None"

                elif trigger == "Sell":
                    cash_needed = abs(deposit_amount)
                    cash_from_dividends = min(cash_needed, dividend_cash[i])
                    dividend_cash[i] -= cash_from_dividends

                    cash_needed_from_sale = cash_needed - cash_from_dividends
                    if cash_needed_from_sale > 0 and open_price > 0:
                        gross_sale, comm = self._sell_order(cash_needed_from_sale)
                        shares_to_sell = gross_sale / open_price
                        shares_sold = min(shares_to_sell, shares[i])
                        cash_raised = (shares_sold * open_price) - comm
                        trade_cash[i] += cash_raised
                        shares[i] -= shares_sold
                        commission[i] = comm
                    trade_trigger[i] = "None"

            # --- Final Daily Valuation ---
            current_total_cash = trade_cash[i] + dividend_cash[i]
            pv = shares[i] * self.simulation_df["Close"].iloc[i]
            portfolio_value[i] = pv
            total_value[i] = pv + current_total_cash

        # --- Assign all calculated lists to the DataFrame at once ---
        self.simulation_df["Shares"] = shares
        self.simulation_df["DividendCash"] = dividend_cash
        self.simulation_df["TradeCash"] = trade_cash
        self.simulation_df["Commission"] = commission
        self.simulation_df["NetDividend"] = net_dividend
        self.simulation_df["PortfolioValue"] = portfolio_value
        self.simulation_df["TotalValue"] = total_value
        self.simulation_df["TradeTrigger"] = trade_trigger

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
