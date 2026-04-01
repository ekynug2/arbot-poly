"""
Execution Engine.
Places and tracks orders via py-clob-client.
Supports paper trading mode for the MVP.
"""

import asyncio
import logging
import uuid
from typing import Optional

from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON
from py_clob_client.clob_types import OrderArgs

from config.settings import Settings
from core.arbitrage import ArbitrageSignal
from core.market_scanner import MarketScanner

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """Manages order placement to Polymarket CLOB."""

    def __init__(self, settings: Settings, scanner: MarketScanner):
        self.settings = settings
        self.scanner = scanner
        self.paper_trading = settings.trade.paper_trading
        
        self.client: Optional[ClobClient] = None
        self._init_client()

    def _init_client(self):
        """Initializes the py-clob-client if in live mode."""
        if self.paper_trading:
            logger.info("Execution Engine initialized in PAPER TRADING mode.")
            return

        if not self.settings.private_key:
            logger.error("No private key configured for live trading mode! Falling back to paper.")
            self.paper_trading = True
            return

        try:
            # Type 0 is EOA Wallet (e.g., MetaMask).
            # If funder_address is provided, use it (for proxy wallets).
            funder = self.settings.funder_address if self.settings.funder_address else None
            
            self.client = ClobClient(
                host=self.settings.polymarket.clob_host,
                chain_id=self.settings.polymarket.chain_id,
                key=self.settings.private_key,
                signature_type=0,  # Ensure this is correct for the user's wallet
                funder=funder
            )
            
            # Derive L2 API credentials
            api_creds = self.client.create_or_derive_api_creds()
            self.client.set_api_creds(api_creds)
            logger.info("Successfully initialized Live Execution Client (py-clob-client).")
        except Exception as e:
            logger.error(f"Failed to init Live Execution Client: {e}. Falling back to paper.")
            self.paper_trading = True

    async def execute_arbitrage(self, signal: ArbitrageSignal) -> bool:
        """Executes a dual-leg arbitrage maneuver."""
        yes_id, no_id = self.scanner.get_current_tokens()
        if not yes_id or not no_id:
            logger.warning("No tokens available for execution.")
            return False

        # In a real bot, calculate shares accurately
        cost_per_share = signal.yes_price + signal.no_price if signal.action == "BUY_BOTH" else 1.0 # rough approx
        shares_to_trade = int(signal.size_usdc / cost_per_share)

        if shares_to_trade <= 0:
            return False

        logger.info(f"Executing {signal.action}: {shares_to_trade} shares. Edge: {signal.edge:.4f}")

        if self.paper_trading:
            return await self._paper_execute(signal, shares_to_trade, yes_id, no_id)
        else:
            return await self._live_execute(signal, shares_to_trade, yes_id, no_id)

    async def _paper_execute(self, signal: ArbitrageSignal, shares: int, yes_id: str, no_id: str) -> bool:
        """Simulates placing and filling orders."""
        trade_id = str(uuid.uuid4())[:8]
        action_str = "BUY" if signal.action == "BUY_BOTH" else "SELL"
        logger.info(f"[PAPER-{trade_id}] Placing Limit {action_str} for YES ({yes_id}) at {signal.yes_price}")
        logger.info(f"[PAPER-{trade_id}] Placing Limit {action_str} for NO ({no_id}) at {signal.no_price}")
        
        await asyncio.sleep(0.5)  # Simulate network latency
        
        logger.info(f"[PAPER-{trade_id}] ✓ YES leg filled.")
        logger.info(f"[PAPER-{trade_id}] ✓ NO leg filled.")
        logger.info(f"[PAPER-{trade_id}] ✅ Arbitrage successful. Simulated Profit booked.")
        return True

    async def _live_execute(self, signal: ArbitrageSignal, shares: int, yes_id: str, no_id: str) -> bool:
        """Places live limit orders concurrently."""
        
        side = "BUY" if signal.action == "BUY_BOTH" else "SELL"
        
        # 1. Create orders locally
        try:
            yes_order_args = OrderArgs(
                price=signal.yes_price,
                size=shares,
                side=side,
                token_id=yes_id
            )
            yes_order = self.client.create_order(yes_order_args)
            
            no_order_args = OrderArgs(
                price=signal.no_price,
                size=shares,
                side=side,
                token_id=no_id
            )
            no_order = self.client.create_order(no_order_args)
        except Exception as e:
            logger.error(f"Failed to create live orders: {e}")
            return False

        # 2. Fire concurrently
        trade_id = str(uuid.uuid4())[:8]
        logger.info(f"[{trade_id}] Firing concurrent {side} orders...")
        
        async def post_order_async(order):
            # ClobClient's post_order is synchronous, so we run it in a thread executor
            # to avoid blocking the main async loop.
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self.client.post_order, order)

        try:
            results = await asyncio.gather(
                post_order_async(yes_order),
                post_order_async(no_order),
                return_exceptions=True
            )
            
            # Note: A real bot would need extensive error handling here, including parsing HTTP 
            # Error codes from the API, tracking order IDs for cancellation/hedging, etc.
            
            yes_success = not isinstance(results[0], Exception)
            no_success = not isinstance(results[1], Exception)
            
            if yes_success and no_success:
                logger.info(f"[{trade_id}] ✅ Successfully posted both legs.")
                # We'd then need to poll `client.get_order(order_id)` to ensure it actually filled.
                return True
            else:
                logger.error(f"[{trade_id}] ❌ Failed to post one or both legs. YES: {yes_success}, NO: {no_success}")
                logger.error(f"[{trade_id}] Exceptions: {results}")
                # Trigger hedging if one filled and one didn't.
                return False

        except Exception as e:
            logger.error(f"Error during live execution: {e}")
            return False
