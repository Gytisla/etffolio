"""HTTP API views for ETFfolio — serves the REST API and frontend panel."""

import logging
import mimetypes
import os
from datetime import datetime, timedelta
from pathlib import Path

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import CONF_ALPHA_VANTAGE_KEY, CONF_CURRENCY, CONF_PRICE_SOURCE, CONF_UPDATE_INTERVAL, DEFAULT_CURRENCY, DEFAULT_PRICE_SOURCE, DEFAULT_UPDATE_INTERVAL, DOMAIN
from .database import ETFfolioDB
from .prices import TICKER_MAP, fetch_all_holdings, fetch_and_store

_LOGGER = logging.getLogger(__name__)


def _get_db(hass: HomeAssistant) -> ETFfolioDB:
    """Get the database instance from hass.data."""
    return hass.data[DOMAIN]["db"]


def _get_config(hass: HomeAssistant) -> dict:
    """Get the integration config from hass.data."""
    return hass.data[DOMAIN]["config"]


async def _refresh_sensors(hass: HomeAssistant) -> None:
    """Tell the coordinator to recompute sensor data now."""
    coordinator = hass.data.get(DOMAIN, {}).get("coordinator")
    if coordinator:
        await coordinator.async_request_refresh()


# ─── Holdings ─────────────────────────────────────────────────


class ETFfolioHoldingsView(HomeAssistantView):
    """Handle /api/etffolio/holdings."""

    url = "/api/etffolio/holdings"
    name = "api:etffolio:holdings"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        hass = request.app["hass"]
        db = _get_db(hass)
        config = _get_config(hass)

        holdings = await db.get_holdings()
        enriched = []
        for h in holdings:
            ticker = h["ticker"]
            adj_shares = await db.get_adjusted_shares(
                ticker, h["shares"], h["purchase_date"]
            )
            latest = await db.get_latest_price(ticker)
            cur_price = latest["close"] if latest else None
            meta = await db.get_etf_metadata(ticker)

            cost_basis = h["shares"] * h["purchase_price"]
            fees = h.get("brokerage_fee", 0) + h.get("stamp_duty", 0)
            total_cost = cost_basis + fees
            value = adj_shares * cur_price if cur_price else None
            pnl = (value - total_cost) if value else None
            pnl_pct = (
                (pnl / total_cost * 100) if (pnl is not None and total_cost > 0) else None
            )

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
        return self.json(enriched)

    async def post(self, request: web.Request) -> web.Response:
        hass = request.app["hass"]
        db = _get_db(hass)

        data = await request.json()
        ticker = data.get("ticker", "").upper()
        if not ticker:
            return self.json_message("ticker is required", status_code=400)

        h = await db.add_holding(
            ticker=ticker,
            shares=float(data["shares"]),
            purchase_date=data["purchase_date"],
            purchase_price=float(data["purchase_price"]),
            brokerage_fee=float(data.get("brokerage_fee", 0)),
            stamp_duty=float(data.get("stamp_duty", 0)),
            notes=data.get("notes", ""),
        )

        # Auto-fetch prices if missing
        latest = await db.get_latest_price(ticker)
        if not latest:
            config = _get_config(hass)
            await fetch_and_store(
                db,
                ticker,
                config.get(CONF_PRICE_SOURCE, DEFAULT_PRICE_SOURCE),
                config.get(CONF_ALPHA_VANTAGE_KEY, ""),
            )

        await _refresh_sensors(hass)
        return self.json(h)


class ETFfolioHoldingDetailView(HomeAssistantView):
    """Handle /api/etffolio/holdings/{holding_id}."""

    url = "/api/etffolio/holdings/{holding_id}"
    name = "api:etffolio:holding_detail"
    requires_auth = False

    async def put(self, request: web.Request, holding_id: str) -> web.Response:
        hass = request.app["hass"]
        db = _get_db(hass)

        data = await request.json()
        result = await db.update_holding(int(holding_id), **data)
        if not result:
            return self.json_message("Holding not found", status_code=404)
        await _refresh_sensors(hass)
        return self.json(result)

    async def delete(self, request: web.Request, holding_id: str) -> web.Response:
        hass = request.app["hass"]
        db = _get_db(hass)

        ok = await db.delete_holding(int(holding_id))
        if not ok:
            return self.json_message("Holding not found", status_code=404)
        await _refresh_sensors(hass)
        return self.json({"deleted": True})


