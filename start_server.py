"""
start_server.py — Direct server launcher (no browser wizard needed).
Loads .env, shows key confirmation in terminal, then starts the bot.
"""
import os
import sys
import time
import json

# Load .env
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()
    print("✅ Loaded .env credentials")
else:
    print("⚠️  No .env file found — create one at:", env_path)

# Run terminal key confirmation
import server_confirm
if not server_confirm.run_confirmation():
    sys.exit(0)

# Create launch flag to bypass wizard
data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(data_dir, exist_ok=True)
flag = os.path.join(data_dir, "launch_authorized.json")
with open(flag, "w") as f:
    json.dump({
        "authorized":    True,
        "timestamp":     time.time(),
        "alpaca_key":    os.environ.get("ALPACA_API_KEY", ""),
        "alpaca_secret": os.environ.get("ALPACA_SECRET_KEY", ""),
        "tg_token":      os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "tg_chat_id":    os.environ.get("TELEGRAM_CHAT_ID", ""),
        "groq_key":      os.environ.get("GROQ_API_KEY", ""),
        "ollama_host":   "http://localhost:11434",
        "ollama_model":  "llama3.1",
        "balance":       1000.0,
        "max_positions": 4,
        "max_pct":       0.10,
        "min_pct":       0.05,
        "daily_loss":    50.0,
    }, f)

print("✅ Launch flag created — starting bot...")
os.execv(sys.executable, [sys.executable,
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")])
