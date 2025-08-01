# src/benchmark.py

import pandas as pd
import numpy as np

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import config
from src import data_providers

class Benchmark:
    pass

# --- Fee Calculation Logic ---
def buy_order(cash_to_invest, FLAT_FEE=config.FLAT_FEE, RATE=config.RATE):
    if cash_to_invest <= FLAT_FEE:
        return 0.0, 0.0

    net_investment = cash_to_invest / (1 + RATE)

    if net_investment >= FLAT_FEE / RATE:
        commission = cash_to_invest - net_investment
    else:
        commission = FLAT_FEE
        net_investment = cash_to_invest - commission

    return net_investment, commission


def sell_order(cash_needed, FLAT_FEE=config.FLAT_FEE, RATE=config.RATE):
    if cash_needed <= 0:
        return 0.0, 0.0

    if cash_needed > (FLAT_FEE / RATE) - FLAT_FEE:
        gross_sale = cash_needed / (1 - RATE)
        commission = gross_sale - cash_needed
    else:
        commission = FLAT_FEE
        gross_sale = cash_needed + commission

    return gross_sale, commission


# --- Main Simulation and Analysis Functions ---


def run_benchmark_simulation(benchmark_df, master_log):
    # ...your main benchmark loop that calls buy_order() and sell_order()...
    # return benchmark_df
    pass


def calculate_holdings(trade_log, split_data):
    # ...your main holdings calculation loop...
    # return holdings_df
    pass
