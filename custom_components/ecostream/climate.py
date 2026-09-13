from __future__ import annotations

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import inspect
import logging
from typing import Any

from .const import DEVICE_MODEL, DEVICE_NAME, DOMAIN
from .coordinator import EcostreamDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the EcoStream climate platform."""
    coordinator: EcostreamDataUpdateCoordinator = entry.runtime_data

    async_add_entities(
        [EcostreamSummerComfortClimate(coordinator, entry)],
        update_before_add=True,
    )


class EcostreamSummerComfortClimate(  # pyright: ignore[reportIncompatibleVariableOverride]
    CoordinatorEntity[EcostreamDataUpdateCoordinator],
    ClimateEntity,
):
    """EcoStream Summer Comfort climate entity (cooling via bypass)."""

    _attr_has_entity_name = True
    _attr_name = "Summer Comfort"
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = PRECISION_WHOLE
    _attr_min_temp = 10
    _attr_max_temp = 30

    def __init__(
        self,
        coordinator: EcostreamDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL]
        self._attr_unique_id = (
            f"{entry.entry_id}_summer_comfort_climate"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.host)},
            manufacturer="BUVA",
            name=DEVICE_NAME,
            model=DEVICE_MODEL,
        )
        self._update_attrs()

    def _get_config(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get("config", {}) or {}

    def _get_status(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get("status", {}) or {}

    async def _apply_config(
        self, cfg: dict[str, Any], action: str
    ) -> None:
        sender = getattr(self.coordinator, "async_send_config", None)
        if sender is not None:
            result = sender(cfg, action)
            if inspect.isawaitable(result):
                await result
                return

        if not self.coordinator.ws:
            _LOGGER.error(
                "EcoStream WebSocket not connected, cannot send %s command",
                action,
            )
            return

        self.coordinator.mark_control_action()
        await self.coordinator.ws.send_json({"config": cfg})

    def _update_attrs(self) -> None:
        config = self._get_config()
        status = self._get_status()

        enabled = bool(config.get("sum_com_enabled", False))
        self._attr_hvac_mode = (
            HVACMode.COOL if enabled else HVACMode.OFF
        )

        if not enabled:
            self._attr_hvac_action = HVACAction.OFF
        else:
            bypass_pos = status.get("bypass_pos")
            try:
                self._attr_hvac_action = (
                    HVACAction.COOLING
                    if bypass_pos is not None and float(bypass_pos) > 0
                    else HVACAction.IDLE
                )
            except (TypeError, ValueError):
                self._attr_hvac_action = HVACAction.IDLE

        try:
            temp = status.get("sensor_temp_eta")
            self._attr_current_temperature = (
                float(temp) if temp is not None else None
            )
        except (TypeError, ValueError):
            self._attr_current_temperature = None

        try:
            target = config.get("sum_com_temp")
            self._attr_target_temperature = (
                float(target) if target is not None else None
            )
        except (TypeError, ValueError):
            self._attr_target_temperature = None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get("temperature")
        if temperature is None:
            return
        await self._apply_config(
            {"sum_com_temp": int(temperature)}, "summer comfort temp"
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        enable = hvac_mode == HVACMode.COOL
        await self._apply_config(
            {"sum_com_enabled": enable}, "summer comfort mode"
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_attrs()
        self.async_write_ha_state()
