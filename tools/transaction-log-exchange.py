import json
import pandas as pd

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import config

def main():
    # 1. Load Sarwa transaction log
    transaction_log = pd.read_csv(config.INPUT_DATA_DIR / "us_mkt_transactions.csv")

    # 2. Load metadata
    with open(config.METADATA_CACHE, "r") as f:
        metadata = json.load(f)

    # 3. Create a simple {symbol: market} mapping dictionary
    market_mapping = {
        symbol: data["Exchange"]
        for symbol, data in metadata.items()
        if "Exchange" in data
    }

    # 4. Use .map() to update the 'Market' column
    transaction_log['Market'] = transaction_log['Symbol'].map(market_mapping).fillna('US Market')

    # 5. Write to us_mkt_transactions.csv
    transaction_log.to_csv(config.INPUT_DATA_DIR / "us_mkt_transactions.csv", index=False)
    
    return transaction_log

if __name__ == "__main__":
    main()