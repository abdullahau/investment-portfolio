import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
import config

print()
print(config.RAW_DATA_DIR)
print(config.DATA_DIR)
print(config.ROOT_DIR)
print(config.API_KEY_TWELVE_DATA)
print(config.ACCOUNT_NUM)