"""
Risk Management Engine.
Enforces limits on exposure, daily loss, and individual trade sizes.
"""

import logging

from config.settings import Settings

logger = logging.getLogger(__name__)


class RiskManager:
    """Tracks exposure and gross PnL, enforcing configured limits."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.max_daily_loss = settings.risk.max_daily_loss
        self.max_exposure = settings.risk.max_open_exposure
        self.max_trade_size = settings.risk.max_position_size
        
        self.current_exposure = 0.0
        self.daily_pnl = 0.0

    def check_trade_allowed(self, proposed_size_usdc: float) -> bool:
        """
        Validates if a proposed trade size is allowed based on:
        1. Max individual trade size limit
        2. Max total open exposure limit
        3. Max daily loss limit
        """
        if proposed_size_usdc > self.max_trade_size:
            logger.warning(
                f"Risk Reject: Proposed size {proposed_size_usdc:.2f} > max_pos_size ({self.max_trade_size:.2f})"
            )
            return False

        if (self.current_exposure + proposed_size_usdc) > self.max_exposure:
            logger.warning(
                f"Risk Reject: Exposure {self.current_exposure:.2f} + {proposed_size_usdc:.2f} > max_exposure ({self.max_exposure:.2f})"
            )
            return False

        if getattr(self, "daily_pnl", 0.0) <= -self.max_daily_loss:
            logger.warning(
                f"Risk Reject: Daily loss limit hit. PnL: {self.daily_pnl:.2f} <= max_daily_loss (-{self.max_daily_loss:.2f})"
            )
            return False

        return True

    def record_open_position(self, size_usdc: float):
        """Update open exposure."""
        self.current_exposure += size_usdc

    def record_close_position(self, size_usdc: float, pnl: float):
        """Decrease exposure and update daily PnL."""
        self.current_exposure -= size_usdc
        self.daily_pnl += pnl
        
        # Prevent floating point precision errors
        if self.current_exposure < 0.001:
            self.current_exposure = 0.0

    def check_partial_fill(self, yes_filled: float, no_filled: float) -> str:
        """
        In Polymarket, if you buy YES and NO but they fill at different sizes,
        you are exposed directionally. We must hedge by market-buying the missing leg.
        """
        diff = abs(yes_filled - no_filled)
        
        # If difference is negligible (e.g. less than 1 share), we are approx neutral
        if diff < 1.0:
            return "NEUTRAL"
            
        if yes_filled > no_filled:
            logger.warning(f"PARTIAL FILL: Long YES by {diff} shares. Must hedge NO.")
            return "HEDGE_NO"
        else:
            logger.warning(f"PARTIAL FILL: Long NO by {diff} shares. Must hedge YES.")
            return "HEDGE_YES"
