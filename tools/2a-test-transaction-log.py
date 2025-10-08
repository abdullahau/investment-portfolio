import pandas as pd
from src import config

transaction_log = pd.read_csv(config.TRANS_LOG_DIR / "us_mkt_transactions.csv")

# %% Cell 1
# All 'Types'
transaction_log["Type"].unique()

# %% Cell 2
# Holdings
transaction_log.groupby("Symbol").agg("Quantity").sum().round(12)

# %% Cell 3
# High-Yield Cash Sweep
transaction_log[transaction_log["Type"] == "High-Yield Cash Sweep"]["Amount"].sum()

# %% Cell 4
# Stock Spit
transaction_log[transaction_log["Type"] == "Stock Split"]

# %% Cell 5
# Net Deposits
transaction_log[transaction_log["Type"] == "Net Deposit"]

# %% Cell 6
# Net Deposits
transaction_log[transaction_log["Type"] == "Net Dividend"]

# %% Cell 7
transaction_log[transaction_log["Type"] == "Net Dividend"]["Amount"].sum()

# %% Cell 8
# Credit/Margin Interest
transaction_log[transaction_log["Type"] == "Credit/Margin Interest"]["Amount"].sum()
