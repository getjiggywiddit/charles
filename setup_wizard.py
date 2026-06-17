"""
setup_wizard.py — Interactive setup wizard that runs BEFORE the bot.
Launched by main.py as a blocking Streamlit process.
Validates all credentials, writes .env, then signals main.py to launch.
Bot ONLY starts after the user clicks Launch and all checks pass.
"""

import json
import os
import sys
import time

import streamlit as st
import requests

WIZARD_DIR   = os.path.dirname(os.path.abspath(__file__))

def _ensure_pyarrow():
    """Install pyarrow via conda if missing — pip version has DLL issues on Windows."""
    try:
        import pyarrow
        return
    except ImportError:
        pass
    try:
        conda_prefix = os.environ.get("CONDA_PREFIX", "")
        if conda_prefix:
            import subprocess as _sp
            print("Installing pyarrow via conda (fixes Windows DLL issue)...")
            _sp.run(["conda", "install", "-c", "conda-forge", "pyarrow", "-y", "--quiet"],
                    capture_output=True)
    except Exception:
        pass

_ensure_pyarrow()
DATA_DIR     = os.path.join(WIZARD_DIR, "data")
LAUNCH_FLAG  = os.path.join(DATA_DIR, "launch_authorized.json")
ENV_FILE     = os.path.join(WIZARD_DIR, ".env")

os.makedirs(DATA_DIR, exist_ok=True)

st.set_page_config(
    page_title="Trading Bot Setup",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Custom styling ────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { max-width: 720px; margin: 0 auto; }
    .stButton > button { width: 100%; padding: 0.75rem; font-size: 1rem; }
    .status-ok  { color: #00c864; font-weight: 700; }
    .status-err { color: #e03030; font-weight: 700; }
    .step-header { font-size: 1.3rem; font-weight: 700; margin: 1rem 0 0.5rem; }
</style>
""", unsafe_allow_html=True)


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='text-align:center;padding:1.5rem 0 0.5rem'>
    <div style='font-size:3.5rem'>🤖</div>
    <h1 style='font-size:2rem;font-weight:800;margin:0.5rem 0'>AI Paper Trading Bot</h1>
    <p style='color:#888;font-size:1rem'>Complete setup below — the bot launches only when all checks pass.</p>
</div>
""", unsafe_allow_html=True)

st.divider()


# ── Load existing .env if present ─────────────────────────────────────────────
def _load_env() -> dict:
    vals = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    vals[k.strip()] = v.strip()
    return vals

existing = _load_env()


# ── Also check config.py as fallback ─────────────────────────────────────────
def _config_val(key: str) -> str:
    try:
        import config
        return getattr(config, key, "") or ""
    except Exception:
        return ""


def _prefill(key: str) -> str:
    """Return existing .env value, then config.py fallback, then empty."""
    v = existing.get(key, "")
    if not v or v.startswith("YOUR_") or v.startswith("REPLACE_"):
        v = _config_val(key)
    if v and (v.startswith("YOUR_") or v.startswith("REPLACE_")):
        return ""
    return v


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — ALPACA
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='step-header'>Step 1 — Alpaca Paper Trading</div>",
            unsafe_allow_html=True)
st.caption("Get free paper trading keys at alpaca.markets → Paper Trading → API Keys")

col1, col2 = st.columns(2)
alpaca_key    = col1.text_input("API Key ID",   value=_prefill("ALPACA_API_KEY"),
                                 type="password", placeholder="PKXXXXXXXXXXXXXXX")
alpaca_secret = col2.text_input("Secret Key",   value=_prefill("ALPACA_SECRET_KEY"),
                                 type="password", placeholder="xxxxxxxxxxxxxxxxxxxx")

alpaca_ok     = False
alpaca_value  = 0.0

if alpaca_key and alpaca_secret:
    with st.spinner("Verifying Alpaca connection..."):
        try:
            from alpaca.trading.client import TradingClient
            client  = TradingClient(alpaca_key, alpaca_secret, paper=True)
            account = client.get_account()
            alpaca_value = float(account.portfolio_value)
            st.markdown(
                f"<span class='status-ok'>✅ Connected — Portfolio: ${alpaca_value:,.2f} | "
                f"Buying power: ${float(account.buying_power):,.2f}</span>",
                unsafe_allow_html=True,
            )
            alpaca_ok = True
        except Exception as e:
            st.markdown(f"<span class='status-err'>❌ Failed: {e}</span>",
                        unsafe_allow_html=True)
else:
    st.caption("↑ Enter your Alpaca keys to verify connection")

st.divider()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — AI / LLM
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='step-header'>Step 2 — AI Brain (LLM)</div>",
            unsafe_allow_html=True)

