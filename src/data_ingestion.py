# src/data_ingestion.py
import pandas as pd
import os


def create_master_log(file_paths):
    """
    Loads and concatenates a list of transaction log CSVs into a single DataFrame.
    """
    log_list = []
    for file_path in file_paths:
        if file_path and os.path.exists(file_path):
            log_list.append(pd.read_csv(file_path, parse_dates=["Date"]))
            print(f"Successfully loaded log: {os.path.basename(file_path)}")

    if not log_list:
        raise FileNotFoundError("No valid transaction logs were found.")

    master_log = pd.concat(log_list).sort_values(by="Date").reset_index(drop=True)
    return master_log
