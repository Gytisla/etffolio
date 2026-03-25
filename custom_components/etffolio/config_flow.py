"""Config flow for ETFfolio integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_ALPHA_VANTAGE_KEY,
    CONF_CURRENCY,
    CONF_PRICE_SOURCE,
    CONF_UPDATE_INTERVAL,
    CURRENCIES,
    DEFAULT_CURRENCY,
    DEFAULT_PRICE_SOURCE,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    PRICE_SOURCES,
)


class ETFfolioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ETFfolio."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        # Only allow a single instance
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="ETFfolio", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PRICE_SOURCE, default=DEFAULT_PRICE_SOURCE
                    ): vol.In(PRICE_SOURCES),
                    vol.Optional(CONF_ALPHA_VANTAGE_KEY, default=""): str,
                    vol.Required(
                        CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
                    vol.Required(
                        CONF_CURRENCY, default=DEFAULT_CURRENCY
                    ): vol.In(CURRENCIES),
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow."""
        return ETFfolioOptionsFlow(config_entry)


class ETFfolioOptionsFlow(OptionsFlow):
    """Handle ETFfolio options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options or self.config_entry.data

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PRICE_SOURCE,
                        default=current.get(CONF_PRICE_SOURCE, DEFAULT_PRICE_SOURCE),
                    ): vol.In(PRICE_SOURCES),
                    vol.Optional(
                        CONF_ALPHA_VANTAGE_KEY,
                        default=current.get(CONF_ALPHA_VANTAGE_KEY, ""),
                    ): str,
                    vol.Required(
                        CONF_UPDATE_INTERVAL,
                        default=current.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
                    vol.Required(
                        CONF_CURRENCY,
                        default=current.get(CONF_CURRENCY, DEFAULT_CURRENCY),
                    ): vol.In(CURRENCIES),
                }
            ),
        )
