"""
Wallet & Web3 Integration.
Handles checking USDC.e balances on Polygon and token approvals.
"""

import logging

from web3 import Web3

from config.settings import Settings

logger = logging.getLogger(__name__)

# Standard ERC20 ABI (Minimal mapping to check balances and approvals)
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
        "stateMutability": "view",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
        "stateMutability": "view",
    }
]

# Polygon USDC (Bridged)
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"


class WalletManager:
    """Manages the wallet balance and allowances on Polygon network."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.w3 = Web3(Web3.HTTPProvider(settings.rpc_url))
        
        self.wallet_address = None
        if self.settings.funder_address:
            self.wallet_address = self.settings.funder_address
        else:
            # We would derive this from the private key if needed, or ask user
            pass

    def check_connection(self) -> bool:
        """Ping QuickNode/RPC to ensure web3 connection is healthy."""
        return self.w3.is_connected()

    def get_usdc_balance(self) -> float:
        """Returns the USDC.e balance formatted in human-readable notation."""
        if not self.wallet_address:
            return 0.0
            
        try:
            checksum_addr = self.w3.to_checksum_address(self.wallet_address)
            usdc_contract = self.w3.eth.contract(
                address=self.w3.to_checksum_address(USDC_ADDRESS),
                abi=ERC20_ABI
            )
            
            raw_balance = usdc_contract.functions.balanceOf(checksum_addr).call()
            # USDC has 6 decimal places typically
            return float(raw_balance) / (10**6)
        except Exception as e:
            logger.error(f"Failed to fetch USDC balance: {e}")
            return 0.0

    def get_pol_balance(self) -> float:
        """Returns native POL (MATIC) balance for gas fees."""
        if not self.wallet_address:
            return 0.0
            
        try:
            checksum_addr = self.w3.to_checksum_address(self.wallet_address)
            raw_balance = self.w3.eth.get_balance(checksum_addr)
            return float(self.w3.from_wei(raw_balance, "ether"))
        except Exception as e:
            logger.error(f"Failed to fetch POL balance: {e}")
            return 0.0
