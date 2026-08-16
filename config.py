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


# ============================================================
#  TRADING MODES  —  mild / medium / hot
#  Set via: charles-mode mild|medium|hot
#  Overrides the base values above when ACTIVE_MODE != "mild"
# ============================================================
import os
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(_env_path):
        load_dotenv(_env_path, encoding="utf-8")
except Exception:
    pass

ACTIVE_MODE = os.environ.get("ACTIVE_MODE", "mild").strip().lower()
if ACTIVE_MODE not in ("mild", "medium", "hot", "extreme"):
    ACTIVE_MODE = "mild"

TRADING_MODES = {
    "mild": {
        "MAX_OPEN_POSITIONS":      4,
        "MAX_POSITION_SIZE_PCT":   0.20,
        "STOP_LOSS_PCT":           0.05,
        "TAKE_PROFIT_PCT":         0.15,
        "MIN_CONFIDENCE":          0.65,
        "STOCK_SCAN_INTERVAL_MIN": 30,
        "TRADE_COOLDOWN_HOURS":    4,
        "MAX_DAILY_LOSS":          50.0,
        "GROQ_TOKEN_BUDGET":       6400,   # matches full 8-symbol batch, paced
        "MAX_SYMBOLS_PER_CYCLE":   8,
        "GROQ_CALL_DELAY_SEC":     8.6,
        "ALLOW_SHORTING":          False,  # ignores regime's allow_shorts
        "DESCRIPTION":             "Current default. Conservative, fewer trades.",
    },
    "medium": {
        "MAX_OPEN_POSITIONS":      6,
        "MAX_POSITION_SIZE_PCT":   0.25,
        "STOP_LOSS_PCT":           0.07,
        "TAKE_PROFIT_PCT":         0.12,
        "MIN_CONFIDENCE":          0.62,
        "STOCK_SCAN_INTERVAL_MIN": 15,
        "TRADE_COOLDOWN_HOURS":    2,
        "MAX_DAILY_LOSS":          75.0,
        "GROQ_TOKEN_BUDGET":       12000,  # matches full 15-symbol batch, paced
        "MAX_SYMBOLS_PER_CYCLE":   15,
        "GROQ_CALL_DELAY_SEC":     8.6,
        "ALLOW_SHORTING":          False,
        "DESCRIPTION":             "Trades more often, moderate risk increase.",
    },
    "hot": {
        "MAX_OPEN_POSITIONS":      10,
        "MAX_POSITION_SIZE_PCT":   0.30,
        "STOP_LOSS_PCT":           0.10,
        "TAKE_PROFIT_PCT":         0.08,
        "MIN_CONFIDENCE":          0.59,
        "STOCK_SCAN_INTERVAL_MIN": 5,
        "TRADE_COOLDOWN_HOURS":    0.5,
        "MAX_DAILY_LOSS":          100.0,
        "GROQ_TOKEN_BUDGET":       22400,  # matches 28-symbol batch, paced
        "MAX_SYMBOLS_PER_CYCLE":   28,     # capped so paced Groq calls fit in the 5-min interval
        "GROQ_CALL_DELAY_SEC":     8.6,
        "ALLOW_SHORTING":          True,   # only used when regime.allow_shorts is also True
        "DESCRIPTION":             "Intraday, high frequency, highest risk. Shorts enabled when regime allows.",
    },
    "extreme": {
        "MAX_OPEN_POSITIONS":      99,     # effectively uncapped — capital runs out first
        "MAX_POSITION_SIZE_PCT":   0.80,   # 80% of total capital per position
        "STOP_LOSS_PCT":           0.12,
        "TAKE_PROFIT_PCT":         0.06,   # take profit fast, this mode is about frequency
        "MIN_CONFIDENCE":          0.56,   # lowest bar of all modes
        "STOCK_SCAN_INTERVAL_MIN": 3,      # fastest interval that stays under Groq TPM budget
        "TRADE_COOLDOWN_HOURS":    0.25,
        "MAX_DAILY_LOSS":          150.0,  # raised ceiling — still a hard floor, not removed
        "GROQ_TOKEN_BUDGET":       12800,  # matches 16-symbol batch, paced
        "MAX_SYMBOLS_PER_CYCLE":   16,     # 3-min interval only fits 16 paced Groq calls safely
        "GROQ_CALL_DELAY_SEC":     8.6,
        "ALLOW_SHORTING":          True,
        "SHORT_IGNORES_REGIME":    True,   # NEW: per-symbol short trigger, not gated by SPY-wide regime
        "ALLOW_OPTIONS":           False,  # reserved — not wired to execution yet
        "DESCRIPTION":             "No meaningful position limits. 80% capital per trade, fastest scan interval possible under API budget, shorts fire on per-symbol technical breakdown regardless of overall market regime. Kill switch is the only backstop.",
    },
}

def get_mode_config(mode: str = None) -> dict:
    """Returns the parameter dict for the given mode (or ACTIVE_MODE if None)."""
    mode = mode or ACTIVE_MODE
    return TRADING_MODES.get(mode, TRADING_MODES["mild"])


# ── Apply active mode overrides on top of base values ──────────────────────
_mode_cfg = get_mode_config()
MAX_OPEN_POSITIONS     = _mode_cfg["MAX_OPEN_POSITIONS"]
MAX_POSITION_SIZE_PCT  = _mode_cfg["MAX_POSITION_SIZE_PCT"]
STOP_LOSS_PCT          = _mode_cfg["STOP_LOSS_PCT"]
TAKE_PROFIT_PCT        = _mode_cfg["TAKE_PROFIT_PCT"]
MIN_CONFIDENCE         = _mode_cfg["MIN_CONFIDENCE"]
STOCK_SCAN_INTERVAL_MIN = _mode_cfg["STOCK_SCAN_INTERVAL_MIN"]
TRADE_COOLDOWN_HOURS   = _mode_cfg["TRADE_COOLDOWN_HOURS"]
MAX_DAILY_LOSS         = _mode_cfg["MAX_DAILY_LOSS"]
GROQ_TOKEN_BUDGET      = _mode_cfg["GROQ_TOKEN_BUDGET"]
MAX_SYMBOLS_PER_CYCLE  = _mode_cfg["MAX_SYMBOLS_PER_CYCLE"]
GROQ_CALL_DELAY_SEC    = _mode_cfg.get("GROQ_CALL_DELAY_SEC", 8.6)
ALLOW_SHORTING_MODE    = _mode_cfg["ALLOW_SHORTING"]
