"""Constants for the ETFfolio integration."""

DOMAIN = "etffolio"

CONF_PRICE_SOURCE = "price_source"
CONF_ALPHA_VANTAGE_KEY = "alpha_vantage_api_key"
CONF_UPDATE_INTERVAL = "update_interval_hours"
CONF_CURRENCY = "currency"

DEFAULT_PRICE_SOURCE = "yfinance"
DEFAULT_UPDATE_INTERVAL = 6
DEFAULT_CURRENCY = "EUR"

PRICE_SOURCES = ["yfinance", "alpha_vantage", "both"]
CURRENCIES = ["EUR", "USD", "GBP", "CHF"]
