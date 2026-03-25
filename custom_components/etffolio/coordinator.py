"""DataUpdateCoordinator for ETFfolio — periodically fetches prices."""

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_ALPHA_VANTAGE_KEY, CONF_PRICE_SOURCE, CONF_UPDATE_INTERVAL, DEFAULT_PRICE_SOURCE, DEFAULT_UPDATE_INTERVAL, DOMAIN
from .database import ETFfolioDB
from .prices import fetch_all_holdings

_LOGGER = logging.getLogger(__name__)


class ETFfolioCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch ETF prices and compute portfolio summary."""

    def __init__(self, hass: HomeAssistant, db: ETFfolioDB, config: dict) -> None:
        """Initialize the coordinator."""
        interval = config.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=interval),
        )
        self.db = db
        self.config = config
        self._fetch_prices = True  # True on scheduled updates, False on manual refresh

    async def _async_update_data(self) -> dict:
        """Compute portfolio summary. Fetch prices only on scheduled updates."""
        if self._fetch_prices:
            source = self.config.get(CONF_PRICE_SOURCE, DEFAULT_PRICE_SOURCE)
            api_key = self.config.get(CONF_ALPHA_VANTAGE_KEY, "")

            results = await fetch_all_holdings(self.db, source, api_key)
            success = sum(1 for r in results if not r.get("error"))
            failed = sum(1 for r in results if r.get("error"))
            _LOGGER.info(
                "Price update complete: %d succeeded, %d failed", success, failed
            )
        else:
            # Reset flag so next scheduled update fetches prices again
            self._fetch_prices = True

        return await self._compute_summary()

    async def async_request_refresh(self) -> None:
        """Refresh sensor data without fetching prices."""
        self._fetch_prices = False
        await super().async_request_refresh()

    async def _compute_summary(self) -> dict:
        """Compute portfolio summary from DB data."""
        holdings = await self.db.get_holdings()
        total_value = 0.0
        total_cost = 0.0
        total_fees = 0.0
        day_change = 0.0

        for h in holdings:
            adj = await self.db.get_adjusted_shares(
                h["ticker"], h["shares"], h["purchase_date"]
            )
            latest = await self.db.get_latest_price(h["ticker"])
            if not latest:
                continue
            cur = latest["close"]

            prices = await self.db.get_prices(h["ticker"])
            prev = prices[-2]["close"] if len(prices) >= 2 else cur

            fees = h.get("brokerage_fee", 0) + h.get("stamp_duty", 0)
            total_value += adj * cur
            total_cost += h["shares"] * h["purchase_price"] + fees
            total_fees += fees
            day_change += adj * (cur - prev)

        pnl = total_value - total_cost
        tickers = {h["ticker"] for h in holdings}

        return {
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
            "currency": self.config.get("currency", "EUR"),
        }
