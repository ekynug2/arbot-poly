"""
Arbitrage Engine.
Detects mispricing between YES and NO tokens based on fee-aware calculations.
"""

import logging
from typing import Dict, Optional, Tuple

from config.settings import Settings

logger = logging.getLogger(__name__)


class ArbitrageSignal:
    def __init__(
        self,
        action: str,  # "BUY_BOTH", "SELL_BOTH", "NONE"
        edge: float,
        size_usdc: float,
        yes_price: float,
        no_price: float,
        yes_size_avail: float,
        no_size_avail: float,
    ):
        self.action = action
        self.edge = edge
        self.size_usdc = size_usdc
        self.yes_price = yes_price
        self.no_price = no_price
        self.yes_size_avail = yes_size_avail
        self.no_size_avail = no_size_avail


class ArbitrageEngine:
    """Calculates fee-adjusted arbitrage edges and emits trade signals."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.target_size = settings.trade.target_size_usdc
        self.min_edge = settings.trade.min_edge_threshold
        
        # In a real bot, we'd fetch this from Gamma API / fee-rate endpoint dynamically
        # Let's assume a default maker fee for calculations (Polymarket generally charges taker fees, maker is 0 or rebate).
        # To be safe for taker/market fallback, we price in a worst-case 200 bps (0.02) fee rate.
        self.assumed_fee_rate_bps = 2.0  # 2.0%

    def _calc_fee(self, price: float, size: float) -> float:
        """
        fee = C * feeRate * p * (1 - p)
        Where C = size in USDC
        """
        fee_rate = self.assumed_fee_rate_bps / 100.0
        return size * fee_rate * price * (1.0 - price)

    def evaluate(
        self,
        yes_ask_p: float, yes_bid_p: float,
        no_ask_p: float, no_bid_p: float,
        yes_ask_s: float, yes_bid_s: float,
        no_ask_s: float, no_bid_s: float
    ) -> ArbitrageSignal:
        """
        Evaluate current orderbook top-of-book for arbitrage opportunities.
        Returns an ArbitrageSignal object.
        """
        
        # --- 1. Evaluate BUY BOTH ---
        # If we buy YES at ask and buy NO at ask
        cost_to_buy = yes_ask_p + no_ask_p
        
        if cost_to_buy < 1.0:
            # We have gross edge
            gross_edge = 1.0 - cost_to_buy
            
            # Max available size is constrained by the thinner side of the book
            # Size in shares is: available USDC / price
            yes_shares_avail = yes_ask_s
            no_shares_avail = no_ask_s
            
            # To be perfectly hedged, we must buy an equal number of shares for YES and NO
            # So the MAX shares we can buy is the minimum of shares available on both sides
            max_shares = min(yes_shares_avail, no_shares_avail)
            
            # Let's scale down to our target USDC size roughly
            target_shares = min(max_shares, self.target_size / cost_to_buy)
            
            total_cost_usdc = target_shares * cost_to_buy
            
            fee_yes = self._calc_fee(yes_ask_p, target_shares)
            fee_no = self._calc_fee(no_ask_p, target_shares)
            
            net_edge = gross_edge - ((fee_yes + fee_no) / target_shares)
            
            if net_edge >= self.min_edge:
                return ArbitrageSignal(
                    "BUY_BOTH", net_edge, total_cost_usdc,
                    yes_ask_p, no_ask_p, yes_shares_avail, no_shares_avail
                )
                
        # --- 2. Evaluate SELL BOTH ---
        # If we sell YES at bid and sell NO at bid
        revenue_from_sell = yes_bid_p + no_bid_p
        
        if revenue_from_sell > 1.0:
            gross_edge = revenue_from_sell - 1.0
            
            yes_shares_avail = yes_bid_s
            no_shares_avail = no_bid_s
            
            max_shares = min(yes_shares_avail, no_shares_avail)
            target_shares = min(max_shares, self.target_size / revenue_from_sell)
            
            total_rev_usdc = target_shares * revenue_from_sell
            
            fee_yes = self._calc_fee(yes_bid_p, target_shares)
            fee_no = self._calc_fee(no_bid_p, target_shares)
            
            net_edge = gross_edge - ((fee_yes + fee_no) / target_shares)
            
            if net_edge >= self.min_edge:
                return ArbitrageSignal(
                    "SELL_BOTH", net_edge, total_rev_usdc,
                    yes_bid_p, no_bid_p, yes_shares_avail, no_shares_avail
                )
                
        # No opportunity
        return ArbitrageSignal("NONE", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
