"""
onboarding.py — First-run setup wizard.

Renders a guided setup screen in Streamlit when the bot
hasn't been configured yet. Writes credentials to .env
and settings to config so users never need to touch raw files.

Triggered when ALPACA_API_KEY is missing or placeholder.
"""

import os
import streamlit as st

SETUP_FLAG = os.path.join(os.path.dirname(__file__), "data", ".setup_complete")


def setup_complete() -> bool:
    """Returns True if onboarding has been completed."""
    import credential_manager as sec
    creds = sec.validate()
    return os.path.exists(SETUP_FLAG) and creds["alpaca"]


def mark_complete():
    """Mark setup as complete."""
    os.makedirs(os.path.dirname(SETUP_FLAG), exist_ok=True)
    with open(SETUP_FLAG, "w") as f:
        f.write("1")


def render_wizard():
    """
    Renders the full onboarding wizard.
    Returns True if setup was just completed (triggers rerun).
    """
    st.markdown("""
    <div style='text-align:center;padding:2rem 0 1rem'>
        <div style='font-size:3rem'>🤖</div>
        <h1 style='font-size:2rem;font-weight:800'>AI Trading Bot Setup</h1>
        <p style='color:#888;font-size:1.1rem'>
            Let's get you configured in about 2 minutes.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Progress steps
    steps = ["Alpaca Keys", "Telegram", "Portfolio", "Confirm"]
    step  = st.session_state.get("setup_step", 0)

    cols = st.columns(len(steps))
    for i, (col, name) in enumerate(zip(cols, steps)):
        done    = i < step
        current = i == step
        color   = "#00c864" if done else ("#4a9eff" if current else "#444")
        icon    = "✅" if done else ("▶️" if current else "○")
        col.markdown(
            f"<div style='text-align:center;color:{color};font-weight:"
            f"{'700' if current else '400'}'>{icon} {name}</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Step 0: Alpaca ────────────────────────────────────────────────────────
    if step == 0:
        st.subheader("Step 1 — Alpaca Paper Trading Keys")
        st.markdown("""
        1. Go to **[alpaca.markets](https://alpaca.markets)** and sign in
        2. Switch to **Paper Trading** in the top-left
        3. Find **API Keys** in the right sidebar
        4. Click **Generate New Keys** and copy both values
        """)

        col1, col2 = st.columns(2)
        api_key    = col1.text_input("API Key ID",    placeholder="PKXXXXXXXXXXXXXXX",
                                      type="password")
        api_secret = col2.text_input("Secret Key",    placeholder="xxxxxxxxxxxxxxxxxxxx",
                                      type="password")
        balance    = st.number_input("Starting paper balance ($)",
                                     min_value=100, max_value=1_000_000,
                                     value=1_000, step=100)

        if st.button("Test Connection →", type="primary", disabled=not (api_key and api_secret)):
            with st.spinner("Testing Alpaca connection..."):
                try:
                    from alpaca.trading.client import TradingClient
                    client  = TradingClient(api_key, api_secret, paper=True)
                    account = client.get_account()
                    st.success(
                        f"✅ Connected! Portfolio value: "
                        f"${float(account.portfolio_value):,.2f}"
                    )
                    st.session_state["setup_alpaca_key"]    = api_key
                    st.session_state["setup_alpaca_secret"] = api_secret
                    st.session_state["setup_balance"]       = balance
                    st.session_state["setup_step"]          = 1
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Connection failed: {e}\nDouble-check your keys.")

    # ── Step 1: Telegram ─────────────────────────────────────────────────────
    elif step == 1:
        st.subheader("Step 2 — Telegram Alerts (optional)")
        st.markdown("""
        Get trade alerts and hourly heartbeats on your phone.
        1. Message **@BotFather** on Telegram → type `/newbot`
        2. Follow the prompts to name your bot
        3. Copy the **token** it gives you
        4. Message **@userinfobot** → copy your **ID number**
        5. Search for your new bot and press **Start**
        """)

        token   = st.text_input("Bot Token",  placeholder="1234567890:AAFxxx...", type="password")
        chat_id = st.text_input("Your Chat ID", placeholder="123456789")

        col1, col2 = st.columns(2)
        if col1.button("Test & Continue →", type="primary",
                       disabled=not (token and chat_id)):
            with st.spinner("Sending test message..."):
                try:
                    import requests
                    r = requests.post(
                        f"https://api.telegram.org/bot{token}/sendMessage",
                        json={"chat_id": chat_id,
                              "text": "🤖 AI Trading Bot connected! Setup almost complete."},
                        timeout=8,
                    )
                    if r.status_code == 200:
                        st.success("✅ Message sent! Check your Telegram.")
                        st.session_state["setup_tg_token"]   = token
                        st.session_state["setup_tg_chat_id"] = chat_id
                        st.session_state["setup_step"]       = 2
                        st.rerun()
                    else:
                        st.error(f"❌ Failed: {r.json().get('description','Unknown error')}")
                except Exception as e:
                    st.error(f"❌ Error: {e}")

        if col2.button("Skip Telegram →"):
            st.session_state["setup_tg_token"]   = ""
            st.session_state["setup_tg_chat_id"] = ""
            st.session_state["setup_step"]       = 2
            st.rerun()

    # ── Step 2: Portfolio settings ────────────────────────────────────────────
    elif step == 2:
        st.subheader("Step 3 — Portfolio Settings")
        balance = st.session_state.get("setup_balance", 1000)

        st.info(f"💰 Account balance detected: **${balance:,}**")

        # Smart defaults based on balance
        if balance <= 1_000:
            default_positions = 4
            default_max_pct   = 10
            default_min_pct   = 5
            default_loss      = round(balance * 0.05)
        elif balance <= 10_000:
            default_positions = 6
            default_max_pct   = 8
            default_min_pct   = 3
            default_loss      = round(balance * 0.05)
        else:
            default_positions = 10
            default_max_pct   = 8
            default_min_pct   = 2
            default_loss      = round(balance * 0.05)

        col1, col2 = st.columns(2)
        max_pos  = col1.slider("Max open positions",   2, 20, default_positions)
        max_pct  = col2.slider("Max position size %",  5, 25, default_max_pct)
        min_pct  = col1.slider("Min position size %",  1, 10, default_min_pct)
        daily_loss = col2.number_input(
            "Daily loss kill switch ($)",
            min_value=10, max_value=balance,
            value=default_loss,
            help="Bot stops trading for the day if losses exceed this amount"
        )

        password = st.text_input(
            "Dashboard password (optional)",
            placeholder="Leave empty for no password",
            type="password",
            help="Protects the dashboard from unauthorized access"
        )

        if st.button("Save & Continue →", type="primary"):
            st.session_state["setup_max_pos"]    = max_pos
            st.session_state["setup_max_pct"]    = max_pct / 100
            st.session_state["setup_min_pct"]    = min_pct / 100
            st.session_state["setup_daily_loss"] = daily_loss
            st.session_state["setup_password"]   = password
            st.session_state["setup_step"]       = 3
            st.rerun()

    # ── Step 3: Confirm & write ───────────────────────────────────────────────
    elif step == 3:
        st.subheader("Step 4 — Confirm Setup")

        balance  = st.session_state.get("setup_balance", 1000)
        max_pos  = st.session_state.get("setup_max_pos", 4)
        max_pct  = st.session_state.get("setup_max_pct", 0.10)
        min_pct  = st.session_state.get("setup_min_pct", 0.05)
        loss     = st.session_state.get("setup_daily_loss", 50)
        has_tg   = bool(st.session_state.get("setup_tg_token"))
        has_pass = bool(st.session_state.get("setup_password"))

        st.markdown(f"""
        | Setting | Value |
        |---------|-------|
        | Alpaca connection | ✅ Verified |
        | Starting balance | ${balance:,} |
        | Max positions | {max_pos} |
        | Max position size | {max_pct*100:.0f}% (${balance*max_pct:,.0f}/trade) |
        | Min position size | {min_pct*100:.0f}% (${balance*min_pct:,.0f}/trade) |
        | Daily loss limit | ${loss:,} |
        | Telegram alerts | {"✅ Configured" if has_tg else "⏭ Skipped"} |
        | Dashboard password | {"✅ Set" if has_pass else "⏭ Not set"} |
        """)

        if st.button("🚀 Launch Bot", type="primary"):
            with st.spinner("Saving configuration..."):
                _write_env_file()
                _write_config_overrides()
                mark_complete()
                st.success("✅ Setup complete! Launching dashboard...")
                st.balloons()
                # Clear setup state
                for key in list(st.session_state.keys()):
                    if key.startswith("setup_"):
                        del st.session_state[key]
                st.rerun()

    return False


def _write_env_file():
    """Write credentials to .env file."""
    lines = [
        "# Trading Bot Credentials — DO NOT SHARE\n",
        f"ALPACA_API_KEY={st.session_state.get('setup_alpaca_key','')}\n",
        f"ALPACA_SECRET_KEY={st.session_state.get('setup_alpaca_secret','')}\n",
        f"TELEGRAM_BOT_TOKEN={st.session_state.get('setup_tg_token','')}\n",
        f"TELEGRAM_CHAT_ID={st.session_state.get('setup_tg_chat_id','')}\n",
        f"DASHBOARD_PASSWORD={st.session_state.get('setup_password','')}\n",
    ]
    path = os.path.join(os.path.dirname(__file__), ".env")
    with open(path, "w") as f:
        f.writelines(lines)

    # Protect .gitignore
    gi = os.path.join(os.path.dirname(__file__), ".gitignore")
    if not os.path.exists(gi):
        with open(gi, "w") as f:
            f.write(".env\n*.pyc\n__pycache__/\ndata/\nlogs/\n")


def _write_config_overrides():
    """Write non-secret settings to a runtime overrides file."""
    overrides = {
        "VIRTUAL_CASH":          st.session_state.get("setup_balance",     1000),
        "MAX_OPEN_POSITIONS":    st.session_state.get("setup_max_pos",     4),
        "MAX_POSITION_SIZE_PCT": st.session_state.get("setup_max_pct",     0.10),
        "MIN_POSITION_SIZE_PCT": st.session_state.get("setup_min_pct",     0.05),
        "MAX_DAILY_LOSS":        st.session_state.get("setup_daily_loss",  50.0),
        "BACKTEST_CAPITAL":      st.session_state.get("setup_balance",     1000),
    }
    import json
    path = os.path.join(os.path.dirname(__file__), "data", "config_overrides.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(overrides, f, indent=2)
