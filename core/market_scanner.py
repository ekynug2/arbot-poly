"""
Market Discovery Engine (Gamma API).
Finds the active BTC 5-minute market and its associated YES/NO token IDs.
Uses direct slug calculation based on Unix timestamps for instant discovery.
"""

import asyncio
import json
import logging
import time
from typing import Optional, Tuple

import aiohttp

from config.settings import Settings

logger = logging.getLogger(__name__)


class MarketScanner:
    """Scans Polymarket's Gamma API for BTC 5m markets."""

    WINDOW_SEC = 300  # 5-minute windows

    def __init__(self, settings: Settings):
        self.settings = settings
        self.gamma_host = settings.polymarket.gamma_host.rstrip('/')
        
        # Caching
        self.current_market_id: Optional[str] = None
        self.yes_token_id: Optional[str] = None
        self.no_token_id: Optional[str] = None
        self.condition_id: Optional[str] = None

    def _build_slugs(self) -> list:
        """
        Build candidate slugs based on the current time.
        Checks previous, current, and next 5-minute windows.
        """
        now = int(time.time())
        window_start = now - (now % self.WINDOW_SEC)
        
        # Prioritize: next window first, then current, then previous
        # This avoids connecting to a market that is about to expire
        timestamps = [
            window_start + self.WINDOW_SEC,   # next (upcoming)
            window_start,                     # current
            window_start - self.WINDOW_SEC,   # previous (fallback)
        ]
        return [f"btc-updown-5m-{ts}" for ts in timestamps]

    async def scan_for_active_market(self) -> bool:
        """
        Polls the Gamma API to find the currently active 5m BTC market.
        Uses direct slug lookup for instant discovery.
        Returns True if a new market was found and cached.
        """
        slugs = self._build_slugs()
        
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                for slug in slugs:
                    endpoint = f"{self.gamma_host}/events"
                    params = {"slug": slug}
                    
                    async with session.get(endpoint, params=params) as response:
                        if response.status != 200:
                            logger.warning(f"Gamma API returned HTTP {response.status} for slug {slug}")
                            continue
                            
                        data = await response.json()
                        if not data:
                            continue
                        
                        event = data[0]
                        title = event.get("title", "")
                        
                        if not event.get("active"):
                            continue
                        
                        markets = event.get("markets", [])
                        if not markets:
                            continue
                        
                        for market in markets:
                            if market.get("active") and not market.get("closed"):
                                market_id = market.get("id")
                                condition_id = market.get("conditionId")
                                tokens_raw = market.get("clobTokenIds", [])
                                # API may return clobTokenIds as a JSON string
                                if isinstance(tokens_raw, str):
                                    tokens = json.loads(tokens_raw)
                                else:
                                    tokens = tokens_raw
                                
                                if len(tokens) >= 2 and market_id != self.current_market_id:
                                    self.current_market_id = market_id
                                    self.condition_id = condition_id
                                    self.yes_token_id = tokens[0]
                                    self.no_token_id = tokens[1]
                                    
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
            found = await self.scan_for_active_market()
            if found:
                logger.info(f"Next scan in {scan_interval}s...")
            await asyncio.sleep(scan_interval)
