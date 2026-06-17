"""
crypto_regime.py — Crypto-specific overnight regime detection.

During market hours, the main regime.py uses SPY data which is
accurate and timely. Overnight (when SPY doesn't trade), this
module takes over for crypto decisions using:

  1. Crypto Fear & Greed Index (free, always live)
  2. Bitcoin 24h momentum (free via CoinGecko)
  3. BTC dominance trend (free via CoinGecko)
  4. Cross-asset crypto volatility

Returns the same regime format as regime.py so brain.py
doesn't need to know which source was used.
"""

import logging
import time
import requests

log = logging.getLogger(__name__)

_cache: dict = {"ts": 0, "regime": "RANGING", "detail": {}}
CACHE_TTL = 900   # 15 minutes — matches crypto scan interval


def detect_crypto_regime() -> tuple[str, dict]:
    """
    Returns (regime_name, detail_dict) using crypto-native data.
    Falls back to RANGING if all sources fail.
    """
    now = time.time()
    if _cache["ts"] > now - CACHE_TTL:
        return _cache["regime"], _cache["detail"]

    try:
        fg    = _fetch_crypto_fear_greed()
        btc   = _fetch_btc_momentum()
        regime, detail = _classify(fg, btc)

        _cache.update({"ts": now, "regime": regime, "detail": detail})
        log.info(
            f"  🪙 Crypto regime: {regime} | "
            f"F&G={fg.get('score',50)} ({fg.get('label','?')}) | "
            f"BTC 24h={btc.get('change_24h',0):+.1f}%"
        )
        return regime, detail

    except Exception as e:
        log.warning(f"Crypto regime detection failed: {e} — defaulting to RANGING")
        return "RANGING", {}


def _fetch_crypto_fear_greed() -> dict:
    """Crypto Fear & Greed Index — always live, no API key needed."""
    try:
        r = requests.get(
            "https://api.alternative.me/fng/?limit=1",
            timeout=8
        )
        r.raise_for_status()
        data  = r.json()["data"][0]
        score = int(data["value"])
        label = data["value_classification"]
        return {"score": score, "label": label}
    except Exception as e:
        log.debug(f"Crypto F&G fetch failed: {e}")
        return {"score": 50, "label": "Neutral"}


def _fetch_btc_momentum() -> dict:
    """Bitcoin 24h and 7d momentum from CoinGecko free tier."""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/bitcoin"
            "?localization=false&tickers=false"
            "&community_data=false&developer_data=false",
            timeout=10,
        )
        r.raise_for_status()
        mkt = r.json().get("market_data", {})
        return {
            "change_24h": mkt.get("price_change_percentage_24h", 0) or 0,
            "change_7d":  mkt.get("price_change_percentage_7d",  0) or 0,
            "price":      mkt.get("current_price", {}).get("usd", 0),
        }
    except Exception as e:
        log.debug(f"BTC momentum fetch failed: {e}")
        return {"change_24h": 0, "change_7d": 0, "price": 0}


def _classify(fg: dict, btc: dict) -> tuple[str, dict]:
    """
    Classify crypto market regime from fear/greed + BTC momentum.

    Fear & Greed scale:
      0-24   = Extreme Fear  → TRENDING_BEAR (panic selling)
      25-44  = Fear          → RANGING (cautious)
      45-55  = Neutral       → RANGING
      56-74  = Greed         → TRENDING_BULL
      75-100 = Extreme Greed → VOLATILE (euphoria, high risk)

    BTC momentum adjustments:
      > +5% 24h  → push toward BULL
      < -5% 24h  → push toward BEAR
      > ±10% 24h → VOLATILE regardless
    """
    score      = fg.get("score", 50)
    change_24h = btc.get("change_24h", 0)
    change_7d  = btc.get("change_7d",  0)

    # Extreme volatility override
    if abs(change_24h) > 10:
        regime = "VOLATILE"
    elif score <= 24:
        regime = "TRENDING_BEAR"
    elif score >= 75:
        regime = "VOLATILE"    # extreme greed = euphoria = risky
    elif score >= 56 and change_24h > 1:
        regime = "TRENDING_BULL"
    elif score <= 44 and change_24h < -1:
        regime = "TRENDING_BEAR"
    else:
        regime = "RANGING"

    # BTC momentum adjustment
    if regime != "VOLATILE":
        if change_24h > 5 and regime == "RANGING":
            regime = "TRENDING_BULL"
        elif change_24h < -5 and regime == "RANGING":
            regime = "TRENDING_BEAR"

    detail = {
        "regime":        regime,
        "fg_score":      score,
        "fg_label":      fg.get("label", "Neutral"),
        "btc_change_24h":round(change_24h, 2),
        "btc_change_7d": round(change_7d,  2),
        "source":        "crypto_fg",
    }

    return regime, detail


def is_market_hours() -> bool:
    """Returns True if US stock market is currently open."""
    try:
        import timeofday
        return timeofday.is_market_open()
    except Exception:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        # Rough ET market hours check
        hour_et = (now.hour - 5) % 24
        return now.weekday() < 5 and 9 <= hour_et < 16


def get_regime_for_crypto() -> tuple[str, dict]:
    """
    Smart regime selector for crypto:
    - During market hours: use SPY-based regime (more accurate)
    - Outside market hours: use crypto Fear & Greed (always live)
    """
    if is_market_hours():
        try:
            import regime as spy_regime
            r, d = spy_regime.detect_regime()
            d["source"] = "spy"
            return r, d
        except Exception:
            pass
    return detect_crypto_regime()
