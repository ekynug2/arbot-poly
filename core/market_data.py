"""
WebSocket Market Data Client.
Subscribes to the Polymarket orderbook for the active market and maintains state.
"""

import asyncio
import json
import logging
from typing import Callable, Coroutine, Dict, Optional, Tuple

import websockets

from config.settings import Settings
from core.market_scanner import MarketScanner

logger = logging.getLogger(__name__)

# Type alias for the callback (yes_ask, yes_bid, no_ask, no_bid, yes_ask_size, yes_bid_size, no_ask_size, no_bid_size)
OrderbookCallback = Callable[[float, float, float, float, float, float, float, float], Coroutine]


class OrderbookState:
    """Maintains an in-memory limit order book."""
    def __init__(self):
        self.bids: Dict[float, float] = {}  # price -> size
        self.asks: Dict[float, float] = {}  # price -> size

    def update(self, changes: list):
        """Update orderbook from a list of changes (price, size)."""
        for change in changes:
            price, size = float(change["price"]), float(change["size"])
            side = change["side"]
            
            book = self.bids if side == "BUY" else self.asks
            
            if size == 0:
                book.pop(price, None)
            else:
                book[price] = size

    def reset_from_snapshot(self, snapshot: dict):
        """Load full snapshot."""
        self.bids.clear()
        self.asks.clear()
        
        for bid in snapshot.get("bids", []):
            self.bids[float(bid["price"])] = float(bid["size"])
            
        for ask in snapshot.get("asks", []):
            self.asks[float(ask["price"])] = float(ask["size"])

    @property
    def best_bid(self) -> Tuple[float, float]:
        if not self.bids:
            return 0.0, 0.0
        best_price = max(self.bids.keys())
        return best_price, self.bids[best_price]

    @property
    def best_ask(self) -> Tuple[float, float]:
        if not self.asks:
            return 1.0, 0.0  # Max price in prediction markets
        best_price = min(self.asks.keys())
        return best_price, self.asks[best_price]


class MarketDataClient:
    """Connects to Polymarket WS to track YES/NO orderbooks."""

    def __init__(self, settings: Settings, scanner: MarketScanner):
        self.settings = settings
        self.scanner = scanner
        self.ws_url = settings.polymarket.ws_url
        
        self.yes_book = OrderbookState()
        self.no_book = OrderbookState()
        
        self.on_update: Optional[OrderbookCallback] = None
        self._current_ws = None
        self._ping_task = None

    def register_callback(self, callback: OrderbookCallback):
        """Register the arbitrage engine callback."""
        self.on_update = callback

    async def _handle_message(self, message: str):
        """Parse WS message and update book state."""
        try:
            data = json.loads(message)
            
            # WS may send arrays (e.g. initial batch); process each item
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        await self._process_event(item)
                return
            
            if not isinstance(data, dict):
                return
                
            await self._process_event(data)

        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.error(f"Error handling WS message: {e}", exc_info=True)

    async def _process_event(self, data: dict):
        """Process a single WS event dict."""
        event_type = data.get("event_type")
        asset_id = data.get("asset_id")
        
        if not asset_id or not event_type:
            return

        yes_id, no_id = self.scanner.get_current_tokens()
        if asset_id not in (yes_id, no_id):
            return
            
        book = self.yes_book if asset_id == yes_id else self.no_book

        if event_type == "book":
            book.reset_from_snapshot(data)
        elif event_type == "price_change":
            book.update(data.get("changes", []))
        elif event_type == "last_trade_price":
            pass
        
        # Fire callback if registered
        if self.on_update:
            yes_bid_p, yes_bid_s = self.yes_book.best_bid
            yes_ask_p, yes_ask_s = self.yes_book.best_ask
            no_bid_p, no_bid_s = self.no_book.best_bid
            no_ask_p, no_ask_s = self.no_book.best_ask
            
            # Only fire if both books are somewhat populated
            if yes_bid_p > 0 and no_bid_p > 0:
                await self.on_update(
                    yes_ask_p, yes_bid_p, no_ask_p, no_bid_p,
                    yes_ask_s, yes_bid_s, no_ask_s, no_bid_s
                )

    async def _ping_loop(self, ws):
        """Keep-alive ping every 10 seconds."""
        try:
            while True:
                await asyncio.sleep(10)
                if ws and not ws.closed:
                    await ws.send("PING")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"Ping loop error: {e}")

    async def connect_and_listen(self):
        """Connect to Polymarket WS, subscribe to active tokens, and listen."""
        yes_id, no_id = self.scanner.get_current_tokens()
        
        if not yes_id or not no_id:
            logger.warning("No tokens active to subscribe to. Waiting for scanner...")
            return

        logger.info(f"Connecting to WS orderbook for YES:{yes_id} NO:{no_id}")
        
        try:
            async with websockets.connect(self.ws_url, ping_interval=None) as ws:
                self._current_ws = ws
                
                # Subscribe payload
                sub_payload = {
                    "assets_ids": [yes_id, no_id],
                    "type": "market",
                    "custom_feature_enabled": True
                }
                await ws.send(json.dumps(sub_payload))
                
                # Start ping loop
                self._ping_task = asyncio.create_task(self._ping_loop(ws))
                
                # Listen loop
                async for message in ws:
                    # Polymarket WS sends 'PONG' strings back occasionally if we send 'PING'
                    if message == "PONG":
                        continue
                    await self._handle_message(message)
                    
        except websockets.ConnectionClosed:
            logger.warning("WebSocket connection closed.")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            if self._ping_task:
                self._ping_task.cancel()
            self._current_ws = None
            
    async def run(self):
        """Main loop managing connection and reconnects."""
        retry_delay = 1
        
        while True:
            await self.connect_and_listen()
            
            # When WS disconnects, trigger an immediate market rescan
            # (the 5m market may have expired)
            logger.info("WS disconnected. Triggering market rescan...")
            found = await self.scanner.scan_for_active_market()
            if found:
                retry_delay = 1  # Reset backoff on new market
            
            logger.info(f"Reconnecting to WebSocket in {retry_delay}s...")
            await asyncio.sleep(retry_delay)
            
            # Exponential backoff (caps at 10s for fast market rotation)
            retry_delay = min(retry_delay * 2, 10)

    async def unsubscribe_and_reconnect(self):
        """Called when scanner detects a new market and flips tokens."""
        logger.info("Market rollover detected, forcing WS reconnect...")
        if self._current_ws and not self._current_ws.closed:
            await self._current_ws.close()
