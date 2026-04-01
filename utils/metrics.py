"""
Metrics logging.
Appends trade results and opportunities to a JSON Lines file.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from config.settings import Settings

logger = logging.getLogger(__name__)


class MetricsTracker:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.file_path = Path(settings.logging.trades_file)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Internal counters
        self.total_opportunities = 0
        self.total_trades = 0
        self.successful_trades = 0

    def log_opportunity(self, signal, yes_id: str, no_id: str):
        """Log a detected arbitrage opportunity."""
        self.total_opportunities += 1
        
        record = {
            "type": "opportunity",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": signal.action,
            "edge": signal.edge,
            "target_size_usdc": signal.size_usdc,
            "yes_token": yes_id,
            "no_token": no_id,
            "yes_price": signal.yes_price,
            "no_price": signal.no_price,
            "yes_liquidity": signal.yes_size_avail,
            "no_liquidity": signal.no_size_avail,
        }
        self._append(record)

    def log_trade(self, signal, success: bool, pnl: float = 0.0):
        """Log a trade attempt result."""
        self.total_trades += 1
        if success:
            self.successful_trades += 1
            
        record = {
            "type": "trade",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": signal.action,
            "success": success,
            "simulated_pnl": pnl if success else 0.0,
        }
        self._append(record)

    def _append(self, record: dict):
        """Append JSON record to file."""
        try:
            with open(self.file_path, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            logger.error(f"Failed to log metric: {e}")
