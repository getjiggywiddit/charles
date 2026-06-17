"""
# ── Guard: must be run via streamlit, not python directly ────────────────────
import sys as _sys
if _sys.argv[0].endswith("dashboard.py"):
    print("\n⚠️  Don't run dashboard.py directly!")
    print("   Run main.py instead — it launches the dashboard automatically.")
    print("   In PyCharm: make sure Play button points to main.py\n")
    _sys.exit(0)

dashboard.py — Full-feature Streamlit dashboard v4.
Covers: equity curve, live portfolio, signals, regime, risk controls,
        news sentiment, backtest, screener.
"""

import json, os, sys, time
from datetime import datetime, timezone, timedelta

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))
import config
import reports as rep

st.set_page_config(page_title="CharlesBot — AI Trading System", page_icon="📈",
                   layout="wide", initial_sidebar_state="expanded")

DATA_DIR    = os.path.join(os.path.dirname(__file__), "data")


@st.cache_data(ttl=5)
def load_notifications():
    p = os.path.join(DATA_DIR, "notifications.json")
    if not os.path.exists(p):
        return []
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return []

@st.cache_data(ttl=300)
def load_reports_list():
    import glob
    rdir = os.path.join(DATA_DIR, "..", "reports")
    rdir = os.path.normpath(rdir)
    if not os.path.exists(rdir):
        return []
    files = sorted(glob.glob(os.path.join(rdir, "*.csv")), reverse=True)
    return files

@st.cache_data(ttl=60)
def load_demographics(period, start=None, end=None):
    try:
        import demographics as demo
        trades, equity, _, _ = demo._filter_period(
            demo._load_trades(), demo._load_equity(), period, start, end)
        return trades, equity
    except Exception as e:
        return [], []

def _df(data, **kwargs):
    """Safe dataframe display — uses HTML to completely bypass pyarrow."""
    try:
        import pandas as _pd
        if not isinstance(data, _pd.DataFrame):
            data = _pd.DataFrame(data)
        # Try native streamlit first
        st.dataframe(data, **kwargs)
    except Exception:
        try:
            # HTML fallback — zero pyarrow dependency
            import pandas as _pd
            if not isinstance(data, _pd.DataFrame):
                data = _pd.DataFrame(data)
            html = data.to_html(index=False, border=0,
                                classes="dataframe",
                                escape=True)
            st.markdown(
                f"""<style>
                .dataframe {{border-collapse:collapse;width:100%;font-size:0.85rem}}
                .dataframe th {{background:#1e1e2e;padding:6px 10px;text-align:left;
                                border-bottom:1px solid #333;color:#aaa;font-weight:600}}
                .dataframe td {{padding:5px 10px;border-bottom:1px solid #222;color:#ddd}}
                .dataframe tr:hover td {{background:#1a1a2e}}
                </style>{html}""",
                unsafe_allow_html=True,
            )
        except Exception as e:
            st.error(f"Could not display table: {e}")
START_VALUE = config.VIRTUAL_CASH


# No password required — dashboard loads directly


# Setup is handled by setup_wizard.py before the dashboard launches


# ── Loaders ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=20)
def load_alpaca():
    try:
        import alpaca_executor as alpaca
        return alpaca.get_account_summary()
    except Exception as e:
        return {"error": str(e)}

@st.cache_data(ttl=20)
def load_snapshot():
    p = os.path.join(DATA_DIR, "latest.json")
    return json.load(open(p)) if os.path.exists(p) else None

@st.cache_data(ttl=15)
def load_equity():
    p = os.path.join(DATA_DIR, "equity_curve.json")
    return json.load(open(p)) if os.path.exists(p) else []

@st.cache_data(ttl=20)
def load_trades():
    p = os.path.join(DATA_DIR, "trades.json")
    return json.load(open(p)) if os.path.exists(p) else []

@st.cache_data(ttl=30)
def load_watchlist():
    p = os.path.join(DATA_DIR, "watchlist.json")
    return json.load(open(p)) if os.path.exists(p) else None

@st.cache_data(ttl=30)
def load_performance():
    p = os.path.join(DATA_DIR, "performance.json")
    return json.load(open(p)) if os.path.exists(p) else None

@st.cache_data(ttl=60)
def load_backtest():
    p = os.path.join(DATA_DIR, "backtest_results.json")
    return json.load(open(p)) if os.path.exists(p) else None

@st.cache_data(ttl=20)
def load_trailing():
    try:
        import risk_manager as rm
        return rm.get_trailing_stops()
    except Exception:
        return {}

@st.cache_data(ttl=20)
def load_daily_stats():
    try:
        import risk_manager as rm
        return rm.get_daily_stats()
    except Exception:
        return {}

@st.cache_data(ttl=30)
def load_timeofday():
    try:
        import timeofday
        return timeofday.session_info()
    except Exception:
        return {}

@st.cache_data(ttl=60)
def load_macro_events():
    try:
        import macro_calendar as mc
        in_blackout = mc.in_macro_blackout()
        return {
            "in_blackout": in_blackout,
            "upcoming":    mc.get_upcoming_events(7),
            "next":        mc.next_event(),
        }
    except Exception:
        return {}

@st.cache_data(ttl=30)
def load_finbert_status():
    try:
        import finbert_sentiment as fbs
        return fbs.is_finbert_active()
    except Exception:
        return False

@st.cache_data(ttl=30)
def load_regime():
    try:
        import regime as reg
        r, d = reg.detect_regime()
        return r, d
    except Exception:
        return "UNKNOWN", {}

def load_tax_report(start_date, end_date):
    try:
        import tax_engine as te
        return te.generate_report(start_date, end_date)
    except Exception as e:
        return {"error": str(e)}

@st.cache_data(ttl=20)
def load_cooldowns():
    p = os.path.join(DATA_DIR, "cooldowns.json")
    return json.load(open(p)) if os.path.exists(p) else {}


# ── Equity chart ──────────────────────────────────────────────────────────────

def build_equity_chart(curve, trades, title="Portfolio equity"):
    if not curve:
        fig = go.Figure()
        fig.add_annotation(text="No data yet — run the bot to populate the chart",
                           xref="paper", yref="paper", x=0.5, y=0.5,
                           showarrow=False, font=dict(size=13, color="gray"))
        fig.update_layout(height=400, paper_bgcolor="rgba(0,0,0,0)",
                          plot_bgcolor="rgba(0,0,0,0)")
        return fig

    df = pd.DataFrame(curve)
    df["ts"]    = pd.to_datetime(df["ts"])
    df["value"] = df["value"].astype(float)

    # Split into gain / loss fill
    above = df["value"].clip(lower=START_VALUE)
    below = df["value"].clip(upper=START_VALUE)

    fig = go.Figure()
    ts_list = [str(t) for t in df["ts"].tolist()]
    fig.add_trace(go.Scatter(x=ts_list, y=above.tolist(), fill="tozeroy",
                             fillcolor="rgba(0,200,100,0.12)",
                             line=dict(color="rgba(0,0,0,0)", width=0),
                             showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=ts_list, y=below.tolist(), fill="tozeroy",
                             fillcolor="rgba(220,50,50,0.12)",
                             line=dict(color="rgba(0,0,0,0)", width=0),
                             showlegend=False, hoverinfo="skip"))

    # Color-segmented main line with data point markers
    num_points = len(df)
    # Show dots only if reasonable number of points
    show_markers = num_points <= 200
    mode = "lines+markers" if show_markers else "lines"
    marker_size = max(3, min(7, 200 // max(num_points, 1)))

    for seg_df, color in _split_segments(df):
        fig.add_trace(go.Scatter(
            x=[str(t) for t in seg_df["ts"].tolist()],
            y=seg_df["value"].tolist(),
            mode=mode,
            line=dict(color=color, width=2.5),
            marker=dict(size=marker_size, color=color,
                        line=dict(width=1, color="white")) if show_markers else None,
            showlegend=False,
            hovertemplate="<b>%{x|%b %d %H:%M}</b><br>$%{y:,.2f}<extra></extra>",
        ))

    # Baseline
    fig.add_hline(y=START_VALUE, line_dash="dot",
                  line_color="rgba(150,150,150,0.5)",
                  annotation_text=f"Start ${START_VALUE:,.0f}",
                  annotation_position="right",
                  annotation_font=dict(size=10, color="gray"))

    # Trade markers
    if trades:
        def nearest_val(ts_str):
            try:
                ts  = pd.to_datetime(ts_str[:19], utc=True)
                idx = (df["ts"] - ts).abs().idxmin()
                return float(df.loc[idx, "value"])
            except Exception:
                return START_VALUE

        buys   = [t for t in trades if t["action"] in ("BUY",)]
        sells  = [t for t in trades if t["action"] in ("SELL","SHORT_COVER")]
        shorts = [t for t in trades if t["action"] == "SHORT"]

        for group, symbol, color, marker in [
            (buys,   "BUY",   "#00c864", "triangle-up"),
            (sells,  "SELL",  "#e03030", "triangle-down"),
            (shorts, "SHORT", "#ff9500", "triangle-down"),
        ]:
            if group:
                xs = [pd.to_datetime(t["timestamp"][:19], utc=True) for t in group]
                ys = [nearest_val(t["timestamp"]) for t in group]
                ls = [f"{t['action']} {t['symbol']} ${t.get('value',0):,.0f}"
                      + (f" P&L ${t['pnl']:+,.0f}" if "pnl" in t else "")
                      for t in group]
                fig.add_trace(go.Scatter(
                    x=xs, y=ys, mode="markers", name=symbol, text=ls,
                    marker=dict(symbol=marker, size=11, color=color,
                                line=dict(width=1.5, color="white")),
                    hovertemplate="%{text}<extra></extra>",
                ))

    current = float(df["value"].iloc[-1])
    pct     = (current - START_VALUE) / START_VALUE * 100
    color   = "#00c864" if current >= START_VALUE else "#e03030"
    sign    = "+" if pct >= 0 else ""

    # Auto-scale y-axis around actual data range with padding
    y_min = float(df["value"].min())
    y_max = float(df["value"].max())
    y_pad = max((y_max - y_min) * 0.15, 20)   # at least $20 padding
    y_low = max(0, y_min - y_pad)
    y_high = y_max + y_pad

    fig.update_layout(
        title=dict(text=f"{title}  <span style='color:{color}'>{sign}{pct:.2f}%</span>",
                   font=dict(size=15)),
        height=420,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.1)",
                   tickformat="%b %d\n%H:%M"),
        yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.1)",
                   tickprefix="$", tickformat=",.0f",
                   range=[y_low, y_high]),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=50, b=30, l=60, r=20),
    )
    return fig


