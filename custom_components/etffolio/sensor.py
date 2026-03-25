"""Sensor platform for ETFfolio — exposes portfolio data as HA sensors."""

from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ETFfolioCoordinator

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "total_value": {
        "name": "Portfolio Value",
        "icon": "mdi:chart-line",
        "device_class": SensorDeviceClass.MONETARY,
        "state_class": SensorStateClass.TOTAL,
        "unit_key": "currency",
    },
    "total_cost": {
        "name": "Total Invested",
        "icon": "mdi:cash-multiple",
        "device_class": SensorDeviceClass.MONETARY,
        "state_class": SensorStateClass.TOTAL,
        "unit_key": "currency",
    },
    "total_pnl": {
        "name": "Total P/L",
        "icon": "mdi:trending-up",
        "device_class": SensorDeviceClass.MONETARY,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit_key": "currency",
    },
    "total_pnl_pct": {
        "name": "Total Return",
        "icon": "mdi:percent-outline",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": "%",
    },
    "day_change": {
        "name": "Day Change",
        "icon": "mdi:calendar-today",
        "device_class": SensorDeviceClass.MONETARY,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit_key": "currency",
    },
    "day_change_pct": {
        "name": "Day Change %",
        "icon": "mdi:percent-outline",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": "%",
    },
    "num_positions": {
        "name": "Positions",
        "icon": "mdi:view-grid-outline",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": "ETFs",
    },
    "last_price_fetch": {
        "name": "Last Price Update",
        "icon": "mdi:clock-check-outline",
        "device_class": SensorDeviceClass.TIMESTAMP,
        "state_class": None,
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ETFfolio sensor entities."""
    coordinator: ETFfolioCoordinator = hass.data[DOMAIN]["coordinator"]

    entities = [
        ETFfolioSensor(coordinator, sensor_type, config)
        for sensor_type, config in SENSOR_TYPES.items()
    ]
    async_add_entities(entities)


class ETFfolioSensor(CoordinatorEntity, SensorEntity):
    """Representation of an ETFfolio sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ETFfolioCoordinator,
        sensor_type: str,
        config: dict,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._config = config
        self._attr_unique_id = f"etffolio_{sensor_type}"
        self._attr_name = config["name"]
        self._attr_icon = config["icon"]
        self._attr_device_class = config.get("device_class")
        self._attr_state_class = config.get("state_class")

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        if "unit" in self._config:
            return self._config["unit"]
        if "unit_key" in self._config and self.coordinator.data:
            return self.coordinator.data.get(self._config["unit_key"], "EUR")
        return None

    @property
    def native_value(self):
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        val = self.coordinator.data.get(self._sensor_type)
        # TIMESTAMP device class needs a datetime object
        if self._sensor_type == "last_price_fetch" and isinstance(val, str):
            try:
                return datetime.fromisoformat(val)
            except (ValueError, TypeError):
                return None
        return val

    @property
    def device_info(self):
        """Return device info to group all sensors."""
        return {
            "identifiers": {(DOMAIN, "etffolio")},
            "name": "ETFfolio",
            "manufacturer": "ETFfolio",
            "model": "Portfolio Tracker",
            "sw_version": "0.1.0",
        }

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional state attributes for the main value sensor."""
        if self._sensor_type != "total_value" or self.coordinator.data is None:
            return {}
        data = self.coordinator.data
        return {
            "total_cost": data.get("total_cost"),
            "total_fees": data.get("total_fees"),
            "num_records": data.get("num_records"),
            "currency": data.get("currency"),
            "last_price_fetch": data.get("last_price_fetch"),
        }
