import argparse
import asyncio
import logging
import sys

from config.settings import load_settings
from core.arbitrage import ArbitrageEngine
from core.execution import ExecutionEngine
from core.market_data import MarketDataClient
from core.market_scanner import MarketScanner
from core.risk import RiskManager
from core.wallet import WalletManager
from utils.logger import configure_logger
from utils.metrics import MetricsTracker
from utils.dashboard import Dashboard
from rich.live import Live

logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(description="Polymarket BTC 5m Arbitrage Bot")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    parser.add_argument("--live", action="store_true", help="Run in live trading mode")
    args = parser.parse_args()

    # 1. Load configuration
    try:
        settings = load_settings(config_path=args.config)
        # Override paper trading if flag is passed
        if args.live:
            settings.trade.paper_trading = False
    except Exception as e:
        print(f"Failed to load configuration: {e}")
        sys.exit(1)

    # 2. Configure logging
    configure_logger(settings)
    mode_str = "LIVE TRADING" if not settings.trade.paper_trading else "PAPER TRADING"
    logger.info(f"🚀 Starting Polymarket Arbitrage Bot in {mode_str} mode")

    # 3. Initialize components
    scanner = MarketScanner(settings)
    ws_client = MarketDataClient(settings, scanner)
    arb_engine = ArbitrageEngine(settings)
    exec_engine = ExecutionEngine(settings, scanner)
    risk_manager = RiskManager(settings)
    wallet_manager = WalletManager(settings)
    metrics = MetricsTracker(settings)
    dashboard = Dashboard(mode_str)

    # Optional: Initial wallet balances
    if wallet_manager.wallet_address and wallet_manager.check_connection():
        usdc_bal = wallet_manager.get_usdc_balance()
        pol_bal = wallet_manager.get_pol_balance()
        dashboard.update_market("Mencari market...")
        dashboard.update_wallet(f"{usdc_bal:.2f} USDC.e | {pol_bal:.4f} POL")
    else:
        dashboard.update_wallet("Offline / Not Connected")

    # 4. Central Callback Loop
    # This function is fired by MarketDataClient every time the top-of-book updates
    async def on_orderbook_update(
        yes_ask_p, yes_bid_p, 
        no_ask_p, no_bid_p, 
        yes_ask_s, yes_bid_s, 
        no_ask_s, no_bid_s
    ):
        # Update Dashboard
        dashboard.update_prices(
            yes_ask_p, yes_bid_p, no_ask_p, no_bid_p,
            yes_ask_s, yes_bid_s, no_ask_s, no_bid_s
        )

        # A. Detect Arbitrage
        signal = arb_engine.evaluate(
            yes_ask_p, yes_bid_p,
            no_ask_p, no_bid_p,
            yes_ask_s, yes_bid_s,
            no_ask_s, no_bid_s
        )

        dashboard.update_signal(signal.action, signal.edge)

        if signal.action != "NONE":
            # Avoid spamming the log for identical opportunities
            # logger.info(f"[{signal.action}] Gross Edge: {signal.edge:.4f} | Max Size: ${signal.size_usdc:.2f}")
            
            yes_id, no_id = scanner.get_current_tokens()
            metrics.log_opportunity(signal, yes_id, no_id)

            # B. Risk Check
            if risk_manager.check_trade_allowed(signal.size_usdc):
                
                # C. Execute Trade
                risk_manager.record_open_position(signal.size_usdc)
                
                try:
                    success = await exec_engine.execute_arbitrage(signal)
                    pnl = signal.size_usdc * signal.edge if success else 0.0
                    metrics.log_trade(signal, success, pnl)
                    
                    if success:
                        risk_manager.record_close_position(signal.size_usdc, pnl)
                        logger.info(f"✅ Trade booked. Estimated PnL: ${pnl:.4f}")
                    else:
                        risk_manager.record_close_position(signal.size_usdc, 0.0)
                        
                except Exception as e:
                    logger.error(f"Execution failed: {e}")
                    risk_manager.record_close_position(signal.size_usdc, 0.0)

    # Register the callback
    ws_client.register_callback(on_orderbook_update)

    # 5. Start main loops concurrently
    # The scanner loop polls Gamma API for the new market every few minutes
    scanner_task = asyncio.create_task(scanner.run_scanner_loop(settings.scanner.scan_interval_sec))
    
    # Initial market discovery spinner
    from rich.console import Console
    console = Console()
    with console.status("[bold green]Mencari market BTC 5-menitan yang aktif...", spinner="dots"):
        while not scanner.current_market_id:
            await asyncio.sleep(1)
        
        # Update dashboard with market info
        dashboard.update_market(scanner.market_title)

    # The WS client loop manages the connection to the CLOB orderbook
    ws_task = asyncio.create_task(ws_client.run())

    async def market_watcher():
        last_yes_id = scanner.get_current_tokens()[0]
        while True:
            await asyncio.sleep(1)
            curr_yes_id = scanner.get_current_tokens()[0]
            if curr_yes_id and curr_yes_id != last_yes_id:
                logger.info("Market rollover detected.")
                dashboard.update_market(scanner.current_market_id or "Mencari...")
                last_yes_id = curr_yes_id
                await ws_client.unsubscribe_and_reconnect()
            
            # Periodically update wallet info too
            if wallet_manager.check_connection():
                usdc = wallet_manager.get_usdc_balance()
                dashboard.update_wallet(f"{usdc:.2f} USDC.e")

    watcher_task = asyncio.create_task(market_watcher())

    try:
        # WRAP GATHER IN LIVE DASHBOARD
        with Live(dashboard.generate(), refresh_per_second=4) as live:
            # Re-update function to keep Live rendering fresh
            async def refresh_ui():
                while True:
                    live.update(dashboard.generate())
                    await asyncio.sleep(0.25)
            
            refresh_task = asyncio.create_task(refresh_ui())
            await asyncio.gather(scanner_task, ws_task, watcher_task, refresh_task)

    except asyncio.CancelledError:
        logger.info("Shutting down bot...")
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
