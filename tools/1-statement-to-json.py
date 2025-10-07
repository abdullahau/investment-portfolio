# tools/statement-to-json.py

import re
import json
import pandas as pd
import pdfplumber
from collections import defaultdict
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
import config


def extract_period_from_text(text):
    """Extracts the statement period (e.g., '2025-June') from the first page text."""
    match = re.search(r"Period:\s+([A-Z]+)\s+-\s+(\d{4})", text)
    if match:
        month = match.group(1).capitalize()
        year = match.group(2)
        return f"{year}-{month}"
    return None


def clean_header(header):
    # Removes \n, trims spaces, and joins words cleanly
    return [col.replace("\n", " ").strip() for col in header]


def process_statement(file_path):
    """
    Parses a single statement PDF, sets correct data types, and extracts the period.
    Returns the period string and a dictionary of DataFrames.
    """
    TABLE_NAMES = ["Holdings", "Income", "Fees", "Transaction", "Deposit & Withdrawals"]
    NUMERIC_COLS = [
        "Net Amt",
        "Amount",
        "Market Price",
        "Market Value",
        "Cost Price",
        "Unrealized",
        "TD Cost Basis",
        "Commission",
        "Price",
        "Quantity",
    ]
    DATE_COLS = ["Trade Date"]  # Add any other date columns here

    data_collector = defaultdict(list)
    current_table_name = None
    statement_period = None

    with pdfplumber.open(file_path) as pdf:
        # Extract period from the first page
        first_page_text = pdf.pages[0].extract_text()
        statement_period = extract_period_from_text(first_page_text)

        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    if not any(cell for cell in row if cell and cell.strip()):
                        continue
                    first_cell = row[0].strip() if row[0] else ""
                    if first_cell in TABLE_NAMES:
                        current_table_name = first_cell
                        continue
                    if current_table_name:
                        if "No record found." in first_cell:
                            current_table_name = None
                            continue
                        data_collector[current_table_name].append(row)

    final_dfs = {}
    for name, rows in data_collector.items():
        if not rows:
            continue
        header = clean_header(rows[0])
        data = [row for row in rows[1:] if row != header]
        if not data:
            continue

        df = pd.DataFrame(data, columns=header)  # pyright: ignore
        df.replace(["-", "--", "$ --", "$--", ""], pd.NA, inplace=True)

        for col in df.columns:
            # Convert numeric columns to float64
            if col in NUMERIC_COLS:
                df[col] = pd.to_numeric(
                    df[col]
                    .astype(str)
                    .str.replace("\n", "", regex=False)
                    .str.replace(" ", "", regex=False)
                    .str.replace("$", "", regex=False)
                    .str.replace(",", "", regex=False)
                    .str.replace("(", "-", regex=False)
                    .str.replace(")", "", regex=False),
                    errors="coerce",
                )

            # Convert date columns to datetime
            elif col in DATE_COLS:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        # All other columns remain as 'object' (string) type by default
        final_dfs[name] = df

    return statement_period, final_dfs


def process_statements(input_folder, output_file):
    """
    Processes all PDF statements in a folder and saves the aggregated data to a single JSON file.
    """
    all_data = {}
    folder_path = Path(input_folder)
    pdf_files = list(folder_path.glob("*.pdf"))

    print(f"Found {len(pdf_files)} PDF files to process...")

    for pdf_file in pdf_files:
        print(f"Processing {pdf_file.name}...")
        period, dfs = process_statement(pdf_file)
        if period:
            # Convert DataFrames to JSON-serializable format (list of dicts)
            # and handle datetime conversion to string format for JSON
            all_data[period] = {
                name: json.loads(df.to_json(orient="records", date_format="iso"))
                for name, df in dfs.items()
            }
        else:
            print(
                f"  - Warning: Could not extract period from {pdf_file.name}. Skipping."
            )

    # Save the master dictionary to a single JSON file
    with open(output_file, "w") as f:
        json.dump(all_data, f, indent=4)

    print(f"\nAll data successfully saved to {output_file}")


if __name__ == "__main__":
    # Process Statements & Store as JSON
    process_statements(
        input_folder=config.RAW_DATA_DIR / "redacted-statements",
        output_file=config.RAW_DATA_DIR / "sarwa_trade.json",
    )

    # # Example Code: Read & Load JSON
    # with open('sarwa_trade.json', 'r') as f:
    #     loaded_data = json.load(f)

    # # Example: Get the Holdings DataFrame for December 2024
    # pd.DataFrame(loaded_data['2024-December']['Holdings'])

    # # Inspect Single Statement Dataframes
    # december2024 = process_statement('tools/raw-data/redacted-statements/December2024.pdf')[1]
    # december2024['Income']