def _split_segments(df):
    segs, cur_seg = [], []
    cur_col = "#00c864" if float(df["value"].iloc[0]) >= START_VALUE else "#e03030"
    for _, row in df.iterrows():
        col = "#00c864" if float(row["value"]) >= START_VALUE else "#e03030"
        if col != cur_col and cur_seg:
            segs.append((pd.DataFrame(cur_seg), cur_col))
            cur_seg = [cur_seg[-1]]
            cur_col = col
        cur_seg.append(row)
    if cur_seg:
        segs.append((pd.DataFrame(cur_seg), cur_col))
    return segs


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("CharlesBot 🤖 -- AI Trading System v1.0 (Official Release)")
    st.caption("Paper trading · All features active")
    st.divider()

    # Regime badge
    regime_name, regime_detail = load_regime()
    regime_colors = {
        "TRENDING_BULL":  ("🟢", "green"),
        "TRENDING_BEAR":  ("🔴", "red"),
        "RANGING":        ("🟡", "orange"),
        "VOLATILE":       ("⚠️",  "red"),
    }
    icon, col = regime_colors.get(regime_name, ("⚪","gray"))
    st.markdown(f"**Market Regime**")
    st.markdown(f":{col}[{icon} {regime_name.replace('_',' ')}]")
    if regime_detail:
        st.caption(f"ATR {regime_detail.get('atr_pct',0):.1f}% · "
                   f"Mom {regime_detail.get('momentum_10d',0):+.1f}% · "
                   f"Chop {regime_detail.get('choppiness',0):.2f}")

    st.divider()

    # Daily kill switch status
    daily = load_daily_stats()
    halted = daily.get("halted", False)
    daily_pnl = daily.get("loss", 0)
    if halted:
        st.error(f"🚨 Kill switch ACTIVE\nLoss today: ${daily_pnl:,.2f}")
    else:
        color = "green" if daily_pnl >= 0 else "red"
        st.markdown(f"**Today's P&L:** :{color}[${daily_pnl:+,.2f}]")
        st.caption(f"Kill switch at -${config.MAX_DAILY_LOSS:,.0f}")

    snap = load_snapshot()
    if snap:
        st.divider()
        fg = snap.get("fear_greed", {})
        sc = fg.get("score", 50)
        lb = fg.get("label","Neutral")
        ic = "🟢" if sc > 55 else ("🔴" if sc < 45 else "🟡")
    perf = load_performance()
    if perf:
        st.divider()
        st.caption("🧠 Self-tuning")
        st.metric("Win Rate",    f"{perf.get('win_rate',0):.1f}%")
        st.metric("Confidence",  f"{perf.get('tuned_confidence', config.MIN_CONFIDENCE):.0%}")

    wl = load_watchlist()
    if wl:
        st.divider()
        st.caption("📋 Today's watchlist (auto-screened)")
        st.caption("📈 " + ", ".join(wl.get("stocks",[])))
        st.caption("🪙 " + ", ".join(wl.get("crypto",[])))

    st.divider()
    auto_refresh = st.toggle("Auto-refresh (15s)", value=True)
    sess = load_timeofday()
    if sess:
        st.divider()
        st.caption("⏰ Session")
        phase_icons = {
            "open_noise": "⚡", "morning_trend": "📈",
            "midday_lull": "😴", "afternoon_trend": "📈",
            "pre_close": "⚠️", "after_hours": "🌙",
        }
        icon = phase_icons.get(sess.get("phase",""), "⏰")
        st.caption(f"{icon} {sess.get('time_et','?')} — {sess.get('phase','?').replace('_',' ')}")
        if sess.get("avoid_trading"):
            st.warning(f"⏸ {sess.get('avoid_reason','')}")
        elif sess.get("optimal_window"):
            st.success("✅ Optimal window")

    macro = load_macro_events()
    next_ev = macro.get("next")
    if next_ev:
        st.divider()
        st.caption("📅 Next macro event")
        st.caption(f"**{next_ev['name']}**")
        st.caption(f"In {next_ev['hours_away']:.1f}h")
        if next_ev["hours_away"] < 4:
            st.warning("⚠️ Blackout zone soon")

    if st.button("🔄 Refresh now"):
        st.cache_data.clear()
        st.rerun()

    # ── Live notification feed ────────────────────────────────────────────────
    notifs = load_notifications()
    if notifs:
        st.divider()
        st.caption("🔔 Live activity")
        for n in reversed(notifs[-8:]):
            ts    = n.get("ts","")[:16].replace("T"," ")
            icon  = n.get("icon","•")
            title = n.get("title","")
            msg   = n.get("message","")
            level = n.get("level","info")
            color = {"success":"#00c864","warning":"#f39c12",
                     "error":"#e03030","info":"#4a9eff"}.get(level,"#888")
            st.markdown(
                f"""<div style='background:rgba(255,255,255,0.04);border-left:3px solid {color};
                border-radius:4px;padding:6px 10px;margin:3px 0;font-size:0.82rem'>
                <span style='color:{color};font-weight:700'>{icon} {title}</span>
                <span style='color:#888;font-size:0.75rem;float:right'>{ts}</span><br>
                <span style='color:#aaa'>{msg}</span>
                </div>""",
                unsafe_allow_html=True,
            )


# ── Tabs ──────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
    "📈 Equity", "📊 Portfolio", "🌡️ Regime & Risk",
    "🧠 Signals", "📰 News", "📉 Backtest",
    "🔍 Screener", "🧾 Tax Docs", "📊 Reports", "📐 Demographics"
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — EQUITY CURVE
# ══════════════════════════════════════════════════════════════════════════════