# ─── Portfolio ────────────────────────────────────────────────


class ETFfolioSummaryView(HomeAssistantView):
    """Handle /api/etffolio/portfolio/summary."""

    url = "/api/etffolio/portfolio/summary"
    name = "api:etffolio:portfolio_summary"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        hass = request.app["hass"]
        db = _get_db(hass)
        config = _get_config(hass)

        holdings = await db.get_holdings()
        total_value = 0.0
        total_cost = 0.0
        total_fees = 0.0
        day_change = 0.0

        for h in holdings:
            adj = await db.get_adjusted_shares(
                h["ticker"], h["shares"], h["purchase_date"]
            )
            latest = await db.get_latest_price(h["ticker"])
            if not latest:
                continue
            cur = latest["close"]

            prices = await db.get_prices(h["ticker"])
            prev = prices[-2]["close"] if len(prices) >= 2 else cur

            fees = h.get("brokerage_fee", 0) + h.get("stamp_duty", 0)
            total_value += adj * cur
            total_cost += h["shares"] * h["purchase_price"] + fees
            total_fees += fees
            day_change += adj * (cur - prev)

        pnl = total_value - total_cost
        tickers = {h["ticker"] for h in holdings}

        return self.json({
            "total_value": round(total_value, 2),
            "total_cost": round(total_cost, 2),
            "total_pnl": round(pnl, 2),
            "total_pnl_pct": (
                round(pnl / total_cost * 100, 2) if total_cost > 0 else 0
            ),
            "day_change": round(day_change, 2),
            "day_change_pct": (
                round(day_change / (total_value - day_change) * 100, 2)
                if (total_value - day_change) > 0
                else 0
            ),
            "total_fees": round(total_fees, 2),
            "num_positions": len(tickers),
            "num_records": len(holdings),
            "currency": config.get(CONF_CURRENCY, DEFAULT_CURRENCY),
            "update_interval_hours": config.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
            "last_updated": datetime.now().isoformat(),
        })


class ETFfolioPositionsView(HomeAssistantView):
    """Handle /api/etffolio/portfolio/positions."""

    url = "/api/etffolio/portfolio/positions"
    name = "api:etffolio:portfolio_positions"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        hass = request.app["hass"]
        db = _get_db(hass)

        holdings = await db.get_holdings()
        if not holdings:
            return self.json([])

        grouped: dict[str, list[dict]] = {}
        for h in holdings:
            grouped.setdefault(h["ticker"], []).append(h)

        today = datetime.now()
        period_offsets = {
            "day": timedelta(days=1),
            "week": timedelta(days=7),
            "month": timedelta(days=30),
            "3month": timedelta(days=90),
            "6month": timedelta(days=180),
            "year": timedelta(days=365),
        }

        results = []
        for ticker, rows in grouped.items():
            latest = await db.get_latest_price(ticker)
            if not latest:
                continue
            cur_price = latest["close"]
            meta = await db.get_etf_metadata(ticker)

            total_shares = 0.0
            total_cost = 0.0
            total_fees = 0.0
            for h in rows:
                adj = await db.get_adjusted_shares(
                    ticker, h["shares"], h["purchase_date"]
                )
                total_shares += adj
                fees = h.get("brokerage_fee", 0) + h.get("stamp_duty", 0)
                total_cost += h["shares"] * h["purchase_price"] + fees
                total_fees += fees

            current_value = total_shares * cur_price
            total_pnl = current_value - total_cost
            total_pnl_pct = (
                (total_pnl / total_cost * 100) if total_cost > 0 else 0
            )

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
        return self.json(results)


