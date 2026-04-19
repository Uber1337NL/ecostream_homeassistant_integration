from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from homeassistant.components.climate import HVACAction, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.ecostream.climate import (
    EcostreamSummerComfortClimate,
    async_setup_entry,
)


def _make_entity(
    data: dict[str, Any] | None = None,
    ws: bool = True,
) -> tuple[EcostreamSummerComfortClimate, MagicMock]:
    coordinator = MagicMock()
    coordinator.data = data or {}
    coordinator.host = "192.168.1.1"
    coordinator.ws = MagicMock() if ws else None
    if ws:
        coordinator.ws.send_json = AsyncMock()
    coordinator.mark_control_action = MagicMock()
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry"

    def _mock_coordinator_entity_init(
        self: CoordinatorEntity, c: Any
    ) -> None:
        self.coordinator = c

    with patch.object(
        CoordinatorEntity,
        "__init__",
        _mock_coordinator_entity_init,
    ):
        entity = EcostreamSummerComfortClimate(coordinator, entry)
    entity.async_write_ha_state = MagicMock()
    return entity, coordinator


@pytest.mark.asyncio
async def test_climate_async_setup_entry_adds_entities():
    coordinator = MagicMock()
    coordinator.host = "192.168.1.1"
    coordinator.data = {}
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry"
    entry.runtime_data = coordinator

    def _mock_coordinator_entity_init(
        self: CoordinatorEntity, c: Any
    ) -> None:
        self.coordinator = c

    with patch.object(
        CoordinatorEntity, "__init__", _mock_coordinator_entity_init
    ):
        add_entities = MagicMock()
        await async_setup_entry(MagicMock(), entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args[0][0]
    assert len(entities) == 1
    assert isinstance(entities[0], EcostreamSummerComfortClimate)


def test_unique_id():
    entity, _ = _make_entity()
    assert entity.unique_id == "test_entry_summer_comfort_climate"


def test_hvac_mode_cool_when_enabled():
    entity, _ = _make_entity({"config": {"sum_com_enabled": True}})
    assert entity.hvac_mode == HVACMode.COOL


def test_hvac_mode_off_when_disabled():
    entity, _ = _make_entity({"config": {"sum_com_enabled": False}})
    assert entity.hvac_mode == HVACMode.OFF


def test_hvac_mode_off_when_missing():
    entity, _ = _make_entity()
    assert entity.hvac_mode == HVACMode.OFF


def test_hvac_action_cooling_when_bypass_open():
    entity, _ = _make_entity(
        {"config": {"sum_com_enabled": True}, "status": {"bypass_pos": 100}}
    )
    assert entity.hvac_action == HVACAction.COOLING


def test_hvac_action_idle_when_bypass_closed():
    entity, _ = _make_entity(
        {"config": {"sum_com_enabled": True}, "status": {"bypass_pos": 0}}
    )
    assert entity.hvac_action == HVACAction.IDLE


def test_hvac_action_off_when_disabled():
    entity, _ = _make_entity(
        {"config": {"sum_com_enabled": False}, "status": {"bypass_pos": 100}}
    )
    assert entity.hvac_action == HVACAction.OFF


def test_current_temperature():
    entity, _ = _make_entity({"status": {"sensor_temp_eta": 23.5}})
    assert entity.current_temperature == 23.5


def test_current_temperature_none_when_missing():
    entity, _ = _make_entity()
    assert entity.current_temperature is None


def test_target_temperature():
    entity, _ = _make_entity({"config": {"sum_com_temp": 22}})
    assert entity.target_temperature == 22.0


def test_target_temperature_none_when_missing():
    entity, _ = _make_entity()
    assert entity.target_temperature is None


@pytest.mark.asyncio
async def test_set_temperature():
    entity, coordinator = _make_entity()
    await entity.async_set_temperature(temperature=25)
    coordinator.ws.send_json.assert_called_once_with(
        {"config": {"sum_com_temp": 25}}
    )


@pytest.mark.asyncio
async def test_set_temperature_no_value():
    entity, coordinator = _make_entity()
    await entity.async_set_temperature()
    coordinator.ws.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_set_hvac_mode_cool():
    entity, coordinator = _make_entity()
    await entity.async_set_hvac_mode(HVACMode.COOL)
    coordinator.ws.send_json.assert_called_once_with(
        {"config": {"sum_com_enabled": True}}
    )


@pytest.mark.asyncio
async def test_set_hvac_mode_off():
    entity, coordinator = _make_entity()
    await entity.async_set_hvac_mode(HVACMode.OFF)
    coordinator.ws.send_json.assert_called_once_with(
        {"config": {"sum_com_enabled": False}}
    )


@pytest.mark.asyncio
async def test_set_temperature_no_ws():
    entity, _ = _make_entity(ws=False)
    await entity.async_set_temperature(temperature=25)


@pytest.mark.asyncio
async def test_set_hvac_mode_no_ws():
    entity, _ = _make_entity(ws=False)
    await entity.async_set_hvac_mode(HVACMode.COOL)


def test_handle_coordinator_update():
    entity, _ = _make_entity(
        {"config": {"sum_com_enabled": True, "sum_com_temp": 24},
         "status": {"bypass_pos": 50, "sensor_temp_eta": 21}}
    )
    entity._handle_coordinator_update()
    cast(MagicMock, entity.async_write_ha_state).assert_called_once()
    assert entity.hvac_mode == HVACMode.COOL
    assert entity.hvac_action == HVACAction.COOLING
    assert entity.current_temperature == 21.0
    assert entity.target_temperature == 24.0


@pytest.mark.asyncio
async def test_apply_config_uses_async_send_config():
    entity, coordinator = _make_entity()
    coordinator.async_send_config = AsyncMock(return_value=True)
    await entity.async_set_temperature(temperature=20)
    coordinator.async_send_config.assert_awaited_once_with(
        {"sum_com_temp": 20}, "summer comfort temp"
    )