st.info(
    "**Groq is recommended** — free, 10x faster than local Ollama, no GPU needed. "
    "Get a free key at [console.groq.com](https://console.groq.com) in under 2 minutes."
)

llm_choice = st.radio("Which AI provider?",
                       ["Groq (recommended — free cloud)", "Ollama (local)"],
                       horizontal=True)

groq_key    = ""
ollama_host = "http://localhost:11434"
ollama_model = "llama3.1"
ollama_ok   = False

if "Groq" in llm_choice:
    groq_key = st.text_input(
        "Groq API Key",
        value=_prefill("GROQ_API_KEY"),
        type="password",
        placeholder="gsk_xxxxxxxxxxxxxxxxxxxx",
        help="Free at console.groq.com — takes 2 minutes to set up"
    )
    if groq_key:
        with st.spinner("Verifying Groq key..."):
            try:
                r = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {groq_key}",
                             "Content-Type": "application/json"},
                    json={"model": "llama-3.1-8b-instant",
                          "messages": [{"role":"user","content":"Say OK"}],
                          "max_tokens": 5},
                    timeout=10,
                )
                if r.status_code == 200:
                    st.markdown("<span class='status-ok'>✅ Groq connected — fast cloud inference ready</span>",
                                unsafe_allow_html=True)
                    ollama_ok = True
                else:
                    st.markdown(f"<span class='status-err'>❌ Invalid key ({r.status_code})</span>",
                                unsafe_allow_html=True)
            except Exception as e:
                st.markdown(f"<span class='status-err'>❌ {e}</span>", unsafe_allow_html=True)
    else:
        st.caption("↑ Enter your free Groq API key")
else:
    ollama_host  = st.text_input("Ollama host", value="http://localhost:11434")
    ollama_model = st.selectbox("Model", ["llama3.1", "mistral", "llama3.2"])
    if ollama_host:
        try:
            r = requests.get(f"{ollama_host}/api/tags", timeout=3)
            models = [m["name"] for m in r.json().get("models", [])]
            if any(ollama_model in m for m in models):
                st.markdown(f"<span class='status-ok'>✅ Ollama running — {ollama_model} ready</span>",
                            unsafe_allow_html=True)
                ollama_ok = True
            else:
                st.markdown(f"<span class='status-err'>⚠️ Run: ollama pull {ollama_model}</span>",
                            unsafe_allow_html=True)
        except Exception:
            st.markdown("<span class='status-err'>❌ Ollama not running — start with: ollama serve</span>",
                        unsafe_allow_html=True)
            ollama_ok = True   # non-fatal

st.divider()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — TELEGRAM (optional)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='step-header'>Step 3 — Telegram Alerts (optional)</div>",
            unsafe_allow_html=True)
st.caption("Get trade alerts and hourly heartbeats on your phone")

tg_token   = st.text_input("Bot Token",   value=_prefill("TELEGRAM_BOT_TOKEN"),
                             type="password", placeholder="1234567890:AAFxxx...")
tg_chat_id = st.text_input("Your Chat ID", value=_prefill("TELEGRAM_CHAT_ID"),
                             placeholder="123456789")
tg_ok      = False

if tg_token and tg_chat_id:
    col_test, col_skip = st.columns(2)
    if col_test.button("📱 Send test message"):
        with st.spinner("Sending..."):
            try:
                r = requests.post(
                    f"https://api.telegram.org/bot{tg_token}/sendMessage",
                    json={"chat_id": tg_chat_id,
                          "text": "🤖 AI Trading Bot — Telegram connected!"},
                    timeout=8,
                )
                if r.status_code == 200:
                    st.markdown("<span class='status-ok'>✅ Message sent!</span>",
                                unsafe_allow_html=True)
                    tg_ok = True
                    st.session_state["tg_verified"] = True
                else:
                    st.markdown(
                        f"<span class='status-err'>❌ {r.json().get('description','Failed')}</span>",
                        unsafe_allow_html=True,
                    )
            except Exception as e:
                st.markdown(f"<span class='status-err'>❌ {e}</span>",
                            unsafe_allow_html=True)

    if st.session_state.get("tg_verified"):
        tg_ok = True
        st.markdown("<span class='status-ok'>✅ Telegram verified</span>",
                    unsafe_allow_html=True)
else:
    st.caption("↑ Optional — leave blank to skip Telegram alerts")
    tg_ok = True   # optional, not blocking

