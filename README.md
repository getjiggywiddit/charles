# AI Paper Trading Bot

AI-powered paper trading bot for stocks and crypto.
Runs entirely locally — zero ongoing API costs.

## Quick Start

### 1. Fill in your config
Open `config.py` and add your Alpaca paper trading keys:
```
ALPACA_API_KEY    = "your key here"
ALPACA_SECRET_KEY = "your secret here"
```
Get free paper trading keys at https://alpaca.markets → sign up → Paper Trading → API Keys

### 2. Install Ollama + pull a model
Download Ollama from https://ollama.com then run in terminal:
```
ollama pull llama3.1
```
(or `ollama pull mistral` for a smaller/faster model)

### 3. Press Play on main.py in JetBrains
That's it. The bot will:
- Auto-install all Python packages
- Run an immediate data collection + trading cycle
- Schedule daily runs at 9:00 AM
- Open the dashboard at http://localhost:8501

## File Structure
```
tradingbot/
├── main.py          ← Press Play here
├── config.py        ← Your settings & watchlist
├── collector.py     ← Fetches prices, news, sentiment
├── brain.py         ← AI decision engine (Ollama + rules)
├── portfolio.py     ← Paper trade execution & tracking
├── dashboard.py     ← Streamlit web dashboard
├── requirements.txt ← Python dependencies
└── data/
    ├── latest.json  ← Most recent market snapshot
    ├── portfolio.json← Your virtual portfolio state
    └── trades.json  ← Full trade history
```

## Free Data Sources Used
| Data | Source | Cost |
|------|---------|------|
| Stock prices | Yahoo Finance (yfinance) | Free |
| Crypto prices | CoinGecko public API | Free |
| News headlines | RSS feeds (Reuters, Yahoo, CoinDesk) | Free |
| Sentiment scoring | VADER NLP (local) | Free |
| Fear & Greed index | CNN (scraped) | Free |
| AI decisions | Ollama local LLM | Free |
| Paper trading | Alpaca paper account | Free |

## Customising the Watchlist
Edit `config.py`:
```python
STOCK_WATCHLIST  = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL"]
CRYPTO_WATCHLIST = ["BTC/USD", "ETH/USD", "SOL/USD"]
```

## Adjusting Risk
```python
VIRTUAL_CASH          = 100_000.0  # Starting balance
MAX_POSITION_SIZE_PCT = 0.05       # 5% max per trade
STOP_LOSS_PCT         = 0.05       # 5% stop loss
MIN_CONFIDENCE        = 0.60       # LLM confidence threshold
```
