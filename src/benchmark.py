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
    def __init__(self, trans_log, date_range, last_market_day, data_provider=MarketData()):
        """
        Initializes the Benchmark simulation engine.
        """
        self.trans_log = trans_log
        self.date_range = date_range
        self.last_market_day = last_market_day
        self.data_provider = data_provider
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
        """Fetches and prepares the historical data for the benchmark index."""
        print(f"Fetching market data for benchmark: {config.BENCHMARK_INDEX}...")
        hist = self.data_provider.get_history(
            config.BENCHMARK_INDEX, self.date_range.min(), self.last_market_day
        )
        
        self.simulation_df['Open'] = hist['Open']
        self.simulation_df['Close'] = hist['Close']
        self.simulation_df['Dividends'] = hist['Dividends']
        
        # Mark trading days and forward-fill price data
        self.simulation_df['Market'] = 'Open'
        self.simulation_df.fillna(value={'Market': 'Closed'}, inplace=True)
        self.simulation_df.ffill(inplace=True)
        self.simulation_df.fillna(0, inplace=True)

    def run_simulation(self):
        """
        Runs the day-by-day simulation of the benchmark portfolio.
        This is the main calculation engine for the benchmark.
        """
        self._prepare_market_data()
        
        # Get all cash flow transactions from the log
        cash_flow_log = self.processor.get_log_for_action('cash_flow')
        self.simulation_df['NetDeposit'] = cash_flow_log.groupby('Date')['Amount'].sum()
        self.simulation_df['NetDeposit'].fillna(0, inplace=True)

        # Initialize tracking columns
        for col in ['Shares', 'DividendCash', 'TradeCash', 'Commission', 'NetDividend', 'PortfolioValue', 'TotalValue']:
            self.simulation_df[col] = 0.0
        self.simulation_df['TradeTrigger'] = 'None'

        # Set initial deposit
        initial_deposit_index = self.simulation_df['NetDeposit'].ne(0).idxmax()
        if self.simulation_df.loc[initial_deposit_index, 'NetDeposit'] > 0:
            self.simulation_df.loc[initial_deposit_index, 'TradeCash'] = self.simulation_df.loc[initial_deposit_index, 'NetDeposit']
            self.simulation_df.loc[initial_deposit_index, 'TradeTrigger'] = 'Buy'

        print("Running benchmark simulation...")
        # Main simulation loop
        for i in range(1, len(self.simulation_df)):
            today = self.simulation_df.index[i]
            yesterday = self.simulation_df.index[i - 1]

            # Carry over state from the previous day
            for col in ['Shares', 'DividendCash', 'TradeCash', 'TradeTrigger']:
                self.simulation_df.loc[today, col] = self.simulation_df.loc[yesterday, col]
            
            # --- Handle Daily Events ---
            # 1. Accrue dividends
            if self.simulation_df.loc[today, 'Dividends'] > 0 and self.simulation_df.loc[yesterday, 'Shares'] > 0:
                net_dividend = self.simulation_df.loc[today, 'Dividends'] * self.simulation_df.loc[yesterday, 'Shares'] * (1 - config.TAX_RATE)
                self.simulation_df.loc[today, 'NetDividend'] = net_dividend
                self.simulation_df.loc[today, 'DividendCash'] += net_dividend

            # 2. Process new cash flows (deposits/withdrawals)
            if self.simulation_df.loc[today, 'NetDeposit'] != 0:
                deposit_amount = self.simulation_df.loc[today, 'NetDeposit']
                self.simulation_df.loc[today, 'TradeCash'] += deposit_amount
                if deposit_amount > 0:
                    self.simulation_df.loc[today, 'TradeTrigger'] = 'Buy'
                elif deposit_amount < 0:
                    self.simulation_df.loc[today, 'TradeTrigger'] = 'Sell'

            # --- Execute Trades if Triggered on an Open Market Day ---
            if self.simulation_df.loc[today, 'Market'] == 'Open' and self.simulation_df.loc[today, 'TradeTrigger'] != 'None':
                trigger = self.simulation_df.loc[today, 'TradeTrigger']
                open_price = self.simulation_df.loc[today, 'Open']

                if trigger == 'Buy':
                    cash_to_invest = self.simulation_df.loc[today, 'TradeCash'] + self.simulation_df.loc[today, 'DividendCash']
                    if cash_to_invest > 1.0:
                        net_investment, commission = self._buy_order(cash_to_invest)
                        shares_bought = net_investment / open_price
                        
                        self.simulation_df.loc[today, 'Shares'] += shares_bought
                        self.simulation_df.loc[today, 'Commission'] = commission
                        self.simulation_df.loc[today, 'TradeCash'] = 0.0
                        self.simulation_df.loc[today, 'DividendCash'] = 0.0
                    
                    self.simulation_df.loc[today, 'TradeTrigger'] = 'None'

                elif trigger == 'Sell':
                    # A withdrawal is based on the cash needed from that day's transaction
                    cash_needed = abs(self.simulation_df.loc[today, 'NetDeposit'])
                    
                    cash_from_dividends = min(cash_needed, self.simulation_df.loc[today, 'DividendCash'])
                    self.simulation_df.loc[today, 'DividendCash'] -= cash_from_dividends
                    
                    cash_needed_from_sale = cash_needed - cash_from_dividends
                    if cash_needed_from_sale > 0:
                        gross_sale, commission = self._sell_order(cash_needed_from_sale)
                        shares_to_sell = gross_sale / open_price
                        shares_sold = min(shares_to_sell, self.simulation_df.loc[today, 'Shares'])
                        cash_raised = (shares_sold * open_price) - commission
                        
                        self.simulation_df.loc[today, 'TradeCash'] += cash_raised
                        self.simulation_df.loc[today, 'Shares'] -= shares_sold
                        self.simulation_df.loc[today, 'Commission'] = commission
                    
                    self.simulation_df.loc[today, 'TradeTrigger'] = 'None'

            # --- Update Daily Mark-to-Market Value ---
            total_cash = self.simulation_df.loc[today, 'TradeCash'] + self.simulation_df.loc[today, 'DividendCash']
            self.simulation_df.loc[today, 'PortfolioValue'] = self.simulation_df.loc[today, 'Shares'] * self.simulation_df.loc[today, 'Close']
            self.simulation_df.loc[today, 'TotalValue'] = self.simulation_df.loc[today, 'PortfolioValue'] + total_cash
        
        print("Benchmark simulation complete.")
        
    def get_results(self):
        """Returns the completed simulation DataFrame."""
        return self.simulation_df
