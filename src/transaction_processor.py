import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
import config


class TransactionProcessor:
    def __init__(self, trans_log):
        self.trans_log = trans_log
        self.transaction_map = self._load_transaction_map()

    def _load_transaction_map(self):
        with open(config.TRANSACTION_MAP_FILE, "r") as f:
            return json.load(f)

    def get_log_for_action(self, action):
        """
        Filters the master log for all transaction types that map to a specific action.
        """
        target_types = [
            trans_type
            for trans_type, details in self.transaction_map.items()
            if details.get("action") == action
        ]
        return self.trans_log[self.trans_log["Type"].isin(target_types)]
