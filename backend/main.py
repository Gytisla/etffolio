"""
ETFfolio — FastAPI backend
Serves: REST API + static frontend (built React app)
Runs inside HA addon container on ingress port 8099
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from . import database as db
from .models import (
    HoldingCreate, HoldingUpdate, HoldingResponse,
    PortfolioSummary, PortfolioHistoryPoint, FetchResult
)
from .prices import fetch_and_store, fetch_all_holdings, TICKER_MAP
from .scheduler import start_scheduler, stop_scheduler

# ─── Logging ──────────────────────────────────────────────────
log_level = os.environ.get("LOG_LEVEL", "info").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger("etffolio")


# ─── Lifespan ─────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ETFfolio starting up...")
    await db.init_db()
    start_scheduler()
    yield
    stop_scheduler()
    logger.info("ETFfolio shutting down.")


# ─── App ──────────────────────────────────────────────────────

app = FastAPI(
    title="ETFfolio",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS (needed for HA ingress iframe)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Holdings API ─────────────────────────────────────────────

@app.get("/api/holdings")
async def list_holdings() -> list[dict]:
    """Get all holdings with computed P/L fields."""
    holdings = await db.get_holdings()
    enriched = []
    for h in holdings:
        ticker = h["ticker"]
        adj_shares = await db.get_adjusted_shares(ticker, h["shares"], h["purchase_date"])
        latest = await db.get_latest_price(ticker)
        cur_price = latest["close"] if latest else None
        meta = await db.get_etf_metadata(ticker)

        cost_basis = h["shares"] * h["purchase_price"]
        fees = h.get("brokerage_fee", 0) + h.get("stamp_duty", 0)
        total_cost = cost_basis + fees
        value = adj_shares * cur_price if cur_price else None
        pnl = (value - total_cost) if value else None
        pnl_pct = (pnl / total_cost * 100) if (pnl is not None and total_cost > 0) else None

        enriched.append({
            **h,
            "adjusted_shares": round(adj_shares, 6),
            "current_price": cur_price,
            "current_value": round(value, 2) if value else None,
            "cost_basis": round(cost_basis, 2),
            "total_cost": round(total_cost, 2),
            "pnl": round(pnl, 2) if pnl is not None else None,
            "pnl_pct": round(pnl_pct, 2) if pnl_pct is not None else None,
            "etf_name": meta["name"] if meta else None,
            "category": meta["category"] if meta else None,
        })
    return enriched


@app.post("/api/holdings")
async def create_holding(data: HoldingCreate) -> dict:
    """Add a new holding. Auto-fetches prices if not yet in DB."""
    h = await db.add_holding(
        ticker=data.ticker.upper(),
        shares=data.shares,
        purchase_date=data.purchase_date,
        purchase_price=data.purchase_price,
        brokerage_fee=data.brokerage_fee,
        stamp_duty=data.stamp_duty,
        notes=data.notes,
    )
    # Trigger price fetch for this ticker if we don't have data
    latest = await db.get_latest_price(data.ticker.upper())
    if not latest:
        await fetch_and_store(data.ticker.upper())
    return h


@app.put("/api/holdings/{holding_id}")
async def update_holding_endpoint(holding_id: int, data: HoldingUpdate) -> dict:
    result = await db.update_holding(holding_id, **data.model_dump(exclude_none=True))
    if not result:
        raise HTTPException(404, "Holding not found")
    return result


@app.delete("/api/holdings/{holding_id}")
async def delete_holding_endpoint(holding_id: int):
    ok = await db.delete_holding(holding_id)
    if not ok:
        raise HTTPException(404, "Holding not found")
    return {"deleted": True}


# ─── Portfolio Summary ────────────────────────────────────────

@app.get("/api/portfolio/summary")
async def portfolio_summary() -> dict:
    """Aggregate portfolio stats."""
    holdings = await db.get_holdings()
    total_value = 0
    total_cost = 0
    total_fees = 0
    day_change = 0

    for h in holdings:
        adj = await db.get_adjusted_shares(h["ticker"], h["shares"], h["purchase_date"])
        latest = await db.get_latest_price(h["ticker"])
        if not latest:
            continue
        cur = latest["close"]

        # Get previous day price
        prices = await db.get_prices(h["ticker"])
        prev = prices[-2]["close"] if len(prices) >= 2 else cur

        fees = h.get("brokerage_fee", 0) + h.get("stamp_duty", 0)
        total_value += adj * cur
        total_cost += h["shares"] * h["purchase_price"] + fees
        total_fees += fees
        day_change += adj * (cur - prev)

    pnl = total_value - total_cost
    tickers = set(h["ticker"] for h in holdings)

    return {
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "total_pnl": round(pnl, 2),
        "total_pnl_pct": round(pnl / total_cost * 100, 2) if total_cost > 0 else 0,
        "day_change": round(day_change, 2),
        "day_change_pct": round(
            day_change / (total_value - day_change) * 100, 2
        ) if (total_value - day_change) > 0 else 0,
        "total_fees": round(total_fees, 2),
        "num_positions": len(tickers),
        "num_records": len(holdings),
        "currency": os.environ.get("CURRENCY", "EUR"),
    }


# ─── Position-level detail (aggregated by ticker) ────────────

@app.get("/api/portfolio/positions")
async def portfolio_positions() -> list[dict]:
    """
    Aggregate all holdings by ticker. For each position compute:
    total P/L, day / week / month / 3-month / 6-month / 1-year change.
    """
    holdings = await db.get_holdings()
    if not holdings:
        return []

    # Group by ticker
    grouped: dict[str, list[dict]] = {}
    for h in holdings:
        grouped.setdefault(h["ticker"], []).append(h)

    today = datetime.now()
    period_offsets = {
        "day":   timedelta(days=1),
        "week":  timedelta(days=7),
        "month": timedelta(days=30),
        "3month": timedelta(days=90),
        "6month": timedelta(days=180),
        "year":  timedelta(days=365),
    }

    results = []
    for ticker, rows in grouped.items():
        latest = await db.get_latest_price(ticker)
        if not latest:
            continue
        cur_price = latest["close"]
        meta = await db.get_etf_metadata(ticker)

        total_shares = 0
        total_cost = 0
        total_fees = 0
        for h in rows:
            adj = await db.get_adjusted_shares(ticker, h["shares"], h["purchase_date"])
            total_shares += adj
            fees = h.get("brokerage_fee", 0) + h.get("stamp_duty", 0)
            total_cost += h["shares"] * h["purchase_price"] + fees
            total_fees += fees

        current_value = total_shares * cur_price
        total_pnl = current_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

        # Compute period changes using historical prices
        changes = {}
        for period_name, offset in period_offsets.items():
            ref_date = (today - offset).strftime("%Y-%m-%d")
            ref_price = await db.get_price_on_date(ticker, ref_date)
            if ref_price is not None and ref_price > 0:
                price_change = cur_price - ref_price
                price_change_pct = (price_change / ref_price) * 100
                value_change = total_shares * price_change
                changes[period_name] = {
                    "value": round(value_change, 2),
                    "pct": round(price_change_pct, 2),
                }
            else:
                changes[period_name] = None

        results.append({
            "ticker": ticker,
            "etf_name": meta["name"] if meta else None,
            "category": meta["category"] if meta else None,
            "total_shares": round(total_shares, 6),
            "current_price": cur_price,
            "current_value": round(current_value, 2),
            "total_cost": round(total_cost, 2),
            "total_fees": round(total_fees, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "changes": changes,
            "num_lots": len(rows),
        })

    results.sort(key=lambda r: r["current_value"], reverse=True)
    return results


# ─── Portfolio History (for charts) ──────────────────────────

@app.get("/api/portfolio/history")
async def portfolio_history(
    range: str = Query("1Y", regex="^(1D|1W|1M|3M|6M|1Y|ALL)$")
) -> list[dict]:
    """
    Compute daily portfolio value + cost basis over time.
    Used for the main performance chart.
    """
    days_map = {"1D": 1, "1W": 7, "1M": 30, "3M": 90, "6M": 180, "1Y": 365, "ALL": 3650}
    days = days_map.get(range, 365)
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    holdings = await db.get_holdings()
    if not holdings:
        return []

    # Gather all price histories
    tickers = list(set(h["ticker"] for h in holdings))
    price_maps = {}
    all_dates = set()
    for t in tickers:
        prices = await db.get_prices(t, start_date=start)
        pm = {p["date"]: p["close"] for p in prices}
        price_maps[t] = pm
        all_dates.update(pm.keys())

    if not all_dates:
        return []

    # Build daily portfolio values
    results = []
    for date_str in sorted(all_dates):
        total_value = 0
        total_cost = 0
        for h in holdings:
            if h["purchase_date"] > date_str:
                continue
            adj = await db.get_adjusted_shares(h["ticker"], h["shares"], h["purchase_date"])
            pm = price_maps.get(h["ticker"], {})
            # Find price on or before this date
            price = pm.get(date_str)
            if price is None:
                # Find closest earlier date
                earlier = [d for d in pm if d <= date_str]
                if earlier:
                    price = pm[max(earlier)]
            if price is not None:
                total_value += adj * price
                total_cost += h["shares"] * h["purchase_price"]

        if total_value > 0:
            results.append({
                "date": date_str,
                "value": round(total_value, 2),
                "cost": round(total_cost, 2),
            })

    return results


# ─── Price Data ───────────────────────────────────────────────

@app.get("/api/prices/{ticker}")
async def get_price_history(
    ticker: str,
    start: str = None,
    end: str = None,
) -> list[dict]:
    return await db.get_prices(ticker.upper(), start, end)


@app.get("/api/prices/{ticker}/latest")
async def get_latest(ticker: str) -> dict:
    p = await db.get_latest_price(ticker.upper())
    if not p:
        raise HTTPException(404, f"No price data for {ticker}")
    return p


# ─── Fetch / Refresh ─────────────────────────────────────────

@app.post("/api/fetch/{ticker}")
async def trigger_fetch(ticker: str) -> dict:
    """Manually trigger a price fetch for a ticker."""
    return await fetch_and_store(ticker.upper())


@app.post("/api/fetch")
async def trigger_fetch_all() -> list[dict]:
    """Manually trigger price fetch for all held tickers."""
    return await fetch_all_holdings()


# ─── ETF Metadata ─────────────────────────────────────────────

@app.get("/api/etfs")
async def list_etfs() -> list[dict]:
    """List all known ETFs (from metadata table)."""
    return await db.get_etf_metadata()


@app.get("/api/etfs/known")
async def known_tickers() -> dict:
    """Return the pre-configured ticker map (for autocomplete)."""
    return {
        "tickers": TICKER_MAP,
        "description": "Short ticker → Yahoo Finance ticker mapping"
    }


# ─── Splits ───────────────────────────────────────────────────

@app.get("/api/splits/{ticker}")
async def get_splits(ticker: str) -> list[dict]:
    return await db.get_splits(ticker.upper())


# ─── Health ───────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": "0.1.0",
        "db": os.path.exists(db.DB_PATH),
    }


# ─── Static frontend serving ─────────────────────────────────
# The built React app is served from /app/frontend/dist
# All non-API routes fall through to index.html (SPA routing)

FRONTEND_DIR = Path("/app/frontend/dist")

if (FRONTEND_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        # Try to serve the exact file
        file_path = FRONTEND_DIR / path
        if file_path.is_file():
            return FileResponse(file_path)
        # Otherwise serve index.html (SPA catch-all)
        return FileResponse(FRONTEND_DIR / "index.html")
else:
    @app.get("/")
    async def no_frontend():
        return JSONResponse({
            "message": "ETFfolio API is running. Frontend not built yet.",
            "api_docs": "/docs",
            "health": "/api/health",
        })
