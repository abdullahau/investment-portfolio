# tools/create-transaction-log.py

import json
import os
import pandas as pd
import numpy as np

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import config

def create_master_log(json_path, crypto_path, interim_path, output_path):
    """
    Consolidates data from the brokerage JSON, crypto CSV, and interim CSV
    into a single, clean master transaction log with currency information.
    """
    all_transactions = []

    # 1. Process data from brokerage_data.json
    with open(json_path, "r") as f:
        brokerage_data = json.load(f)

    mappings = {
        "Transaction": {
            "Date": "Trade Date",
            "Symbol": "Symbol",
            "Quantity": "Quantity",
            "Amount": "Amount",
            "Commission": "Commission",
            "Description": "Entry Type",
            "Type": "Side",
            "Price": "Price",
        },
        "Income": {
            "Date": "Trade Date",
            "Symbol": "Symbol",
            "Amount": "Net Amt",
            "Description": "Description",
            "Type": "Entry Type",
        },
        "Fees": {
            "Date": "Trade Date",
            "Amount": "Net Amt",
            "Description": "Description",
            "Type": "Description",
        },
        "Deposit & Withdrawals": {
            "Date": "Trade Date",
            "Amount": "Net Amt",
            "Description": "Description",
            "Type": "Entry Type",
        },
    }

    for period, data in brokerage_data.items():
        for section, mapping in mappings.items():
            if section in data:
                for record in data[section]:
                    type_val = record.get(mapping.get("Type")) or record.get(
                        mapping.get("Description")
                    )

                    if record.get("Entry Type") == "Journal Entry(Cash)":
                        type_val = "Net Deposit"

                    tx = {
                        "Date": pd.to_datetime(record.get(mapping.get("Date"))),
                        "Symbol": record.get(mapping.get("Symbol")),
                        "Quantity": record.get(mapping.get("Quantity")),
                        "Price": record.get(mapping.get("Price")),
                        "Amount": record.get(mapping.get("Amount")),
                        "Commission": record.get(mapping.get("Commission")),
                        "Description": record.get(mapping.get("Description")),
                        "Type": type_val,
                        "Currency": "USD",
                        "Source": "Sarwa Trade",
                    }
                    all_transactions.append(tx)

    # 2. Process data from crypto_transactions.csv
    if os.path.exists(crypto_path):
        crypto_df = pd.read_csv(crypto_path)
        crypto_df["Date"] = pd.to_datetime(crypto_df["Trade Date"])
        for _, row in crypto_df.iterrows():
            tx = {
                "Date": row["Date"],
                "Symbol": row["Crypto"],
                "Quantity": row["Quantity"],
                "Amount": row["Amount"],
                "Type": row["Type"],
                "Currency": "USD",
                "Source": "Sarwa Crypto",
            }
            all_transactions.append(tx)

    # 3. Process data from interim_transactions.csv
    if os.path.exists(interim_path):
        interim_df = pd.read_csv(interim_path)
        interim_df["Date"] = pd.to_datetime(interim_df["Date"])
        for _, row in interim_df.iterrows():
            tx = {
                "Date": row["Date"],
                "Type": row["Type"],
                "Symbol": row["Symbol"],
                "Quantity": row["Quantity"],
                "Amount": row["Amount"],
                "Commission": row["Commission"],
                "Description": row["Description"],
                "Currency": "USD",
                "Source": "Sarwa Trade - Interim",
            }
            all_transactions.append(tx)

    master_log = pd.DataFrame(all_transactions)
    
    # Ensure all numerical columns are consistently typed as float64
    numerical_cols = ['Quantity', 'Price', 'Amount', 'Commission']
    for col in numerical_cols:
        if col in master_log.columns:
            master_log[col] = pd.to_numeric(master_log[col], errors='coerce')
            master_log[col] = master_log[col].astype('float64')
    
    master_log.sort_values(by="Date", inplace=True, ignore_index=True)

    # 4. Apply Cleaning Rules and Caveats
    master_log = master_log[
        ~master_log["Description"].str.contains("Deposit to Alpaca Crypto", na=False)
    ]
    master_log = master_log[master_log["Symbol"] != "219RGT073"]

    master_log["Price"] = np.where(
        pd.isnull(master_log["Price"]),
        (master_log["Amount"].abs() / master_log["Quantity"].abs()).where(
            master_log["Quantity"] != 0
        ),
        master_log["Price"],
    )

    final_cols = [
        "Date",
        "Type",
        "Symbol",
        "Quantity",
        "Price",
        "Amount",
        "Commission",
        "Currency",
        "Description",
        "Source",
    ]
    master_log = master_log[final_cols]

    # 5. Aggregate dividend-related transactions
    types_to_combine = ["Dividends", "Div. Adj(NRA Withheld)"]
    div_rows = master_log[master_log["Type"].isin(types_to_combine)].copy()
    other_rows = master_log[~master_log["Type"].isin(types_to_combine)]
    div_rows_sorted = div_rows.sort_values(by="Type", ascending=False)
    group_keys = ["Date", "Symbol"]
    agg_rules = {
        col: "first" for col in div_rows_sorted.columns if col not in group_keys
    }
    agg_rules["Amount"] = "sum"
    aggregated_divs = div_rows_sorted.groupby(group_keys, as_index=False).agg(agg_rules)
    aggregated_divs["Amount"] = aggregated_divs["Amount"].round(12) # Numerical stability
    aggregated_divs["Type"] = "Net Dividend"

    master_log = (
        pd.concat([other_rows, aggregated_divs], ignore_index=True)
        .sort_values(by="Date")
        .reset_index(drop=True)
    )

    # 5. Save the final log
    master_log.to_csv(output_path, index=False)
    return master_log


if __name__ == "__main__":
    create_master_log(
        json_path=config.RAW_DATA_DIR / "brokerage_data.json",
        crypto_path=config.RAW_DATA_DIR / "crypto_transactions.csv",
        interim_path=config.RAW_DATA_DIR / "interim_transactions.csv",
        output_path=config.INPUT_DATA_DIR / "us_mkt_transactions.csv",
    )