class ETFfolioHistoryView(HomeAssistantView):
    """Handle /api/etffolio/portfolio/history."""

    url = "/api/etffolio/portfolio/history"
    name = "api:etffolio:portfolio_history"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        hass = request.app["hass"]
        db = _get_db(hass)

        range_param = request.query.get("range", "1Y")
        valid_ranges = {"1D", "1W", "1M", "3M", "6M", "1Y", "ALL"}
        if range_param not in valid_ranges:
            range_param = "1Y"

        days_map = {
            "1D": 1, "1W": 7, "1M": 30, "3M": 90,
            "6M": 180, "1Y": 365, "ALL": 3650,
        }
        days = days_map.get(range_param, 365)
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        holdings = await db.get_holdings()
        if not holdings:
            return self.json([])

        tickers = list({h["ticker"] for h in holdings})
        price_maps = {}
        all_dates: set[str] = set()
        for t in tickers:
            prices = await db.get_prices(t, start_date=start)
            pm = {p["date"]: p["close"] for p in prices}
            price_maps[t] = pm
            all_dates.update(pm.keys())

        if not all_dates:
            return self.json([])

        results = []
        for date_str in sorted(all_dates):
            total_value = 0.0
            total_cost = 0.0
            for h in holdings:
                if h["purchase_date"] > date_str:
                    continue
                adj = await db.get_adjusted_shares(
                    h["ticker"], h["shares"], h["purchase_date"]
                )
                pm = price_maps.get(h["ticker"], {})
                price = pm.get(date_str)
                if price is None:
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

        return self.json(results)


# ─── Prices ───────────────────────────────────────────────────


class ETFfolioPricesView(HomeAssistantView):
    """Handle /api/etffolio/prices/{ticker}."""

    url = "/api/etffolio/prices/{ticker}"
    name = "api:etffolio:prices"
    requires_auth = False

    async def get(self, request: web.Request, ticker: str) -> web.Response:
        hass = request.app["hass"]
        db = _get_db(hass)
        start = request.query.get("start")
        end = request.query.get("end")
        return self.json(await db.get_prices(ticker.upper(), start, end))


class ETFfolioPriceLatestView(HomeAssistantView):
    """Handle /api/etffolio/prices/{ticker}/latest."""

    url = "/api/etffolio/prices/{ticker}/latest"
    name = "api:etffolio:price_latest"
    requires_auth = False

    async def get(self, request: web.Request, ticker: str) -> web.Response:
        hass = request.app["hass"]
        db = _get_db(hass)
        p = await db.get_latest_price(ticker.upper())
        if not p:
            return self.json_message(
                f"No price data for {ticker}", status_code=404
            )
        return self.json(p)


# ─── Fetch / Refresh ─────────────────────────────────────────


class ETFfolioFetchTickerView(HomeAssistantView):
    """Handle /api/etffolio/fetch/{ticker}."""

    url = "/api/etffolio/fetch/{ticker}"
    name = "api:etffolio:fetch_ticker"
    requires_auth = False

    async def post(self, request: web.Request, ticker: str) -> web.Response:
        hass = request.app["hass"]
        db = _get_db(hass)
        config = _get_config(hass)
        result = await fetch_and_store(
            db,
            ticker.upper(),
            config.get(CONF_PRICE_SOURCE, DEFAULT_PRICE_SOURCE),
            config.get(CONF_ALPHA_VANTAGE_KEY, ""),
        )
        await _refresh_sensors(hass)
        return self.json(result)


class ETFfolioFetchAllView(HomeAssistantView):
    """Handle /api/etffolio/fetch."""

    url = "/api/etffolio/fetch"
    name = "api:etffolio:fetch_all"
    requires_auth = False

    async def post(self, request: web.Request) -> web.Response:
        hass = request.app["hass"]
        db = _get_db(hass)
        config = _get_config(hass)
        results = await fetch_all_holdings(
            db,
            config.get(CONF_PRICE_SOURCE, DEFAULT_PRICE_SOURCE),
            config.get(CONF_ALPHA_VANTAGE_KEY, ""),
        )
        await _refresh_sensors(hass)
        return self.json(results)


