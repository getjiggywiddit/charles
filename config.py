# ============================================================
#  TRADING BOT CONFIGURATION  —  v8
#  Stocks only | Cash account optimized | $1,000 account
# ============================================================

# --- Alpaca Paper Trading ← YOUR KEYS GO IN .env FILE ------
# Leave these empty — keys are loaded from .env by credential_manager
ALPACA_API_KEY    = ""
ALPACA_SECRET_KEY = ""
ALPACA_PAPER      = True
ALPACA_ACCOUNT_TYPE = "cash"   # "cash" or "margin" — affects PDT logic

# --- Telegram Alerts ← YOUR KEYS GO IN .env FILE -----------
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID   = ""

# --- AI / LLM Settings ---------------------------------------
# Groq is recommended for server deployment (free, fast, no GPU needed)
# Get a free API key at console.groq.com
# If GROQ_API_KEY is set, Groq is used. Otherwise falls back to Ollama.
GROQ_API_KEY  = ""          # set in .env as GROQ_API_KEY
GROQ_MODEL    = "llama-3.1-8b-instant"   # free, very fast

# Ollama (local fallback — used if Groq key not set)
OLLAMA_HOST  = "http://localhost:11434"
OLLAMA_MODEL = "llama3.1"

# Which LLM to use: "groq", "ollama", or "auto" (groq if key set, else ollama)
LLM_PROVIDER = "auto"

# --- Stock Watchlist (screener auto-updates daily) ----------
# Crypto removed — stocks only for cleaner signals and zero fees
STOCK_WATCHLIST = ["MRVL","SMCI","ORCL","AMAT","ARM","ASML","MU","KLAC"]

# --- Cash account settings ----------------------------------
# Cash accounts have no PDT restriction but require T+2 settlement
# We track settlement dates to avoid using unsettled funds
SETTLEMENT_DAYS   = 2      # T+2 for stocks (T+1 coming 2024 but T+2 to be safe)
MAX_UNSETTLED_PCT = 0.30   # never use more than 30% unsettled funds

# --- Portfolio settings --------------------------------------
VIRTUAL_CASH          = 1_000.0   # matches $1,000 Alpaca account
MAX_OPEN_POSITIONS    = 4         # 4 max at $1k — enough diversification

# --- Position sizing -----------------------------------------
# Cash account: size conservatively to always have dry powder
MAX_POSITION_SIZE_PCT = 0.20      # 10% = $100/trade at $1k
MIN_POSITION_SIZE_PCT = 0.05      # 5%  = $50/trade minimum

# --- Stop loss / Take profit ---------------------------------
STOP_LOSS_PCT         = 0.05      # 5% fixed stop loss
TAKE_PROFIT_PCT       = 0.15      # 15% fixed take profit

# --- Trailing stops ------------------------------------------
TRAILING_STOP_ATR_MULT = 2.0      # wide enough for noise, tight for reversals

# --- Daily max loss kill switch ------------------------------
MAX_DAILY_LOSS        = 50.0      # 5% of $1k — halt if exceeded

# --- Strategy thresholds ------------------------------------
RSI_OVERSOLD          = 35
RSI_OVERBOUGHT        = 65
MIN_CONFIDENCE        = 0.65      # slightly strict at small account

# --- Volume confirmation ------------------------------------
VOLUME_CONFIRM_RATIO  = 1.2       # volume must be 1.2x 20-day avg

# --- Scan schedule ------------------------------------------
# Cash account: scan during market hours only — no overnight needed
STOCK_SCAN_INTERVAL_MIN = 30      # every 30 min during market hours
NEWS_REFRESH_MIN        = 60      # top of every hour

# --- Cooldown / duplicate prevention ------------------------
TRADE_COOLDOWN_HOURS  = 4         # prevent doubling up same position

# --- Earnings blackout --------------------------------------
EARNINGS_BLACKOUT_DAYS = 3        # skip stocks within 3 days of earnings

# --- Market trend filter ------------------------------------
SPY_TREND_PERIOD      = 20        # 20-day MA for bull/bear detection

# --- Cash account PDT guard ---------------------------------
# Not needed for cash accounts but kept as safety net
MAX_DAY_TRADES_PER_WEEK = 999     # unlimited on cash account

# --- Backtesting --------------------------------------------
BACKTEST_YEARS        = 2
BACKTEST_CAPITAL      = 1_000.0

# --- Reporting ----------------------------------------------
STREAMLIT_PORT        = 8501
LOG_LEVEL             = "INFO"

# --- News sources -------------------------------------------
RSS_FEEDS = [
    # Financial news
    "https://feeds.finance.yahoo.com/rss/2.0/headline",
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.reuters.com/reuters/technologyNews",
    "https://feeds.marketwatch.com/marketwatch/topstories",
    "https://www.investing.com/rss/news.rss",
    "https://seekingalpha.com/market_currents.xml",
    # Stock specific
    "https://finance.yahoo.com/rss/2.0/headline?s=AAPL,MSFT,NVDA,TSLA,GOOGL",
]
