import requests
import pandas as pd
from src import config


def fetch_data(url):
    try:
        response = requests.get(url)
        response.raise_for_status()

        data = response.json()
        df = pd.DataFrame(data)

        if "DT" in df.columns:
            df.rename(columns={"DT": "Date"}, inplace=True)
            df["Date"] = pd.to_datetime(df["Date"]).dt.date  # ty: ignore
            df = df.set_index("Date")

    except requests.exceptions.RequestException as e:  # ty: ignore
        print(f"An error occurred: {e}")
    except ValueError:
        print("Error: Could not decode JSON from the response.")

    return df  # pyright: ignore


def main():
    trans_log = pd.read_csv(config.RAW_DATA_DIR / "IntlSecurities_transactions.csv")
    symbol_market_pair = trans_log[["Symbol", "Exchange"]].dropna().drop_duplicates()

    session_id = "e23b8b7e-5e52-4ce8-ade6-0c4e3311b720"
    start = "1900-01-31T20:18:48.000Z"
    end = "2100-01-31T20:00:00.000Z"
    interval = "1"  # 1d
    additional_slug = "1753968492999"

    for _, row in symbol_market_pair.iterrows():
        symbol = row["Symbol"]
        exchange = row["Exchange"] if row["Exchange"] == "DFM" else "ADSM"

        # Intl Securities Datafeed API Reference: tools/IntlSecurities-data-scrapping.png
        base_url = "https://mobile.intlsecurities.ae/FITDataFeedServiceGateway/DataFeedService.asmx/datafeedDFN"
        url = f"{base_url}?session={session_id}&symbol={symbol},{exchange}&period=day&from={start}&to={end}&interval={interval}${additional_slug}"
        df = fetch_data(url)
        df.reset_index().to_csv(f"data/manual-source/prices/{symbol}.csv", index=False)


if __name__ == "__main__":
    main()
