"""
Market Discovery Engine (Gamma API).
Finds the active BTC 5-minute market and its associated YES/NO token IDs.
"""

import asyncio
import logging
from typing import Dict, Optional, Tuple

import aiohttp

from config.settings import Settings

logger = logging.getLogger(__name__)


class MarketScanner:
    """Scans Polymarket's Gamma API for BTC 5m markets."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.gamma_host = settings.polymarket.gamma_host.rstrip('/')
        
        # Caching
        self.current_market_id: Optional[str] = None
        self.yes_token_id: Optional[str] = None
        self.no_token_id: Optional[str] = None
        self.condition_id: Optional[str] = None

    async def scan_for_active_market(self) -> bool:
        """
        Polls the Gamma API to find the currently active 5m BTC market.
        Returns True if a new market was found and cached.
        """
        endpoint = f"{self.gamma_host}/events"
        params = {
            "active": "true",
            "closed": "false",
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                for offset in range(0, 3000, 500):
                    params["offset"] = str(offset)
                    logger.debug(f"Scanning events at offset {offset}...")
                    async with session.get(endpoint, params=params) as response:
                        if response.status != 200:
                            logger.error(f"Failed to fetch markets: HTTP {response.status}")
                            break
                            
                        data = await response.json()
                        if not data:
                            break  # No more events
                        
                        # Filter for BTC 5m events by slug
                        for event in data:
                            title = event.get("title", "")
                            slug = event.get("slug", "")
                            
                            # Match the current active event slug pattern (e.g., btc-updown-5m-1775034000)
                            if "btc-updown-5m" in slug and event.get("active"):
                                
                                # Polymarket events contain 'markets'
                                markets = event.get("markets", [])
                                if not markets:
                                    continue
                                
                                # Typically the first market in the list is the one we want for single-market events
                                for market in markets:
                                    if market.get("active") and not market.get("closed"):
                                        market_id = market.get("id")
                                        condition_id = market.get("conditionId")
                                        tokens = market.get("clobTokenIds", [])
                                        
                                        if len(tokens) >= 2 and market_id != self.current_market_id:
                                            self.current_market_id = market_id
                                            self.condition_id = condition_id
                                            self.yes_token_id = tokens[0]  # Standard assumption: Index 0 is YES
                                            self.no_token_id = tokens[1]   # Standard assumption: Index 1 is NO
                                            
                                            logger.info(f"New Market Detected: {title}")
                                            logger.info(f"Market ID: {self.current_market_id}")
                                            logger.info(f"YES Token: {self.yes_token_id}")
                                            logger.info(f"NO Token:  {self.no_token_id}")
                                            return True
        except Exception as e:
            logger.error(f"Error scanning markets: {e}", exc_info=True)
            
        return False

    def get_current_tokens(self) -> Tuple[Optional[str], Optional[str]]:
        """Returns (yes_token_id, no_token_id) for the active market."""
        return self.yes_token_id, self.no_token_id

    async def run_scanner_loop(self, scan_interval: int):
        """Continuously scans for the next market."""
        logger.info("Starting market scanner loop...")
        while True:
            await self.scan_for_active_market()
            # The 5m markets change every 5m. Polling every X seconds to catch the flip.
            await asyncio.sleep(scan_interval)
