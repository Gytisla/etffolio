"""The ETFfolio integration for Home Assistant."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ALPHA_VANTAGE_KEY,
    CONF_CURRENCY,
    CONF_PRICE_SOURCE,
    CONF_UPDATE_INTERVAL,
    DEFAULT_CURRENCY,
    DEFAULT_PRICE_SOURCE,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from .coordinator import ETFfolioCoordinator
from .database import ETFfolioDB
from .http_api import register_views

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ETFfolio from a config entry."""
    config = {**entry.data, **entry.options}

    # Database — stored in HA config directory
    db_path = hass.config.path("etffolio.db")
    db = ETFfolioDB(db_path)
    await db.init_db()

    # Coordinator — handles periodic price updates
    coordinator = ETFfolioCoordinator(hass, db, config)

    # Store references for API views and sensors
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["db"] = db
    hass.data[DOMAIN]["config"] = config
    hass.data[DOMAIN]["coordinator"] = coordinator
    hass.data[DOMAIN]["entry"] = entry

    # Register HTTP API views and frontend
    frontend_path = str(Path(__file__).parent / "frontend")
    register_views(hass, frontend_path)

    # Register sidebar panel (iframe to our served frontend)
    hass.components.frontend.async_register_built_in_panel(
        "iframe",
        title="ETFfolio",
        icon="mdi:chart-line",
        frontend_url_path="etffolio",
        config={"url": "/etffolio_panel"},
        require_admin=False,
    )

    # Initial data fetch
    await coordinator.async_config_entry_first_refresh()

    # Forward sensor platform setup
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    _LOGGER.info("ETFfolio integration loaded successfully")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload ETFfolio config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Remove the sidebar panel
        hass.components.frontend.async_remove_panel("etffolio")
        hass.data.pop(DOMAIN, None)
        _LOGGER.info("ETFfolio integration unloaded")

    return unload_ok


async def _async_options_updated(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Handle options update — reload the integration."""
    await hass.config_entries.async_reload(entry.entry_id)
