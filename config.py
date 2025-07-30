# config.py

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv() # Reads the .env file

# --- API Keys & Secrets ---
API_KEY_TWELVE_DATA = os.getenv("TWELVE_DATA_API_KEY")
ACCOUNT_NUM = os.getenv("ACCOUNT_NUM")
ACCOUNT_NAME = os.getenv("ACCOUNT_NAME")

# --- Path Management ---
# Absolute path to the project's root directory
ROOT_DIR = Path(__file__).resolve().parent
# Important directories relative to the root
SRC_DIR = ROOT_DIR / "src"
DATA_DIR = ROOT_DIR / "data"
INPUT_DATA_DIR = DATA_DIR / "input"
TOOLS_DIR = ROOT_DIR / "tools"
DOCS_DIR = ROOT_DIR / "docs"
NOTEBOOKS_DIR = ROOT_DIR / "notebooks"
RAW_DATA_DIR = TOOLS_DIR / "raw-data"