# ─── Metadata ─────────────────────────────────────────────────


class ETFfolioETFsView(HomeAssistantView):
    """Handle /api/etffolio/etfs."""

    url = "/api/etffolio/etfs"
    name = "api:etffolio:etfs"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        hass = request.app["hass"]
        db = _get_db(hass)
        return self.json(await db.get_etf_metadata())


class ETFfolioKnownTickersView(HomeAssistantView):
    """Handle /api/etffolio/etfs/known."""

    url = "/api/etffolio/etfs/known"
    name = "api:etffolio:etfs_known"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        return self.json({
            "tickers": TICKER_MAP,
            "description": "Short ticker → Yahoo Finance ticker mapping",
        })


class ETFfolioSplitsView(HomeAssistantView):
    """Handle /api/etffolio/splits/{ticker}."""

    url = "/api/etffolio/splits/{ticker}"
    name = "api:etffolio:splits"
    requires_auth = False

    async def get(self, request: web.Request, ticker: str) -> web.Response:
        hass = request.app["hass"]
        db = _get_db(hass)
        return self.json(await db.get_splits(ticker.upper()))


class ETFfolioHealthView(HomeAssistantView):
    """Handle /api/etffolio/health."""

    url = "/api/etffolio/health"
    name = "api:etffolio:health"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        hass = request.app["hass"]
        db = _get_db(hass)
        return self.json({
            "status": "ok",
            "version": "0.1.0",
            "db": os.path.exists(db._db_path),
        })


# ─── Frontend Panel Serving ──────────────────────────────────


class ETFfolioPanelView(HomeAssistantView):
    """Serve the ETFfolio SPA index.html."""

    url = "/etffolio_panel"
    extra_urls = ["/etffolio_panel/{path:.*}"]
    name = "etffolio:panel"
    requires_auth = False

    # Ensure JS/CSS are served with correct MIME types
    MIME_TYPES = {
        ".js": "application/javascript",
        ".css": "text/css",
        ".html": "text/html",
        ".json": "application/json",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".ico": "image/x-icon",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
    }

    def __init__(self, frontend_path: str) -> None:
        self._frontend_path = Path(frontend_path)

    def _file_response(self, file_path: Path) -> web.Response:
        """Return a response with correct Content-Type for the file."""
        suffix = file_path.suffix.lower()
        content_type = self.MIME_TYPES.get(
            suffix,
            mimetypes.guess_type(str(file_path))[0] or "application/octet-stream",
        )
        return web.FileResponse(
            file_path,
            headers={"Content-Type": content_type},
        )

    async def get(
        self, request: web.Request, path: str = ""
    ) -> web.Response:
        # Serve static files if they exist
        if path:
            file_path = self._frontend_path / path
            if file_path.is_file():
                return self._file_response(file_path)

        # Fallback to index.html (SPA routing)
        index = self._frontend_path / "index.html"
        if index.is_file():
            return self._file_response(index)

        return web.Response(
            text="ETFfolio frontend not built. Run: cd frontend && npm run build",
            status=404,
        )


# ─── Registration ─────────────────────────────────────────────

API_VIEWS = [
    ETFfolioHoldingsView,
    ETFfolioHoldingDetailView,
    ETFfolioSummaryView,
    ETFfolioPositionsView,
    ETFfolioHistoryView,
    ETFfolioPricesView,
    ETFfolioPriceLatestView,
    ETFfolioFetchTickerView,
    ETFfolioFetchAllView,
    ETFfolioETFsView,
    ETFfolioKnownTickersView,
    ETFfolioSplitsView,
    ETFfolioHealthView,
]


def register_views(hass: HomeAssistant, frontend_path: str) -> None:
    """Register all ETFfolio API views and frontend panel."""
    for view_cls in API_VIEWS:
        hass.http.register_view(view_cls())

    hass.http.register_view(ETFfolioPanelView(frontend_path))
