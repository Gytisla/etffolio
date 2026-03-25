#!/usr/bin/env python3
"""
ETFfolio — Local development server
Run without Home Assistant. Just needs Python 3.10+

Usage:
    pip install -r backend/requirements.txt
    python run_local.py

Options (env vars):
    PRICE_SOURCE=both              yfinance | alpha_vantage | both
    ALPHA_VANTAGE_KEY=your_key     Required if using alpha_vantage
    UPDATE_INTERVAL=6              Hours between auto-fetches
    CURRENCY=EUR                   EUR | USD | GBP | CHF
    LOG_LEVEL=info                 debug | info | warning | error
    DB_PATH=./data/etffolio.db     SQLite database location
    PORT=8099                      Server port
"""

import os
import sys

# ─── Defaults (mimic what bashio would provide in HA) ─────────
os.environ.setdefault("PRICE_SOURCE", "both")
os.environ.setdefault("ALPHA_VANTAGE_KEY", "")
os.environ.setdefault("UPDATE_INTERVAL", "6")
os.environ.setdefault("CURRENCY", "EUR")
os.environ.setdefault("LOG_LEVEL", "info")
os.environ.setdefault("DB_PATH", os.path.join(os.path.dirname(__file__), "data", "etffolio.db"))

# Ensure data directory exists
db_dir = os.path.dirname(os.environ["DB_PATH"])
os.makedirs(db_dir, exist_ok=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8099"))

    print(f"""
╔══════════════════════════════════════════════╗
║           ETFfolio — Local Mode              ║
╠══════════════════════════════════════════════╣
║  API:       http://localhost:{port}             ║
║  Swagger:   http://localhost:{port}/docs         ║
║  DB:        {os.environ['DB_PATH']:<33s}║
║  Source:    {os.environ['PRICE_SOURCE']:<33s}║
║  Currency:  {os.environ['CURRENCY']:<33s}║
║  Interval:  {os.environ['UPDATE_INTERVAL']}h{' ' * 30}║
╚══════════════════════════════════════════════╝
""")

    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level=os.environ["LOG_LEVEL"],
    )
