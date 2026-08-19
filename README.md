# Charles

Self-hosted AI trading bot powered by Groq's LLM. Charles screens a stock universe, scores signals using a combination of technical indicators and an LLM reasoning layer, checks the setup against a market-regime filter, and trades on Alpaca's paper trading API.

Paper trading by default — no real money at risk. Live trading is optional and requires your own funded Alpaca account.

## Features

- Autonomous screener across sectors, with a mid-day refresh
- Technical signals: RSI, MACD, moving-average structure
- LLM-based reasoning layer for signal scoring and news/sentiment context (via Groq)
- Market regime detection (trending bull, trending bear, ranging, volatile) that gates position sizing and shorting
- Four trading modes — mild, medium, hot, extreme — trading off frequency, position sizing, and risk
- Dynamic trailing stops, earnings blackout, daily loss kill switch
- Streamlit dashboard
- Telegram alerts

## Requirements

- Python 3.11
- Free API keys:
  - [Alpaca](https://alpaca.markets) (paper trading)
  - [Groq](https://console.groq.com) (LLM reasoning engine)
  - [Telegram bot token](https://core.telegram.org/bots) (for alerts, optional)

## Setup

You can run Charles on your own computer or on a cloud server so it runs 24/7. Either way, the steps are the same.

1. Clone the repo:
   ```
   git clone https://github.com/nswansonprojects/charles.git
   cd charles
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and fill in your API keys:
   ```
   cp .env.example .env
   ```
   ```
   ALPACA_API_KEY=your_key
   ALPACA_SECRET_KEY=your_secret
   GROQ_API_KEY=your_groq_key
   TELEGRAM_BOT_TOKEN=your_token       # optional
   TELEGRAM_CHAT_ID=your_chat_id       # optional
   ```

4. Run Charles:
   ```
   python main.py
   ```

5. A setup wizard opens in your browser to finish configuration. Once it's done, the dashboard is available at `http://localhost:8501`.

First startup can take a few minutes while it loads models and connects to Alpaca and Groq.

## Trading modes

Charles ships with four modes that trade off trading frequency, position sizing, and risk tolerance. Switch modes with:

```
charles-mode mild
charles-mode medium
charles-mode hot
charles-mode extreme
```

(Run with no argument to see the current mode.) The bot restarts automatically to apply the change.

| Mode | Max positions | Max position size | Min confidence | Scan interval | Shorting |
|------|---------------|--------------------|-----------------|----------------|----------|
| mild | 4 | 20% | 0.65 | 30 min | No |
| medium | 6 | 25% | 0.62 | 15 min | No |
| hot | 10 | 30% | 0.59 | 5 min | Yes, when regime allows |
| extreme | ~uncapped | 80% | 0.56 | 3 min | Yes, per-symbol technical trigger, regardless of regime |

**Extreme mode carries substantially more risk than the others** — a single position can consume most of the account's capital, and shorting is not gated by the overall market regime. The daily loss kill switch is raised in this mode but not removed; it remains the only hard backstop. Consider running mild or medium first to get a feel for how the bot behaves before switching to hot or extreme.

## Running 24/7 on a server

To keep Charles running continuously, deploy it on a cloud server (e.g. a $12/month DigitalOcean droplet) instead of your own machine. The setup steps are the same as above.

Full walkthrough: [charles-bot.xyz/setup.html](https://charles-bot.xyz/setup.html)

## Command reference

If deployed via the server setup script, these commands manage the bot:

| Command | What it does |
|---------|--------------|
| `charles-start` | Starts the bot |
| `charles-stop` | Stops the bot |
| `charles-restart` | Restarts the bot |
| `charles-status` | Shows whether it's running |
| `charles-logs` | Watches the live log stream |
| `charles-mode [mild\|medium\|hot\|extreme]` | Switches trading mode and restarts |

## Dashboard

Once running, visit `http://localhost:8501` (or `http://YOUR_SERVER_IP:8501` on a server) to view live positions, market regime, and the trading log.

## Disclaimer

Charles trades in Alpaca's paper trading environment by default — simulated orders, no real money. This is for educational and research purposes, not financial advice. Live trading is possible by configuring live Alpaca keys, but you take on full responsibility and risk for doing so. Backtesting on this project's own strategy has shown it can substantially underperform simply buying and holding during strong bull markets, and its clearest advantage so far has been reducing losses during downturns rather than outperforming in general. Trade accordingly.

## Support

Setup help and documentation: [charles-bot.xyz/setup.html](https://charles-bot.xyz/setup.html)