st.divider()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — PORTFOLIO SETTINGS
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='step-header'>Step 4 — Portfolio Settings</div>",
            unsafe_allow_html=True)

balance = alpaca_value if alpaca_value > 0 else float(_config_val("VIRTUAL_CASH") or 1000)

# Smart defaults based on balance
if balance <= 1_000:
    def_pos, def_max, def_min, def_loss = 4,  10, 5,  round(balance * 0.05)
elif balance <= 10_000:
    def_pos, def_max, def_min, def_loss = 6,  8,  3,  round(balance * 0.05)
else:
    def_pos, def_max, def_min, def_loss = 10, 8,  2,  round(balance * 0.05)

if alpaca_ok:
    st.info(f"💰 Account balance: **${balance:,.2f}** — settings auto-configured for this size")

col1, col2 = st.columns(2)
max_pos    = col1.slider("Max open positions",  2, 20, def_pos)
max_pct    = col2.slider("Max position size %", 5, 25, def_max)
min_pct    = col1.slider("Min position size %", 1, 10, def_min)
daily_loss = col2.number_input("Daily loss limit ($)", min_value=5,
                                max_value=int(balance) if balance > 5 else 1000,
                                value=int(def_loss))

st.divider()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — DASHBOARD PASSWORD
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='step-header'>Step 5 — Dashboard Security (optional)</div>",
            unsafe_allow_html=True)
st.caption("Protects the dashboard from unauthorized access")

pwd = st.text_input("Dashboard password", type="password",
                    value=existing.get("DASHBOARD_PASSWORD", ""),
                    placeholder="Leave empty for no password")

st.divider()


# ══════════════════════════════════════════════════════════════════════════════
# LAUNCH SECTION
# ══════════════════════════════════════════════════════════════════════════════
all_ok = alpaca_ok and ollama_ok and tg_ok

st.markdown("<div class='step-header'>Launch Status</div>", unsafe_allow_html=True)

status_rows = [
    ("Alpaca connection", alpaca_ok),
    ("Ollama / AI",       ollama_ok),
    ("Telegram",          tg_ok),
]
for label, ok in status_rows:
    icon  = "✅" if ok else "❌"
    color = "#00c864" if ok else "#e03030"
    st.markdown(f"<span style='color:{color}'>{icon} {label}</span>",
                unsafe_allow_html=True)

st.markdown("")

if not all_ok:
    st.warning("Complete all required steps above to enable the Launch button.")

launch_clicked = st.button(
    "🚀 Launch Trading Bot",
    type="primary",
    disabled=not all_ok,
    help="All checks must pass before launching" if not all_ok else "Click to launch!",
)

if launch_clicked and all_ok:
    # Write .env file
    env_lines = [
        "# Trading Bot Credentials\n",
        f"ALPACA_API_KEY={alpaca_key}\n",
        f"ALPACA_SECRET_KEY={alpaca_secret}\n",
        f"TELEGRAM_BOT_TOKEN={tg_token}\n",
        f"TELEGRAM_CHAT_ID={tg_chat_id}\n",
        f"DASHBOARD_PASSWORD={pwd}\n",
    ]
    with open(ENV_FILE, "w") as f:
        f.writelines(env_lines)

    # Write .gitignore
    gi = os.path.join(WIZARD_DIR, ".gitignore")
    if not os.path.exists(gi):
        with open(gi, "w") as f:
            f.write(".env\n*.pyc\n__pycache__/\ndata/\nlogs/\n")

    # Write launch authorization with all settings
    launch_data = {
        "authorized":      True,
        "timestamp":       time.time(),
        "alpaca_key":      alpaca_key,
        "alpaca_secret":   alpaca_secret,
        "tg_token":        tg_token,
        "tg_chat_id":      tg_chat_id,
        "dashboard_pwd":   pwd,
        "groq_key":        groq_key,
        "ollama_host":     ollama_host,
        "ollama_model":    ollama_model,
        "balance":         balance,
        "max_positions":   max_pos,
        "max_pct":         max_pct / 100,
        "min_pct":         min_pct / 100,
        "daily_loss":      float(daily_loss),
    }
    with open(LAUNCH_FLAG, "w") as f:
        json.dump(launch_data, f)

    st.success("✅ Configuration saved — launching bot...")
    time.sleep(2)
    st.markdown("**The bot is now starting. This window will close shortly.**")
    # Signal main.py by writing the flag — main.py polls for it
    time.sleep(1)
    st.stop()
