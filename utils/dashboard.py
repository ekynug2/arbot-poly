"""
Live Dashboard for Polymarket Arbitrage Bot.
Uses Rich to create a dynamic terminal interface.
"""

from datetime import datetime
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.console import Group
from rich.text import Text

class Dashboard:
    def __init__(self, mode: str):
        self.mode = mode
        self.market_title = "Mencari market..."
        self.yes_price = (0.0, 0.0, 0.0, 0.0) # ask, bid, ask_size, bid_size
        self.no_price = (0.0, 0.0, 0.0, 0.0)
        self.edge = 0.0
        self.last_signal = "NONE"
        self.wallet_info = "Loading..."
        self.start_time = datetime.now()
        self.last_update = datetime.now()

    def update_prices(self, yes_ask, yes_bid, no_ask, no_bid, yes_ask_s, yes_bid_s, no_ask_s, no_bid_s):
        self.yes_price = (yes_ask, yes_bid, yes_ask_s, yes_bid_s)
        self.no_price = (no_ask, no_bid, no_ask_s, no_bid_s)
        self.last_update = datetime.now()

    def update_signal(self, action, edge):
        self.last_signal = action
        self.edge = edge

    def update_market(self, title):
        self.market_title = title

    def update_wallet(self, info):
        self.wallet_info = info

    def generate(self) -> Panel:
        # 1. Header Table
        header = Table.grid(expand=True)
        header.add_column(justify="left")
        header.add_column(justify="right")
        
        uptime = str(datetime.now() - self.start_time).split(".")[0]
        mode_color = "green" if self.mode == "PAPER TRADING" else "red"
        
        header.add_row(
            Text.from_markup(f"[bold white]Market:[/bold white] [cyan]{self.market_title}[/cyan]"),
            Text.from_markup(f"[{mode_color}]{self.mode}[/{mode_color}] | Uptime: {uptime}")
        )

        # 2. Price Table
        price_table = Table(show_header=True, header_style="bold magenta", expand=True)
        price_table.add_column("Asset", style="dim")
        price_table.add_column("Best BID", justify="right", style="green")
        price_table.add_column("Size", justify="right", style="dim")
        price_table.add_column("Best ASK", justify="right", style="red")
        price_table.add_column("Size", justify="right", style="dim")

        ya, yb, yas, ybs = self.yes_price
        na, nb, nas, nbs = self.no_price

        price_table.add_row("YES (UP)", f"${yb:.3f}", f"{ybs:.0f}", f"${ya:.3f}", f"{yas:.0f}")
        price_table.add_row("NO (DOWN)", f"${nb:.3f}", f"{nbs:.0f}", f"${na:.3f}", f"{nas:.0f}")

        # 3. Status Footer
        footer = Table.grid(expand=True)
        footer.add_column(justify="left")
        footer.add_column(justify="right")
        
        sig_color = "yellow" if self.last_signal != "NONE" else "white"
        footer.add_row(
            Text.from_markup(f"[bold]Signal:[/bold] [{sig_color}]{self.last_signal}[/{sig_color}] | Edge: [bold green]{self.edge*100:.2f}%[/bold green]"),
            Text.from_markup(f"[dim]Wallet:[/dim] {self.wallet_info}")
        )

        # Combine into a Panel
        return Panel(
            Group(header, price_table, footer),
            title="[bold green]Polymarket BTC 5m Arb Bot[/bold green]",
            border_style="bright_blue"
        )
