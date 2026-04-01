# Product Requirements Document (PRD)
## Polymarket BTC 5m Arbitrage Trading Bot

---

## 1. Overview

Build an automated arbitrage trading bot for Polymarket 5-minute BTC Up/Down markets.

Target market example:
https://polymarket.com/event/btc-updown-5m-1774434300

The bot must:
- Detect arbitrage opportunities in real-time
- Execute trades with minimal latency
- Manage execution risk and capital exposure

---

## 2. Goals

Primary goals:
- Identify mispricing where YES + NO != 1
- Execute arbitrage trades profitably
- Minimize execution risk (partial fill)

Secondary goals:
- Log all trades and opportunities
- Provide metrics for performance evaluation

---

## 3. Non-Goals

- No UI required (CLI only)
- No ML model in MVP
- No multi-market strategy (single market focus)

---

## 4. System Architecture

### High-level architecture

[Polymarket WebSocket] → [Market Engine]
                                 ↓
                         [Arbitrage Engine]
                                 ↓
                         [Execution Engine]
                                 ↓
                           [Risk Manager]
                                 ↓
                             [Logger]

### External dependencies:
- Polymarket CLOB API
- Polymarket WebSocket
- Polygon RPC via QuickNode

---

## 5. Core Components

### 5.1 Market Data Module

Responsibilities:
- Subscribe to WebSocket feed
- Track:
  - Best bid/ask YES
  - Best bid/ask NO
  - Last trade price
  - Timestamp

Requirements:
- Latency < 500ms
- Reconnect on disconnect

---

### 5.2 Arbitrage Engine

Logic:

IF:
    yes_price + no_price < 1
THEN:
    arbitrage opportunity (BUY BOTH)

IF:
    yes_price + no_price > 1
THEN:
    reverse arbitrage (SELL BOTH)

Config:
- min_edge_threshold (default: 0.02)
- ignore opportunities below threshold

Output:
- signal: BUY / SELL / NONE
- confidence score

---

### 5.3 Execution Engine

Responsibilities:
- Place orders via Polymarket CLOB API
- Execute two legs (YES and NO)

Requirements:
- Atomic-like execution (minimize delay between legs)
- Retry failed orders
- Cancel unfilled orders after timeout

Execution strategy:
- Prefer limit orders at best bid/ask
- Fallback to market order if needed

---

### 5.4 Risk Management Module

Rules:
- Max position size: 2% of bankroll
- Max daily loss: configurable
- Max open exposure: configurable

Failure handling:
- If only one leg filled → hedge immediately
- If liquidity insufficient → abort trade

---

### 5.5 Wallet Module

Responsibilities:
- Sign transactions
- Manage private key securely
- Interact with Polygon via QuickNode

Requirements:
- Support USDC.e balance tracking
- Gas fee handling (POL)

---

### 5.6 Logger & Metrics

Log:
- All detected opportunities
- Executed trades
- Failed executions

Metrics:
- Win rate
- Total PnL
- Sharpe ratio (optional)

Storage:
- Local file (JSON or CSV)
- Optional: PostgreSQL

---

## 6. Configuration

Example config.yaml:

```yaml
rpc_url: "https://your-quicknode-endpoint"
private_key: "YOUR_PRIVATE_KEY"

trade:
  max_position_pct: 0.02
  min_edge_threshold: 0.02
  order_timeout_sec: 5

risk:
  max_daily_loss: 100


⸻

7. API Requirements

Polymarket API
	•	GET orderbook
	•	POST order
	•	DELETE order

Base URL:
https://clob.polymarket.com

⸻

WebSocket

Endpoint:
wss://ws-subscriptions-clob.polymarket.com/ws/market

Subscribe to:
	•	market_id

⸻

Blockchain (QuickNode)
	•	Polygon RPC
	•	Send transactions
	•	Approve tokens

⸻

8. Execution Flow
	1.	Connect WebSocket
	2.	Receive market updates
	3.	Update orderbook state
	4.	Run arbitrage detection
	5.	If opportunity:
	•	Validate liquidity
	•	Execute trades
	6.	Log results

⸻

9. Edge Cases
	•	Partial fill (critical)
	•	Sudden liquidity drop
	•	WebSocket disconnect
	•	Transaction failure
	•	Slippage

⸻

10. MVP Scope

Must include:
	•	Real-time data ingestion
	•	Arbitrage detection
	•	Paper trading mode
	•	Logging

Nice to have:
	•	Live trading
	•	Risk dashboard

⸻

11. Future Enhancements
	•	Multi-market arbitrage
	•	ML-based prediction layer
	•	Latency optimization
	•	Market making strategy

⸻

12. Acceptance Criteria
	•	Bot detects arbitrage correctly
	•	Executes both legs reliably
	•	Handles failures without crashing
	•	Logs all activity

⸻

13. Tech Stack
	•	Python (recommended)
	•	Asyncio + WebSockets
	•	FastAPI (optional)
	•	Redis (optional)
	•	PostgreSQL (optional)

⸻

14. Deployment
	•	VPS (low latency)
	•	Dockerized
	•	Auto-restart on crash

⸻

15. Risks
	•	Latency vs competitors
	•	Execution mismatch
	•	Market efficiency
	•	Smart contract interaction issues

⸻

16. Success Metrics
	•	Positive expected value (EV)
	•	Stable execution success rate (>95%)
	•	Low drawdown

---

# Penjelasan singkat (biar kamu tahu kenapa ini kuat)

PRD ini saya buat dengan prinsip:

- **tidak ambigu** → AI agent bisa langsung coding
- **modular** → gampang dipecah jadi task
- **real-world aware** → ada handling partial fill & latency
- **tidak over-engineered** → fokus MVP dulu

---

Kalau kamu mau next step yang paling impactful:

👉 saya bisa ubah ini jadi **task breakdown untuk AI agent (step-by-step coding plan)**  
👉 atau langsung buatkan **starter code Python sesuai PRD ini (biar agent tinggal lanjut)**