with tab1:
    summary = load_alpaca()
    curve   = load_equity()
    trades  = load_trades()

    if summary and "error" not in summary:
        c1,c2,c3,c4,c5 = st.columns(5)
        total = summary.get("total_value", START_VALUE)
        ret   = summary.get("total_return", 0)
        pct   = summary.get("total_return_pct", 0)
        c1.metric("Portfolio Value", f"${total:,.2f}")
        c2.metric("Total Return",    f"${ret:+,.2f}", f"{pct:+.2f}%", delta_color="normal")
        c3.metric("Cash",            f"${summary.get('cash',0):,.2f}")
        c4.metric("Buying Power",    f"${summary.get('buying_power',0):,.2f}")
        c5.metric("Positions",       summary.get("open_positions",0))
    else:
        st.warning("Waiting for Alpaca connection...")

    # ── Daily Win/Loss Banner ─────────────────────────────────────────────────
    daily_stats = load_daily_stats()
    daily_pnl   = daily_stats.get("loss", 0)   # named 'loss' but holds net P&L
    halted      = daily_stats.get("halted", False)

    # Also compute today's P&L from equity curve for accuracy
    try:
        curve_now = load_equity()
        from datetime import date as _date
        today_str = str(_date.today())
        today_pts = [p for p in curve_now if p.get("ts","")[:10] == today_str]
        if today_pts and summary and "error" not in (summary or {}):
            start_today = today_pts[0]["value"]
            current_val = summary.get("total_value", start_today)
            daily_pnl   = current_val - start_today
    except Exception:
        pass

    daily_pct = (daily_pnl / config.VIRTUAL_CASH * 100)
    is_up     = daily_pnl >= 0
    border_color = "#00c864" if is_up else "#e03030"
    banner_color = "rgba(0,200,100,0.12)" if is_up else "rgba(220,50,50,0.12)"
    icon_big     = "📈" if is_up else "📉"
    sign         = "+" if is_up else ""

    if halted:
        st.markdown(
            f"""<div style='background:{banner_color};border-left:4px solid #ff9500;
            border-radius:8px;padding:16px 20px;margin:8px 0'>
            <span style='font-size:1.5rem'>🚨</span>
            <span style='font-size:1.8rem;font-weight:700;color:#ff9500;margin-left:12px'>
            TRADING HALTED</span>
            <span style='font-size:1.1rem;color:#aaa;margin-left:16px'>
            Daily loss limit hit — resumes at midnight</span>
            </div>""",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""<div style='background:{banner_color};border-left:4px solid {border_color};
            border-radius:8px;padding:16px 20px;margin:8px 0;display:flex;align-items:center;gap:16px'>
            <span style='font-size:2rem'>{icon_big}</span>
            <div>
              <div style='font-size:0.85rem;color:#aaa;font-weight:500;letter-spacing:0.05em'>
              TODAY&apos;S P&amp;L</div>
              <div style='font-size:2.2rem;font-weight:800;color:{border_color};line-height:1.1'>
              {sign}${abs(daily_pnl):,.2f}</div>
              <div style='font-size:1rem;color:{border_color};opacity:0.85'>
              {sign}{abs(daily_pct):.2f}% today</div>
            </div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.divider()

    # Timeframe filter
    tf_col, _ = st.columns([1, 4])
    with tf_col:
        tf = st.selectbox("Timeframe", ["All time","Today","1 Week","1 Month"], label_visibility="collapsed")

    filtered_curve = curve
    if curve and tf != "All time":
        df_c = pd.DataFrame(curve)
        df_c["ts"] = pd.to_datetime(df_c["ts"])
        now = pd.Timestamp.now(tz="UTC")
        cuts = {"Today": now - timedelta(days=1),
                "1 Week": now - timedelta(weeks=1),
                "1 Month": now - timedelta(days=30)}
        filt = df_c[df_c["ts"] >= cuts[tf]]
        if not filt.empty:
            filtered_curve = filt.to_dict("records")
            for r in filtered_curve:
                r["ts"] = str(r["ts"])

    st.plotly_chart(build_equity_chart(filtered_curve, trades), use_container_width=True)

    if curve:
        df_eq = pd.DataFrame(curve)
        vals  = df_eq["value"].tolist()
        high  = max(vals); low = min(vals)
        peak, max_dd = START_VALUE, 0
        for v in vals:
            if v > peak: peak = v
            dd = (peak - v) / peak * 100
            if dd > max_dd: max_dd = dd
        cs1,cs2,cs3,cs4 = st.columns(4)
        cs1.metric("All-time High",  f"${high:,.2f}")
        cs2.metric("All-time Low",   f"${low:,.2f}")
        cs3.metric("Max Drawdown",   f"-{max_dd:.2f}%")
        cs4.metric("Data points",    f"{len(curve):,}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — PORTFOLIO
# ══════════════════════════════════════════════════════════════════════════════

with tab2:
    summary  = load_alpaca()
    trailing = load_trailing()

    if "error" in (summary or {}):
        st.error(f"Alpaca error: {summary['error']}")
    elif summary:
        positions = summary.get("positions", [])
        if positions:
            st.subheader(f"Open positions ({len(positions)})")
            rows = []
            for p in positions:
                sym   = p["symbol"]
                side  = p.get("side","long").upper()
                ts    = trailing.get(sym, {})
                stop  = ts.get("stop")
                high  = ts.get("highest")
                rows.append({
                    "Symbol":        sym,
                    "Side":          "🟢 LONG" if side == "LONG" else "🔴 SHORT",
                    "Shares":        f"{p['shares']:.4f}",
                    "Avg Price":     f"${p['avg_price']:,.4f}",
                    "Current":       f"${p['current_price']:,.4f}",
                    "Value":         f"${p['market_value']:,.2f}",
                    "P&L":           f"${p['unrealized_pnl']:+,.2f}",
                    "P&L %":         f"{p['unrealized_pct']:+.2f}%",
                    "Trailing Stop": f"${stop:,.4f}" if stop else "—",
                    "Peak":          f"${high:,.4f}" if high else "—",
                })
            _df(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            if len(positions) > 1:
                fig = px.pie(
                    values=[abs(p["market_value"]) for p in positions],
                    names=[f"{p['symbol']} ({p.get('side','long').upper()})" for p in positions],
                    title="Allocation", hole=0.4,
                )
                fig.update_layout(height=280, margin=dict(t=40,b=0,l=0,r=0))
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No open positions.")

        # Cooldowns
        cd = load_cooldowns()
        if cd:
            st.divider()
            st.subheader("⏳ Cooldowns")
            cd_rows = []
            for sym, ts in cd.items():
                elapsed   = (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).total_seconds() / 3600
                remaining = max(0, config.TRADE_COOLDOWN_HOURS - elapsed)
                cd_rows.append({
                    "Symbol":    sym,
                    "Last trade": ts[:19].replace("T"," "),
                    "Cooldown":  f"{remaining:.1f}h left" if remaining > 0 else "✅ Ready",
                })
            _df(pd.DataFrame(cd_rows), use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Trade history")
        trades = load_trades()
        if trades:
            df_t = pd.DataFrame(reversed(trades[-50:]))
            df_t["timestamp"] = df_t["timestamp"].str[:19].str.replace("T"," ")
            if "pnl" in df_t.columns:
                df_t["pnl"] = df_t["pnl"].apply(lambda v: f"${v:+,.2f}" if pd.notna(v) else "—")
            _df(df_t, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — REGIME & RISK
# ══════════════════════════════════════════════════════════════════════════════

with tab3:
    regime_name, detail = load_regime()

    try:
        import regime as reg_mod
        mults = reg_mod.regime_multipliers(regime_name)
    except Exception:
        mults = {}

    # Regime card
    icon, col = regime_colors.get(regime_name, ("⚪","gray"))
    st.subheader(f"{icon} Market Regime: {regime_name.replace('_',' ')}")
    st.caption(mults.get("description",""))

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("ATR %",        f"{detail.get('atr_pct',0):.2f}%")
    c2.metric("10d Momentum", f"{detail.get('momentum_10d',0):+.2f}%")
    c3.metric("Choppiness",   f"{detail.get('choppiness',0):.2f}")
    c4.metric("Vol expanding",str(detail.get('vol_expanding', False)))

    st.divider()
    st.subheader("⚙️ Regime behavior")
    rc1, rc2 = st.columns(2)
    with rc1:
        st.write(f"**Size multiplier:** {mults.get('size_mult',1):.0%}")
        st.write(f"**Confidence boost:** +{mults.get('conf_boost',0):.0%}")
    with rc2:
        st.write(f"**Longs allowed:** {'✅' if mults.get('allow_longs') else '❌'}")
        st.write(f"**Shorts allowed:** {'✅' if mults.get('allow_shorts') else '❌'}")
        st.write(f"**Hedges (inverse ETFs):** {'✅' if mults.get('allow_hedges') else '❌'}")

    st.divider()
    st.subheader("🛡️ Trailing stops")
    trailing = load_trailing()
    if trailing:
        ts_rows = []
        for sym, ts in trailing.items():
            locked = ts["highest"] - ts["entry"]
            ts_rows.append({
                "Symbol":       sym,
                "Entry":        f"${ts['entry']:,.4f}",
                "Peak":         f"${ts['highest']:,.4f}",
                "Stop":         f"${ts['stop']:,.4f}",
                "ATR dist":     f"${ts.get('dist',0):,.4f}",
                "Locked in":    f"${locked:+,.4f}",
            })
        _df(pd.DataFrame(ts_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No trailing stops active (opens when positions are entered).")

    st.divider()
    st.subheader("🚨 Daily kill switch")
    daily = load_daily_stats()
    halted = daily.get("halted", False)
    daily_pnl = daily.get("loss", 0)

    d1,d2,d3 = st.columns(3)
    d1.metric("Today's P&L",   f"${daily_pnl:+,.2f}")
    d2.metric("Limit",         f"-${config.MAX_DAILY_LOSS:,.0f}")
    d3.metric("Status",        "🚨 HALTED" if halted else "✅ Active")

    remaining_budget = config.MAX_DAILY_LOSS + daily_pnl
    pct_used = max(0, -daily_pnl / config.MAX_DAILY_LOSS * 100)
    st.progress(min(pct_used / 100, 1.0),
                text=f"Daily loss budget: ${max(0, remaining_budget):,.0f} remaining  ({pct_used:.0f}% used)")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — SIGNALS
# ══════════════════════════════════════════════════════════════════════════════

with tab4:
    snap = load_snapshot()
    if not snap:
        st.info("No snapshot yet — run the bot first.")
    else:
        market = snap.get("market", {})

        try:
            import market_filter as mf
            bullish, spy_pct = mf.market_is_bullish()
            trend_color = "green" if bullish else "red"
            trend_label = "📈 BULLISH — buys enabled" if bullish else "📉 BEARISH — buys suppressed"
            st.markdown(f"**SPY trend:** :{trend_color}[{trend_label}] ({spy_pct:+.2f}% vs MA{config.SPY_TREND_PERIOD})")
        except Exception:
            pass

        rows = []
        for sym, d in market.items():
            rsi  = d.get("rsi", 50)
            macd = d.get("macd", 0)
            sig  = d.get("macd_signal", 0)
            bb   = d.get("bb_pos", 0.5)
            vol  = d.get("vol_ratio", 1.0)

            try:
                near, days = mf.near_earnings(sym)
                earn = f"⚠️ {days}d" if near else "✅"
            except Exception:
                earn = "—"

            rows.append({
                "Symbol":    sym,
                "Price":     f"${d['price']:,.4f}",
                "Change":    f"{d.get('change_pct',0):+.2f}%",
                "RSI 14":    round(rsi,1),
                "RSI 7":     round(d.get("rsi_7",rsi),1),
                "MACD X":    "🟢" if macd > sig else "🔴",
                "BB pos":    f"{bb:.2f}",
                "Vol ratio": f"{vol:.1f}x",
                "Vol ✓":     "✅" if d.get("vol_confirm") else "❌",
                "MTF Buy":   "✅" if d.get("mtf_buy") else "—",
                "MTF Sell":  "✅" if d.get("mtf_sell") else "—",
                "ATR%":      f"{d.get('atr_pct',0):.2f}%",
                "Earnings":  earn,
            })

        if rows:
            _df(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            syms   = list(market.keys())
            rsis   = [market[s].get("rsi",50) for s in syms]
            colors = ["#00c864" if r < config.RSI_OVERSOLD
                      else ("#e03030" if r > config.RSI_OVERBOUGHT else "#4a9eff")
                      for r in rsis]

            fig = go.Figure(go.Bar(x=syms, y=rsis, marker_color=colors,
                                   hovertemplate="%{x}: RSI %{y:.1f}<extra></extra>"))
            fig.add_hline(y=config.RSI_OVERSOLD,   line_dash="dash", line_color="#00c864",
                          annotation_text=f"Oversold ({config.RSI_OVERSOLD})")
            fig.add_hline(y=config.RSI_OVERBOUGHT, line_dash="dash", line_color="#e03030",
                          annotation_text=f"Overbought ({config.RSI_OVERBOUGHT})")
            fig.update_layout(title="RSI overview", height=280, yaxis=dict(range=[0,100]),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              margin=dict(t=40,b=0,l=0,r=0))
            st.plotly_chart(fig, use_container_width=True)

            # Bollinger band position chart
            bbs    = [market[s].get("bb_pos",0.5) for s in syms]
            bb_col = ["#00c864" if b < 0.2 else ("#e03030" if b > 0.8 else "#4a9eff") for b in bbs]
            fig2 = go.Figure(go.Bar(x=syms, y=bbs, marker_color=bb_col,
                                    hovertemplate="%{x}: BB pos %{y:.2f}<extra></extra>"))
            fig2.add_hline(y=0.15, line_dash="dash", line_color="#00c864", annotation_text="Near lower band")
            fig2.add_hline(y=0.85, line_dash="dash", line_color="#e03030", annotation_text="Near upper band")
            fig2.update_layout(title="Bollinger Band position (0=lower, 1=upper)", height=260,
                               yaxis=dict(range=[0,1]),
                               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               margin=dict(t=40,b=0,l=0,r=0))
            st.plotly_chart(fig2, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — NEWS
# ══════════════════════════════════════════════════════════════════════════════

with tab5:
    snap = load_snapshot()

    # ── Live news feed ────────────────────────────────────────────────────────
    st.subheader("📰 Market News Feed")

    # Always try to show fresh news even if snapshot is old
    news = []
    if snap:
        news = snap.get("news", [])
        ts_str = snap.get("collected_at","")[:19].replace("T"," ")
        finbert_on = load_finbert_status()
        col_a, col_b = st.columns([3,1])
        col_a.caption(f"Last updated: {ts_str} UTC  ·  {'🧠 FinBERT' if finbert_on else '📊 VADER'} sentiment")
        col_b.caption(f"{len(news)} articles")

    if not news:
        st.info(
            "No news collected yet. The bot fetches news every hour. "
            "Check back after the first collection cycle."
        )
    else:
        # Sentiment summary bar
        sentiments = [a.get("sentiment",0) for a in news]
        pos = sum(1 for s in sentiments if s > 0.05)
        neg = sum(1 for s in sentiments if s < -0.05)
        neu = len(sentiments) - pos - neg
        sc1,sc2,sc3,sc4 = st.columns(4)
        sc1.metric("🟢 Bullish", pos)
        sc2.metric("⚪ Neutral", neu)
        sc3.metric("🔴 Bearish", neg)
        avg_sent = sum(sentiments)/len(sentiments) if sentiments else 0
        sc4.metric("Avg sentiment", f"{avg_sent:+.3f}")

        # Filter controls
        fc1, fc2 = st.columns([2,2])
        sent_filter = fc1.radio("Filter by sentiment",
                                ["All","Bullish only","Bearish only"],
                                horizontal=True)
        sym_filter  = fc2.selectbox("Filter by stock", ["All stocks"] +
                                    list(set(s for a in news
                                             for s in a.get("mentioned",[]))))

        filtered_news = news
        if sent_filter == "Bullish only":
            filtered_news = [a for a in news if a.get("sentiment",0) > 0.05]
        elif sent_filter == "Bearish only":
            filtered_news = [a for a in news if a.get("sentiment",0) < -0.05]
        if sym_filter != "All stocks":
            filtered_news = [a for a in filtered_news
                             if sym_filter in a.get("mentioned",[])]

        st.caption(f"Showing {len(filtered_news)} articles")
        st.divider()

        # Articles
        for a in filtered_news[:30]:
            s    = a.get("sentiment",0)
            icon = "🟢" if s > 0.05 else ("🔴" if s < -0.05 else "⚪")
            mentioned = ", ".join(a.get("mentioned",[])) or "—"
            pub  = a.get("published","")[:16]
            with st.expander(f"{icon}  {a['title'][:120]}  ·  {pub}"):
                summary = a.get("summary","")
                if summary:
                    st.write(summary[:400])
                c1,c2,c3 = st.columns(3)
                c1.metric("Sentiment", f"{s:+.3f}",
                          delta="Bullish" if s > 0.05 else ("Bearish" if s < -0.05 else "Neutral"),
                          delta_color="normal" if s > 0 else "inverse")
                c2.caption(f"📊 Stocks: {mentioned}")
                c3.caption(f"🕐 {pub}")

    # ── Macro calendar ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("📅 Upcoming Market Events")
    macro = load_macro_events()
    upcoming = macro.get("upcoming", [])
    if upcoming:
        for ev in upcoming[:5]:
            hours = ev.get("hours_away", 0)
            warn  = "⚠️ " if hours < 4 else ""
            color = "#e03030" if hours < 4 else ("#f39c12" if hours < 24 else "#4a9eff")
            st.markdown(
                f"<div style='padding:8px 12px;margin:4px 0;border-radius:6px;"
                f"border-left:3px solid {color};background:rgba(255,255,255,0.03)'>"
                f"<b>{warn}{ev['name']}</b> — in <b>{hours:.0f}h</b>"
                f"  <span style='color:#888;font-size:0.85rem'>({ev['dt']})</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No major events in the next 7 days.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — BACKTEST
# ══════════════════════════════════════════════════════════════════════════════

with tab6:
    bt = load_backtest()
    if not bt:
        st.info("No backtest results yet.")
        st.code("python backtest.py", language="bash")
        st.caption("Run the above in your terminal to backtest 2 years of historical data.")
    else:
        run_at = bt.get("run_at","")[:19].replace("T"," ")
        st.caption(f"Last run: {run_at} UTC · {bt.get('years',2)} years · {len(bt.get('symbols',[]))} symbols")

        results = [r for r in bt.get("results",[]) if "error" not in r]
        if results:
            total_start = sum(r["start_capital"] for r in results)
            total_end   = sum(r["end_capital"]   for r in results)
            port_ret    = (total_end - total_start) / total_start * 100

            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Portfolio Return", f"{port_ret:+.2f}%")
            c2.metric("Avg Sharpe",       f"{sum(r['sharpe_ratio'] for r in results)/len(results):.3f}")
            c3.metric("Avg Win Rate",     f"{sum(r['win_rate'] for r in results)/len(results):.1f}%")
            c4.metric("Avg Max Drawdown", f"{sum(r['max_drawdown_pct'] for r in results)/len(results):.1f}%")

            st.divider()
            df_bt = pd.DataFrame([{
                "Symbol": r["symbol"],
                "Return": f"{r['total_return_pct']:+.1f}%",
                "vs B&H": f"{r['alpha']:+.1f}%",
                "Sharpe": r["sharpe_ratio"],
                "Win %":  f"{r['win_rate']:.0f}%",
                "Max DD": f"-{r['max_drawdown_pct']:.1f}%",
                "Trades": r["closed_trades"],
            } for r in results])
            _df(df_bt, use_container_width=True, hide_index=True)

            fig = go.Figure()
            fig.add_trace(go.Bar(name="Strategy",
                x=[r["symbol"] for r in results],
                y=[r["total_return_pct"] for r in results],
                marker_color=["#00c864" if r["total_return_pct"]>=0 else "#e03030" for r in results]))
            fig.add_trace(go.Bar(name="Buy & Hold",
                x=[r["symbol"] for r in results],
                y=[r["buy_hold_pct"] for r in results],
                marker_color="rgba(100,150,255,0.6)"))
            fig.update_layout(title="Strategy vs Buy & Hold", barmode="group", height=300,
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              yaxis_ticksuffix="%", margin=dict(t=40,b=0,l=0,r=0))
            st.plotly_chart(fig, use_container_width=True)

            fig2 = go.Figure()
            for r in results:
                ec = r.get("equity_curve",[])
                if ec:
                    fig2.add_trace(go.Scatter(y=ec, mode="lines", name=r["symbol"],
                        hovertemplate=f"{r['symbol']}: $%{{y:,.0f}}<extra></extra>"))
            if results:
                fig2.add_hline(y=results[0]["start_capital"], line_dash="dot", line_color="gray")
            fig2.update_layout(title="Equity curves", height=320,
                               yaxis_tickprefix="$", yaxis_tickformat=",.0f",
                               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               margin=dict(t=40,b=0,l=0,r=0),
                               legend=dict(orientation="h"))
            st.plotly_chart(fig2, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 7 — SCREENER
# ══════════════════════════════════════════════════════════════════════════════

with tab7:
    wl = load_watchlist()
    if not wl:
        st.info("Screener runs at startup and daily at 8:45 AM ET.")
    else:
        st.caption(f"Screened: {wl.get('generated_at','')[:19].replace('T',' ')} UTC")
        scores = wl.get("scores",[])
        if scores:
            df_sc = pd.DataFrame(scores)
            for asset_type, label in [("stock","📈 Stocks"), ("crypto","🪙 Crypto")]:
                sub = df_sc[df_sc["type"]==asset_type].sort_values("score", ascending=False)
                if sub.empty:
                    continue
                st.subheader(label)
                fig = px.bar(sub, x="symbol", y="score", color="score",
                             range_color=[0,100],
                             color_continuous_scale=["#e03030","#f39c12","#00c864"],
                             title="Momentum score (0–100)")
                fig.update_layout(height=240, paper_bgcolor="rgba(0,0,0,0)",
                                  plot_bgcolor="rgba(0,0,0,0)",
                                  margin=dict(t=40,b=0,l=0,r=0))
                st.plotly_chart(fig, use_container_width=True)

        perf = load_performance()
        if perf:
            st.divider()
            st.subheader("🧠 Performance feedback loop")
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Win Rate",   f"{perf.get('win_rate',0):.1f}%")
            c2.metric("Total P&L",  f"${perf.get('total_pnl',0):,.2f}")
            c3.metric("Avg Win",    f"${perf.get('avg_win',0):,.2f}")
            c4.metric("Avg Loss",   f"${perf.get('avg_loss',0):,.2f}")
            good = perf.get("good_symbols",[])
            bad  = perf.get("bad_symbols",[])
            if good: st.success("✅ Best performers: " + ", ".join(good))
            if bad:  st.error("❌ Worst performers: "  + ", ".join(bad))


# ══════════════════════════════════════════════════════════════════════════════
# TAB 8 — TAX DOCUMENTATION
# ══════════════════════════════════════════════════════════════════════════════

with tab8:
    import tax_engine as te
    from datetime import date

    st.subheader("🧾 Tax Documentation")
    st.caption(
        "Generates IRS-style capital gains reports from your trade history. "
        "Uses FIFO cost basis, detects wash sales, and separates short-term "
        "vs long-term gains. **Always consult a tax professional before filing.**"
    )
    st.divider()

    # ── Date range selector ───────────────────────────────────────────────────
    st.markdown("**Select reporting period**")
    period_col1, period_col2, period_col3 = st.columns([1, 1, 2])

    with period_col1:
        preset = st.selectbox("Quick select", [
            "Custom range",
            "Tax Year 2025 (Jan 1 – Dec 31)",
            "Tax Year 2026 (Jan 1 – Dec 31)",
            "Last 30 days",
            "Last 90 days",
            "Last 6 months",
            "All time",
        ])

    today = date.today()
    if preset == "Tax Year 2025 (Jan 1 – Dec 31)":
        default_start = date(2025, 1, 1)
        default_end   = date(2025, 12, 31)
    elif preset == "Tax Year 2026 (Jan 1 – Dec 31)":
        default_start = date(2026, 1, 1)
        default_end   = date(2026, 12, 31)
    elif preset == "Last 30 days":
        default_start = today - timedelta(days=30)
        default_end   = today
    elif preset == "Last 90 days":
        default_start = today - timedelta(days=90)
        default_end   = today
    elif preset == "Last 6 months":
        default_start = today - timedelta(days=182)
        default_end   = today
    elif preset == "All time":
        default_start = date(2020, 1, 1)
        default_end   = today
    else:
        default_start = date(today.year, 1, 1)
        default_end   = today

    with period_col2:
        col_s, col_e = st.columns(2)
        start_dt = col_s.date_input("From", value=default_start)
        end_dt   = col_e.date_input("To",   value=default_end)

    start_str = start_dt.strftime("%Y-%m-%d")
    end_str   = end_dt.strftime("%Y-%m-%d")

    if start_dt > end_dt:
        st.error("Start date must be before end date.")
        st.stop()

    # ── Generate report ───────────────────────────────────────────────────────
    report = load_tax_report(start_str, end_str)

    if "error" in report:
        st.error(f"Tax engine error: {report['error']}")
    else:
        lots    = report.get("lots", [])
        summary = report.get("summary", {})

        if not lots:
            st.info(
                f"No closed trades found between {start_str} and {end_str}. "
                "Tax documentation will appear here once the bot closes positions."
            )
        else:
            # ── Summary cards ─────────────────────────────────────────────────
            st.markdown("### 📊 Summary")
            c1, c2, c3, c4 = st.columns(4)
            net  = summary.get("net_gain_loss", 0)
            net_color = "green" if net >= 0 else "red"
            net_sign  = "+" if net >= 0 else ""
            c1.metric("Net Capital Gain/Loss",
                      f"{net_sign}${abs(net):,.2f}",
                      delta=f"{net_sign}${abs(net):,.2f}",
                      delta_color="normal")
            c2.metric("Short-term Gains",
                      f"${summary.get('short_term_gains', 0):+,.2f}",
                      "Taxed as ordinary income")
            c3.metric("Long-term Gains",
                      f"${summary.get('long_term_gains', 0):+,.2f}",
                      "Preferential rate")
            c4.metric("Closed Lots",
                      summary.get("total_closed_lots", 0),
                      f"{summary.get('winning_trades',0)}W / {summary.get('losing_trades',0)}L")

            st.divider()
            c5, c6, c7, c8 = st.columns(4)
            c5.metric("Est. Short-term Tax",
                      f"${summary.get('estimated_st_tax', 0):,.2f}",
                      "@ 37% ordinary rate")
            c6.metric("Est. Long-term Tax",
                      f"${summary.get('estimated_lt_tax', 0):,.2f}",
                      "@ 15% cap gains rate")
            c7.metric("Est. Total Tax",
                      f"${summary.get('estimated_total_tax', 0):,.2f}",
                      "Consult a tax pro ⚠️")
            c8.metric("Wash Sales Detected",
                      summary.get("wash_sale_count", 0),
                      f"${summary.get('wash_sale_disallowed', 0):,.2f} disallowed")

            if summary.get("wash_sale_count", 0) > 0:
                st.warning(
                    f"⚠️ **{summary['wash_sale_count']} wash sale(s) detected.** "
                    "Losses from these trades are disallowed under IRS rules. "
                    "The disallowed loss is added to the cost basis of your replacement shares. "
                    "Consult a tax professional."
                )

            # ── Schedule D visual summary ────────────────────────────────────
            st.divider()
            st.markdown("### 📋 Schedule D — Capital Gains Summary")
            sched_data = {
                "Category":  ["Short-term (≤1 year)", "Long-term (>1 year)", "Net Total"],
                "Proceeds":  [
                    f"${summary.get('short_term_proceeds',0):,.2f}",
                    f"${summary.get('long_term_proceeds',0):,.2f}",
                    f"${summary.get('short_term_proceeds',0) + summary.get('long_term_proceeds',0):,.2f}",
                ],
                "Cost Basis": [
                    f"${summary.get('short_term_basis',0):,.2f}",
                    f"${summary.get('long_term_basis',0):,.2f}",
                    f"${summary.get('short_term_basis',0) + summary.get('long_term_basis',0):,.2f}",
                ],
                "Net Gain/Loss": [
                    f"${summary.get('short_term_gains',0):+,.2f}",
                    f"${summary.get('long_term_gains',0):+,.2f}",
                    f"${summary.get('net_gain_loss',0):+,.2f}",
                ],
                "Tax Rate": ["Ordinary income", "0% / 15% / 20%", "—"],
            }
            _df(pd.DataFrame(sched_data),
                         use_container_width=True, hide_index=True)

            # Gain/loss bar chart
            chart_data = [
                {"Category": "Short-term", "Amount": summary.get("short_term_gains", 0)},
                {"Category": "Long-term",  "Amount": summary.get("long_term_gains",  0)},
            ]
            fig_tax = go.Figure(go.Bar(
                x=[d["Category"] for d in chart_data],
                y=[d["Amount"]    for d in chart_data],
                marker_color=["#00c864" if d["Amount"] >= 0 else "#e03030"
                              for d in chart_data],
                text=[f"${d['Amount']:+,.2f}" for d in chart_data],
                textposition="outside",
            ))
            fig_tax.add_hline(y=0, line_color="gray", line_dash="dot")
            fig_tax.update_layout(
                title="Capital gains by term",
                height=300, yaxis_tickprefix="$", yaxis_tickformat=",.0f",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=40, b=20, l=60, r=20),
            )
            st.plotly_chart(fig_tax, use_container_width=True)

            # ── Form 8949 — Trade by trade ───────────────────────────────────
            st.divider()
            st.markdown("### 📄 Form 8949 — Trade-by-Trade Detail")
            st.caption(
                "Each row represents one closed tax lot. "
                "🔴 = loss  🟢 = gain  ⚠️ = wash sale (loss disallowed)"
            )

            term_filter = st.radio("Filter", ["All", "Short-term only", "Long-term only",
                                               "Gains only", "Losses only", "Wash sales only"],
                                   horizontal=True)

            filtered_lots = lots
            if term_filter == "Short-term only":
                filtered_lots = [l for l in lots if l["term"] == "SHORT"]
            elif term_filter == "Long-term only":
                filtered_lots = [l for l in lots if l["term"] == "LONG"]
            elif term_filter == "Gains only":
                filtered_lots = [l for l in lots if l["gain_loss"] > 0]
            elif term_filter == "Losses only":
                filtered_lots = [l for l in lots if l["gain_loss"] < 0]
            elif term_filter == "Wash sales only":
                filtered_lots = [l for l in lots if l["wash_sale"]]

            rows_8949 = []
            for l in filtered_lots:
                gl = l["gain_loss"]
                ws = l["wash_sale"]
                status = "⚠️ Wash" if ws else ("🟢" if gl >= 0 else "🔴")
                rows_8949.append({
                    "":            status,
                    "Symbol":      l["symbol"],
                    "Bought":      l["buy_date"],
                    "Sold":        l["sell_date"],
                    "Days":        l["hold_days"],
                    "Term":        l["term"],
                    "Shares":      f"{l['shares']:.4f}",
                    "Cost/Share":  f"${l['cost_per_share']:,.4f}",
                    "Sell Price":  f"${l['sell_price']:,.4f}",
                    "Proceeds":    f"${l['proceeds']:,.2f}",
                    "Basis":       f"${l['cost_basis']:,.2f}",
                    "Gain/Loss":   f"${gl:+,.2f}",
                    "Wash Adj":    f"${l['wash_sale_disallowed']:,.2f}" if ws else "—",
                })
            if rows_8949:
                _df(pd.DataFrame(rows_8949),
                             use_container_width=True, hide_index=True)
            else:
                st.info("No lots match the selected filter.")

            # ── Unrealized positions ──────────────────────────────────────────
            st.divider()
            st.markdown("### 📂 Open Positions — Unrealized (not yet taxable)")
            alpaca_data = load_alpaca()
            if alpaca_data and "error" not in alpaca_data:
                unrealized = te.get_open_positions_unrealized(alpaca_data)
                if unrealized:
                    df_unreal = pd.DataFrame(unrealized)
                    df_unreal["unrealized_pnl"] = df_unreal["unrealized_pnl"].apply(
                        lambda v: f"${v:+,.2f}")
                    df_unreal["unrealized_pct"] = df_unreal["unrealized_pct"].apply(
                        lambda v: f"{v:+.2f}%")
                    _df(df_unreal, use_container_width=True, hide_index=True)
                    st.caption("These gains/losses are unrealized and not taxable until sold.")
                else:
                    st.info("No open positions.")

            # ── Export buttons ────────────────────────────────────────────────
            st.divider()
            st.markdown("### 💾 Export")
            st.caption(
                "CSV files are compatible with TurboTax, H&R Block, and most "
                "tax software. Import under 'Investment Income' → 'Stocks, "
                "Crypto, Mutual Funds' → 'Enter a different way' → 'CSV import'."
            )

            exp1, exp2, exp3 = st.columns(3)

            # Form 8949 CSV
            csv_8949 = te.export_csv(lots)
            exp1.download_button(
                label="📥 Form 8949 CSV (all trades)",
                data=csv_8949,
                file_name=f"form_8949_{start_str}_to_{end_str}.csv",
                mime="text/csv",
                help="Trade-by-trade detail — import into TurboTax or H&R Block",
            )

            # Schedule D CSV
            csv_sched = te.export_schedule_d_csv(summary)
            exp2.download_button(
                label="📥 Schedule D Summary CSV",
                data=csv_sched,
                file_name=f"schedule_d_{start_str}_to_{end_str}.csv",
                mime="text/csv",
                help="Schedule D totals — short-term and long-term capital gains summary",
            )

            # Full trade history CSV (all columns)
            if lots:
                df_full = pd.DataFrame(lots)
                full_csv = df_full.to_csv(index=False)
                exp3.download_button(
                    label="📥 Full trade log CSV",
                    data=full_csv,
                    file_name=f"trade_log_{start_str}_to_{end_str}.csv",
                    mime="text/csv",
                    help="Complete trade history with all fields",
                )

            st.divider()
            st.caption(
                "⚠️ **Tax disclaimer:** These calculations are estimates based on "
                "trade records in this application. They are provided for informational "
                "purposes only and do not constitute tax advice. Tax rules vary by "
                "jurisdiction, filing status, and individual circumstances. "
                "Always consult a qualified tax professional before filing."
            )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 9 — REPORTS (Weekly / Monthly / Yearly + Sample Previews)
# ══════════════════════════════════════════════════════════════════════════════

with tab9:
    import reports as rpt
    from datetime import date as _date
    from datetime import timedelta as _td

    st.subheader("📊 Performance Reports")
    st.caption(
        "Generate weekly, monthly, and yearly reports. "
        "Reports are automatically sent to Telegram on schedule "
        "and saved as CSV files in the reports/ folder."
    )
    st.divider()

    # ── Manual report generation ──────────────────────────────────────────────
    st.markdown("### 🔄 Generate a Report Now")
    rc1, rc2, rc3 = st.columns(3)

    if rc1.button("📅 This Week", use_container_width=True):
        with st.spinner("Generating weekly report..."):
            try:
                stats = rpt.generate_report("weekly")
                st.success(f"✅ Weekly report generated — Return: {stats['period_return']:+.2f}%")
                rpt.send_report_telegram(stats)
            except Exception as e:
                st.error(f"Error: {e}")

    if rc2.button("🗓️ This Month", use_container_width=True):
        with st.spinner("Generating monthly report..."):
            try:
                stats = rpt.generate_report("monthly")
                st.success(f"✅ Monthly report generated — Return: {stats['period_return']:+.2f}%")
                rpt.send_report_telegram(stats)
            except Exception as e:
                st.error(f"Error: {e}")

    if rc3.button("📆 This Year", use_container_width=True):
        with st.spinner("Generating yearly report..."):
            try:
                stats = rpt.generate_report("yearly")
                st.success(f"✅ Yearly report generated — Return: {stats['period_return']:+.2f}%")
                rpt.send_report_telegram(stats)
            except Exception as e:
                st.error(f"Error: {e}")

    # Custom date range
    st.markdown("### 📐 Custom Date Range")
    cc1, cc2 = st.columns(2)
    c_start = cc1.date_input("From", value=_date.today() - _td(days=30), key="rpt_start")
    c_end   = cc2.date_input("To",   value=_date.today(), key="rpt_end")

    if st.button("Generate Custom Report"):
        with st.spinner("Generating..."):
            try:
                stats = rpt.generate_report(
                    "custom",
                    custom_start=str(c_start),
                    custom_end=str(c_end)
                )
                st.success(f"✅ Custom report: {stats['period_return']:+.2f}% return, "
                           f"{stats['win_rate']:.1f}% win rate")
                rpt.send_report_telegram(stats)
            except Exception as e:
                st.error(f"Error: {e}")

    st.divider()

    # ── Saved reports download ────────────────────────────────────────────────
    st.markdown("### 💾 Download Saved Reports")
    report_files = load_reports_list()
    real_reports = [f for f in report_files if "sample" not in os.path.basename(f)]

    if real_reports:
        for fpath in real_reports[:20]:
            fname = os.path.basename(fpath)
            with open(fpath) as f:
                csv_data = f.read()
            st.download_button(
                label=f"📥 {fname}",
                data=csv_data,
                file_name=fname,
                mime="text/csv",
                key=f"dl_{fname}",
            )
    else:
        st.info("No reports generated yet. Reports are automatically created weekly, monthly, and yearly, or generate one manually above.")

    st.divider()

    # ── Sample / Example reports ──────────────────────────────────────────────
    st.markdown("### 🔍 Sample Report Previews")
    st.caption("See exactly what your reports will look like once trading data accumulates.")

    sp1, sp2, sp3 = st.columns(3)

    for period, col, label in [
        ("weekly",  sp1, "📅 Sample Weekly"),
        ("monthly", sp2, "🗓️ Sample Monthly"),
        ("yearly",  sp3, "📆 Sample Yearly"),
    ]:
        if col.button(label, use_container_width=True, key=f"sample_{period}"):
            with st.spinner(f"Generating {period} sample..."):
                try:
                    rpt.generate_sample_report_csv(period)
                    st.session_state[f"show_sample_{period}"] = True
                except Exception as e:
                    st.error(f"Error: {e}")

        if st.session_state.get(f"show_sample_{period}"):
            import glob
            sample_files = glob.glob(
                os.path.join(DATA_DIR, "..", "reports", f"sample_{period}_*.csv"))
            for sf in sorted(sample_files):
                with open(sf) as f:
                    data = f.read()
                col.download_button(
                    f"📥 {os.path.basename(sf)}",
                    data=data,
                    file_name=os.path.basename(sf),
                    mime="text/csv",
                    key=f"sdl_{os.path.basename(sf)}",
                )

    st.divider()

    # ── Sample tax document previews ──────────────────────────────────────────
    st.markdown("### 🧾 Sample Tax Document Previews")
    st.caption(
        "Preview all tax forms with realistic sample data "
        "before your real trading history generates them."
    )

    tax_docs = {
        "Form 8949 (Trade-by-Trade)": "form_8949",
        "Schedule D (Summary)":       "schedule_d",
        "Full Trade Log":             "full_log",
    }

    if st.button("🔍 Generate All Sample Tax Documents", type="primary"):
        with st.spinner("Generating sample tax documents..."):
            try:
                docs = rpt.generate_sample_tax_documents()
                st.session_state["sample_tax_docs"] = docs
                st.success(f"✅ {len(docs)} sample tax documents generated")
            except Exception as e:
                st.error(f"Error: {e}")

    if "sample_tax_docs" in st.session_state:
        docs = st.session_state["sample_tax_docs"]
        st.caption("⚠️ These are sample documents with example data for preview only.")

        for label, key in tax_docs.items():
            if key in docs:
                with st.expander(f"📄 Preview: {label}"):
                    lines = docs[key].split("\n")[:15]
                    st.code("\n".join(lines), language=None)
                st.download_button(
                    f"📥 Download {label} (Sample)",
                    data=docs[key],
                    file_name=f"sample_tax_{key}.csv",
                    mime="text/csv",
                    key=f"tax_dl_{key}",
                )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 10 — DEMOGRAPHICS
# ══════════════════════════════════════════════════════════════════════════════

with tab10:
    import demographics as demo
    import csv as _dcsv
    import io as _dio
    import zipfile as _dzf
    from datetime import date as _date2, timedelta as _td2

    st.subheader("📐 Portfolio Demographics")
    st.caption("Visual breakdown of your trading performance. Download any chart as CSV for Excel graphing.")
    st.divider()

    dc1, dc2 = st.columns([2, 3])
    period_sel = dc1.selectbox("Time period", [
        "All time","This week","This month","This year","Custom range"])

    today2 = _date2.today()
    if period_sel == "This week":
        d_period, d_start, d_end = "weekly", None, None
        period_label = f"Week ending {today2}"
    elif period_sel == "This month":
        d_period, d_start, d_end = "monthly", None, None
        period_label = today2.strftime("%B %Y")
    elif period_sel == "This year":
        d_period, d_start, d_end = "yearly", None, None
        period_label = str(today2.year)
    elif period_sel == "Custom range":
        d_period = "custom"
        col_s2, col_e2 = dc2.columns(2)
        d_start = str(col_s2.date_input("From", value=today2 - _td2(days=30), key="demo_start2"))
        d_end   = str(col_e2.date_input("To",   value=today2, key="demo_end2"))
        period_label = f"{d_start} to {d_end}"
    else:
        d_period, d_start, d_end = "all", None, None
        period_label = "All Time"

    def _make_csv(headers, rows):
        buf = _dio.StringIO()
        w = _dcsv.writer(buf)
        w.writerow(headers)
        for row in rows:
            w.writerow(row)
        return buf.getvalue()

    d_trades2, d_equity2 = load_demographics(d_period, d_start, d_end)
    d_sells2 = [t for t in d_trades2 if t.get("action") == "SELL" and "pnl" in t]

    if not d_trades2:
        st.info("No trading data for this period. Demographics appear once the bot has closed trades.")
    else:
        st.caption(f"Analyzing {len(d_trades2)} trades ({len(d_sells2)} closed) — {period_label}")
        st.divider()

        # Portfolio over time
        st.markdown("### 📈 Portfolio Value Over Time")
        gran = st.radio("Granularity", ["daily","weekly","monthly"], horizontal=True, key="d_gran")
        td = demo.pnl_over_time(d_equity2, gran)
        if td["dates"]:
            sv = td["values"][0] if td["values"] else 1000
            colors_t = ["#00c864" if v >= sv else "#e03030" for v in td["values"]]
            fig_t = go.Figure(go.Bar(x=td["dates"], y=td["returns"],
                marker_color=colors_t,
                hovertemplate="%{x}<br>Return: %{y:+.2f}%<extra></extra>"))
            fig_t.add_hline(y=0, line_dash="dot", line_color="gray")
            fig_t.update_layout(height=300, yaxis_ticksuffix="%",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=20,b=0,l=40,r=10))
            st.plotly_chart(fig_t, use_container_width=True)
            csv_t = _make_csv(["Date","Value ($)","Return (%)"],
                zip(td["dates"], td["values"], td["returns"]))
            st.download_button("📥 Portfolio Over Time CSV", csv_t,
                f"portfolio_time_{period_label}.csv", "text/csv", key="d_t")
        st.divider()

        # P&L by symbol
        st.markdown("### 🏷️ P&L by Symbol")
        sd = demo.pnl_by_symbol(d_trades2)
        if sd["symbols"]:
            fig_s = px.bar(x=sd["symbols"], y=sd["pnl"],                color_continuous_scale=["#e03030","#f39c12","#00c864"],
                text=[f"${v:+,.2f}" for v in sd["pnl"]])
            fig_s.update_traces(textposition="outside")
            fig_s.add_hline(y=0, line_dash="dot", line_color="gray")
            fig_s.update_layout(height=300, showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=20,b=0,l=40,r=10))
            st.plotly_chart(fig_s, use_container_width=True)
            csv_s = _make_csv(["Symbol","P&L ($)","Trades","Win Rate (%)"],
                zip(sd["symbols"], sd["pnl"], sd["trades"], sd["win_rate"]))
            st.download_button("📥 P&L by Symbol CSV", csv_s,
                f"pnl_symbol_{period_label}.csv", "text/csv", key="d_s")
        st.divider()

        # Monthly summary
        st.markdown("### 🗓️ Monthly Performance")
        ms = demo.monthly_summary(d_trades2, d_equity2)
        if ms["months"]:
            fig_m = go.Figure()
            mc = ["#00c864" if p >= 0 else "#e03030" for p in ms["pnl"]]
            fig_m.add_trace(go.Bar(x=ms["months"], y=ms["pnl"],
                marker_color=mc, name="P&L ($)"))
            fig_m.add_trace(go.Scatter(x=ms["months"], y=ms["win_rate"],
                mode="lines+markers", name="Win Rate (%)", yaxis="y2",
                line=dict(color="#4a9eff", width=2)))
            fig_m.update_layout(height=300,
                yaxis=dict(tickprefix="$"),
                yaxis2=dict(overlaying="y", side="right", ticksuffix="%", range=[0,100]),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h"), margin=dict(t=20,b=0,l=60,r=60))
            st.plotly_chart(fig_m, use_container_width=True)
            csv_m = _make_csv(["Month","P&L ($)","Trades","Win Rate (%)"],
                zip(ms["months"], ms["pnl"], ms["trades"], ms["win_rate"]))
            st.download_button("📥 Monthly Summary CSV", csv_m,
                f"monthly_{period_label}.csv", "text/csv", key="d_m")
        st.divider()

        # Best trading hours
        st.markdown("### ⏰ Best Trading Hours (ET)")
        th = demo.trades_by_hour(d_trades2)
        hc = ["#00c864" if p >= 0 else "#e03030" for p in th["avg_pnl"]]
        fig_h = go.Figure(go.Bar(x=th["hours"], y=th["avg_pnl"], marker_color=hc,
            hovertemplate="%{x}<br>Avg P&L: $%{y:+,.2f}<extra></extra>"))
        fig_h.add_hline(y=0, line_dash="dot", line_color="gray")
        fig_h.update_layout(height=280, yaxis_tickprefix="$",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=20,b=0,l=60,r=10))
        st.plotly_chart(fig_h, use_container_width=True)
        csv_h = _make_csv(["Hour (ET)","Avg P&L ($)","Count"],
            zip(th["hours"], th["avg_pnl"], th["count"]))
        st.download_button("📥 Hours CSV", csv_h,
            f"hours_{period_label}.csv", "text/csv", key="d_h")
        st.divider()

        # Confidence vs outcome
        st.markdown("### 🎯 AI Confidence vs Trade Outcome")
        co = demo.confidence_vs_outcome(d_trades2)
        if co["confidence"]:
            fig_c = px.scatter(x=co["confidence"], y=co["pnl"],                color_continuous_scale=["#e03030","#f39c12","#00c864"],
                labels={"x":"Confidence (%)","y":"P&L ($)"})
            fig_c.add_hline(y=0, line_dash="dot", line_color="gray")
            fig_c.add_vline(x=65, line_dash="dash", line_color="#4a9eff",
                annotation_text="Min threshold")
            fig_c.update_layout(height=300, showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=20,b=0,l=60,r=10))
            st.plotly_chart(fig_c, use_container_width=True)
            csv_c = _make_csv(["Symbol","Confidence (%)","P&L ($)"],
                zip(co["symbols"], co["confidence"], co["pnl"]))
            st.download_button("📥 Confidence CSV", csv_c,
                f"confidence_{period_label}.csv", "text/csv", key="d_c")
        st.divider()

        # Export all as zip
        st.markdown("### 💾 Export All as CSV Package")
        if st.button("📦 Download All Charts as ZIP", type="primary", key="d_zip"):
            with st.spinner("Generating..."):
                try:
                    all_csvs = demo.export_demographics_csv(d_trades2, d_equity2, period_label)
                    zb = _dio.BytesIO()
                    with _dzf.ZipFile(zb, "w") as zf:
                        for n, cd in all_csvs.items():
                            zf.writestr(f"{n}.csv", cd)
                    st.download_button("📥 Download ZIP", zb.getvalue(),
                        f"demographics_{period_label}.zip", "application/zip", key="d_zip2")
                    st.success(f"Ready — {len(all_csvs)} files")
                except Exception as e:
                    st.error(f"Error: {e}")


# ── Auto-refresh ──────────────────────────────────────────────────────────────

# Show toast for the most recent notification
_last_notif_key = "last_notif_ts"
_notifs = load_notifications()
if _notifs:
    _latest = _notifs[-1]
    _latest_ts = _latest.get("ts","")
    if st.session_state.get(_last_notif_key) != _latest_ts:
        st.session_state[_last_notif_key] = _latest_ts
        _level = _latest.get("level","info")
        _msg   = f"{_latest.get('icon','')} **{_latest.get('title','')}** — {_latest.get('message','')[:100]}"
        if _level == "success":
            st.toast(_msg, icon="✅")
        elif _level == "error":
            st.toast(_msg, icon="🚨")
        elif _level == "warning":
            st.toast(_msg, icon="⚠️")
        else:
            st.toast(_msg, icon="ℹ️")

if auto_refresh:
    time.sleep(15)
    st.cache_data.clear()
    st.rerun()
