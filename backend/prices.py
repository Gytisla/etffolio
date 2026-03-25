"""
Price fetcher with dual-source support:
  1. yfinance (primary, free, no API key)
  2. Alpha Vantage (fallback, free tier 25 req/day)

Handles: daily OHLCV prices, stock splits, ETF metadata.
European UCITS ETFs use suffixes: .AS (Amsterdam), .DE (XETRA), .L (London)
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import httpx

from . import database as db

logger = logging.getLogger(__name__)

# ─── Ticker suffix mapping for Yahoo Finance ─────────────────
# European ETFs need exchange suffixes for yfinance
EXCHANGE_SUFFIXES = {
    "Euronext Amsterdam": ".AS",
    "XETRA": ".DE",
    "LSE": ".L",
    "SIX": ".SW",
    "Borsa Italiana": ".MI",
    "Euronext Paris": ".PA",
}

# Known European UCITS ETFs and their Yahoo tickers
TICKER_MAP = {
    "EMIM": "EMIM.AS",
    "IWDA": "IWDA.AS",
    "VWCE": "VWCE.DE",
    "IUSN": "IUSN.DE",
    "EUNL": "EUNL.DE",
    "IS3N": "IS3N.DE",
    "SUSW": "SUSW.AS",
    "CSPX": "CSPX.L",
    "AGGH": "AGGH.AS",
    "IEMA": "IEMA.L",
}


def get_yahoo_ticker(ticker: str) -> str:
    """Resolve a short ticker to its Yahoo Finance equivalent."""
    upper = ticker.upper()
    if upper in TICKER_MAP:
        return TICKER_MAP[upper]
    # If it already has a suffix, use as-is
    if "." in upper:
        return upper
    # Default: try Amsterdam
    return f"{upper}.AS"


# ─── yfinance fetcher ─────────────────────────────────────────

async def fetch_yfinance(ticker: str, period: str = "2y") -> dict:
    """
    Fetch price history + splits + metadata via yfinance.
    Returns: {prices: [...], splits: [...], metadata: {...}}
    
    Note: yfinance is synchronous, so we run it in a thread.
    """
    import asyncio
    import yfinance as yf

    yahoo_ticker = get_yahoo_ticker(ticker)
    logger.info(f"[yfinance] Fetching {ticker} as {yahoo_ticker}, period={period}")

    def _fetch():
        try:
            etf = yf.Ticker(yahoo_ticker)

            # Price history
            hist = etf.history(period=period, auto_adjust=True)
            prices = []
            for date_idx, row in hist.iterrows():
                prices.append({
                    "date": date_idx.strftime("%Y-%m-%d"),
                    "open": round(float(row.get("Open", 0)), 4),
                    "high": round(float(row.get("High", 0)), 4),
                    "low": round(float(row.get("Low", 0)), 4),
                    "close": round(float(row.get("Close", 0)), 4),
                    "volume": int(row.get("Volume", 0)),
                })

            # Splits
            splits_data = etf.splits
            splits = []
            if splits_data is not None and len(splits_data) > 0:
                for date_idx, ratio in splits_data.items():
                    splits.append({
                        "date": date_idx.strftime("%Y-%m-%d"),
                        "ratio": float(ratio),
                    })

            # Metadata
            info = etf.info or {}
            metadata = {
                "name": info.get("shortName", ""),
                "full_name": info.get("longName", ""),
                "isin": info.get("isin", ""),
                "exchange": info.get("exchange", ""),
                "currency": info.get("currency", "EUR"),
                "ter": info.get("annualReportExpenseRatio"),
                "category": info.get("category", ""),
            }

            return {"prices": prices, "splits": splits, "metadata": metadata}

        except Exception as e:
            logger.error(f"[yfinance] Error fetching {yahoo_ticker}: {e}")
            return {"prices": [], "splits": [], "metadata": {}, "error": str(e)}

    return await asyncio.to_thread(_fetch)


# ─── Alpha Vantage fetcher ────────────────────────────────────

async def fetch_alpha_vantage(ticker: str, api_key: str,
                               outputsize: str = "full") -> dict:
    """
    Fetch daily prices from Alpha Vantage.
    Free tier: 25 requests/day.
    """
    yahoo_ticker = get_yahoo_ticker(ticker)
    # Alpha Vantage uses different symbols — strip the suffix
    av_symbol = yahoo_ticker.replace(".AS", ".AMS").replace(".DE", ".DEX")

    logger.info(f"[alpha_vantage] Fetching {ticker} as {av_symbol}")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                "https://www.alphavantage.co/query",
                params={
                    "function": "TIME_SERIES_DAILY",
                    "symbol": av_symbol,
                    "outputsize": outputsize,
                    "apikey": api_key,
                }
            )
            data = resp.json()

        if "Error Message" in data:
            return {"prices": [], "error": data["Error Message"]}
        if "Note" in data:
            return {"prices": [], "error": f"Rate limited: {data['Note']}"}

        ts = data.get("Time Series (Daily)", {})
        prices = []
        for date_str, vals in sorted(ts.items()):
            prices.append({
                "date": date_str,
                "open": round(float(vals["1. open"]), 4),
                "high": round(float(vals["2. high"]), 4),
                "low": round(float(vals["3. low"]), 4),
                "close": round(float(vals["4. close"]), 4),
                "volume": int(float(vals["5. volume"])),
            })

        return {"prices": prices, "splits": [], "metadata": {}}

    except Exception as e:
        logger.error(f"[alpha_vantage] Error: {e}")
        return {"prices": [], "splits": [], "metadata": {}, "error": str(e)}


# ─── Unified fetch + store ────────────────────────────────────

async def fetch_and_store(ticker: str, source: str = None,
                          api_key: str = None) -> dict:
    """
    Fetch prices using configured source(s), store in DB.
    source: 'yfinance', 'alpha_vantage', or 'both'
    """
    if source is None:
        source = os.environ.get("PRICE_SOURCE", "yfinance")
    if api_key is None:
        api_key = os.environ.get("ALPHA_VANTAGE_KEY", "")

    result = {"ticker": ticker, "source": None, "prices_stored": 0,
              "splits_stored": 0, "error": None}

    data = None

    # Try yfinance first (or only)
    if source in ("yfinance", "both"):
        data = await fetch_yfinance(ticker)
        if data["prices"]:
            result["source"] = "yfinance"
        elif source == "both":
            logger.warning(f"[yfinance] No data for {ticker}, falling back to Alpha Vantage")
            data = None

    # Try Alpha Vantage (fallback or only)
    if data is None or not data.get("prices"):
        if source in ("alpha_vantage", "both") and api_key:
            data = await fetch_alpha_vantage(ticker, api_key)
            if data["prices"]:
                result["source"] = "alpha_vantage"

    if not data or not data.get("prices"):
        err = data.get("error", "No data returned") if data else "No source available"
        result["error"] = err
        await db.log_fetch(ticker, source, "error", err)
        return result

    # Store prices
    await db.upsert_prices(ticker, data["prices"])
    result["prices_stored"] = len(data["prices"])

    # Store splits
    if data.get("splits"):
        await db.upsert_splits(ticker, data["splits"])
        result["splits_stored"] = len(data["splits"])

    # Store metadata
    if data.get("metadata"):
        meta = {k: v for k, v in data["metadata"].items() if v}
        if meta:
            await db.upsert_etf_metadata(ticker, **meta)

    await db.log_fetch(ticker, result["source"], "success",
                       f"{result['prices_stored']} prices, {result['splits_stored']} splits")

    logger.info(f"[{result['source']}] Stored {result['prices_stored']} prices, "
                f"{result['splits_stored']} splits for {ticker}")
    return result


async def fetch_all_holdings():
    """Fetch prices for all tickers that have holdings."""
    holdings = await db.get_holdings()
    tickers = list(set(h["ticker"] for h in holdings))
    results = []
    for ticker in tickers:
        r = await fetch_and_store(ticker)
        results.append(r)
    return results
