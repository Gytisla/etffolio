"""Price fetcher with dual-source support for ETFfolio."""

import asyncio
import logging
from typing import Optional

import httpx

from .database import ETFfolioDB

_LOGGER = logging.getLogger(__name__)

# ─── Ticker suffix mapping for Yahoo Finance ─────────────────
EXCHANGE_SUFFIXES = {
    "Euronext Amsterdam": ".AS",
    "XETRA": ".DE",
    "LSE": ".L",
    "SIX": ".SW",
    "Borsa Italiana": ".MI",
    "Euronext Paris": ".PA",
}

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
    if "." in upper:
        return upper
    return f"{upper}.AS"


# ─── yfinance fetcher ─────────────────────────────────────────

async def fetch_yfinance(ticker: str, period: str = "2y") -> dict:
    """Fetch price history + splits + metadata via yfinance."""
    import yfinance as yf

    yahoo_ticker = get_yahoo_ticker(ticker)
    _LOGGER.info("[yfinance] Fetching %s as %s, period=%s", ticker, yahoo_ticker, period)

    def _fetch():
        try:
            etf = yf.Ticker(yahoo_ticker)
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

            splits_data = etf.splits
            splits = []
            if splits_data is not None and len(splits_data) > 0:
                for date_idx, ratio in splits_data.items():
                    splits.append({
                        "date": date_idx.strftime("%Y-%m-%d"),
                        "ratio": float(ratio),
                    })

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
            _LOGGER.error("[yfinance] Error fetching %s: %s", yahoo_ticker, e)
            return {"prices": [], "splits": [], "metadata": {}, "error": str(e)}

    return await asyncio.to_thread(_fetch)


# ─── Alpha Vantage fetcher ────────────────────────────────────

async def fetch_alpha_vantage(
    ticker: str, api_key: str, outputsize: str = "full"
) -> dict:
    """Fetch daily prices from Alpha Vantage."""
    yahoo_ticker = get_yahoo_ticker(ticker)
    av_symbol = yahoo_ticker.replace(".AS", ".AMS").replace(".DE", ".DEX")

    _LOGGER.info("[alpha_vantage] Fetching %s as %s", ticker, av_symbol)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                "https://www.alphavantage.co/query",
                params={
                    "function": "TIME_SERIES_DAILY",
                    "symbol": av_symbol,
                    "outputsize": outputsize,
                    "apikey": api_key,
                },
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
        _LOGGER.error("[alpha_vantage] Error: %s", e)
        return {"prices": [], "splits": [], "metadata": {}, "error": str(e)}


# ─── Unified fetch + store ────────────────────────────────────

async def fetch_and_store(
    db: ETFfolioDB,
    ticker: str,
    source: str = "yfinance",
    api_key: str = "",
) -> dict:
    """Fetch prices using configured source(s), store in DB."""
    result = {
        "ticker": ticker,
        "source": None,
        "prices_stored": 0,
        "splits_stored": 0,
        "error": None,
    }

    data = None

    if source in ("yfinance", "both"):
        data = await fetch_yfinance(ticker)
        if data["prices"]:
            result["source"] = "yfinance"
        elif source == "both":
            _LOGGER.warning(
                "[yfinance] No data for %s, falling back to Alpha Vantage",
                ticker,
            )
            data = None

    if data is None or not data.get("prices"):
        if source in ("alpha_vantage", "both") and api_key:
            data = await fetch_alpha_vantage(ticker, api_key)
            if data["prices"]:
                result["source"] = "alpha_vantage"

    if not data or not data.get("prices"):
        err = (
            data.get("error", "No data returned") if data else "No source available"
        )
        result["error"] = err
        await db.log_fetch(ticker, source, "error", err)
        return result

    await db.upsert_prices(ticker, data["prices"])
    result["prices_stored"] = len(data["prices"])

    if data.get("splits"):
        await db.upsert_splits(ticker, data["splits"])
        result["splits_stored"] = len(data["splits"])

    if data.get("metadata"):
        meta = {k: v for k, v in data["metadata"].items() if v}
        if meta:
            await db.upsert_etf_metadata(ticker, **meta)

    await db.log_fetch(
        ticker,
        result["source"],
        "success",
        f"{result['prices_stored']} prices, {result['splits_stored']} splits",
    )

    _LOGGER.info(
        "[%s] Stored %d prices, %d splits for %s",
        result["source"],
        result["prices_stored"],
        result["splits_stored"],
        ticker,
    )
    return result


async def fetch_all_holdings(
    db: ETFfolioDB,
    source: str = "yfinance",
    api_key: str = "",
) -> list[dict]:
    """Fetch prices for all tickers that have holdings."""
    holdings = await db.get_holdings()
    tickers = list({h["ticker"] for h in holdings})
    results = []
    for ticker in tickers:
        r = await fetch_and_store(db, ticker, source, api_key)
        results.append(r)
    return results
