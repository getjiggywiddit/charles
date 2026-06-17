# Charles

Self-hosted AI trading bot powered by Groq's LLM. Charles screens a 100-stock universe, scores signals using a combination of technical indicators and an LLM reasoning layer, and trades on Alpaca's paper trading API 24/7.

Paper trading by default — no real money at risk. Live trading is optional and requires your own Alpaca live keys.

## Features

- 100-stock screener across sectors, with a mid-day refresh
- Technical signals: RSI, MACD, 50-day moving average breakout
- LLM-based reasoning layer for signal scoring (via Groq)
- Sector rotation scoring
- Relative strength vs SPY
- 52-week high breakout detection
- Dynamic trailing stops
- Earnings exit protection
- Pre-market gap filter
- Time-based exits for stale trades
- Streamlit dashboard
- Telegram alerts

## Requirements

- Python 3.11
- Free API keys:
  - [Alpaca](https://alpaca.markets) (paper trading)
  - [Groq](https://console.groq.com) (LLM reasoning engine)
  - [Telegram bot token](https://core.telegram.org/bots) (for alerts)

## Setup

You can run Charles on your own computer or on a cloud server so it runs 24/7. Either way, the steps are the same.

1. Clone this repo:
   ```bash
   git clone https://github.com/getjiggywiddit/charles.git
   cd charles
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and fill in your API keys:
   ```bash
   cp .env.example .env
   ```

4. Run Charles:
   ```bash
   python main.py
   ```

5. A setup wizard opens in your browser to finish configuration. Once it's done, the dashboard is available at `http://localhost:8501`.

First startup can take a few minutes while it loads models and connects to Alpaca and Groq.

## Running 24/7 on a server

To keep Charles running continuously, deploy it on a cloud server (e.g. a $12/month DigitalOcean droplet) instead of your own machine. The setup steps are the same as above — clone, install dependencies, add your `.env`, and run.

Full walkthrough: [charles-bot.xyz/setup.html](https://charles-bot.xyz/setup.html)

## Dashboard

Once running, visit `http://localhost:8501` (or `http://YOUR_SERVER_IP:8501` on a server) to view live positions, signals, and performance.

## Disclaimer

Charles trades in Alpaca's paper trading environment by default — simulated orders, no real money. This is for educational and research purposes, not financial advice. Live trading is possible by configuring live Alpaca keys, but you take on full responsibility and risk for doing so.

## Contributing

Pull requests are welcome. Feel free to fork and extend the strategy logic, add new signals, or improve the dashboard.

## Support

Setup help and documentation: [charles-bot.xyz/setup.html](https://charles-bot.xyz/setup.html)
