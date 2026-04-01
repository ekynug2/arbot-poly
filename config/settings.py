"""
Configuration management — loads config.yaml + .env overrides.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv


# ── Dataclass hierarchy ──────────────────────────────────────────

@dataclass
class PolymarketConfig:
    clob_host: str = "https://clob.polymarket.com"
    gamma_host: str = "https://gamma-api.polymarket.com"
    ws_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    chain_id: int = 137


@dataclass
class TradeConfig:
    paper_trading: bool = True
    max_position_pct: float = 0.02
    min_edge_threshold: float = 0.02
    order_timeout_sec: int = 5
    fallback_to_market_sec: int = 2
    target_size_usdc: float = 10.0


@dataclass
class RiskConfig:
    max_daily_loss: float = 100.0
    max_open_exposure: float = 500.0
    max_position_size: float = 50.0


@dataclass
class ScannerConfig:
    scan_interval_sec: int = 240
    market_keyword: str = "BTC"
    market_type: str = "5m"


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: str = "logs/arbot.log"
    trades_file: str = "logs/trades.jsonl"
    max_log_size_mb: int = 50
    backup_count: int = 5


@dataclass
class Settings:
    """Top-level settings container assembling all sub-configs."""

    # Secrets (from .env only — NEVER from yaml)
    private_key: str = ""
    rpc_url: str = ""
    funder_address: str = ""

    # Sub-configs
    polymarket: PolymarketConfig = field(default_factory=PolymarketConfig)
    trade: TradeConfig = field(default_factory=TradeConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    scanner: ScannerConfig = field(default_factory=ScannerConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


# ── Loader ────────────────────────────────────────────────────────

def _merge_section(dc_instance, yaml_dict: dict):
    """Overwrite dataclass fields from a flat dict (one level)."""
    if not yaml_dict:
        return
    for key, value in yaml_dict.items():
        if hasattr(dc_instance, key):
            expected_type = type(getattr(dc_instance, key))
            try:
                setattr(dc_instance, key, expected_type(value))
            except (ValueError, TypeError):
                setattr(dc_instance, key, value)


def load_settings(
    config_path: str = "config.yaml",
    env_path: str = ".env",
) -> Settings:
    """
    Build a Settings object by:
      1. Starting with dataclass defaults
      2. Overlaying values from config.yaml
      3. Injecting secrets from .env
    """
    settings = Settings()

    # ── 1. Load yaml ──────────────────────────────────────────
    cfg_file = Path(config_path)
    if cfg_file.exists():
        with open(cfg_file) as f:
            raw = yaml.safe_load(f) or {}

        _merge_section(settings.polymarket, raw.get("polymarket"))
        _merge_section(settings.trade, raw.get("trade"))
        _merge_section(settings.risk, raw.get("risk"))
        _merge_section(settings.scanner, raw.get("scanner"))
        _merge_section(settings.logging, raw.get("logging"))

    # ── 2. Load .env secrets ──────────────────────────────────
    env_file = Path(env_path)
    if env_file.exists():
        load_dotenv(env_file)

    settings.private_key = os.getenv("PRIVATE_KEY", "")
    settings.rpc_url = os.getenv("RPC_URL", "")
    settings.funder_address = os.getenv("FUNDER_ADDRESS", "")

    return settings
