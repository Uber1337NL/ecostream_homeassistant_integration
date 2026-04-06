from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from homeassistant.components.switch.const import (
    DOMAIN as SWITCH_DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ecostream.const import (
    CONF_PRESET_OVERRIDE_MINUTES,
    CONF_SUMMER_COMFORT_TEMP,
    DEFAULT_PRESET_OVERRIDE_MINUTES,
    PRESET_HIGH,
    PRESET_LOW,
    PRESET_MID,
)
from custom_components.ecostream.switch import (
    EcostreamBypassSwitch,
    EcostreamPresetSwitch,
    EcostreamScheduleSwitch,
    EcostreamSummerComfortSwitch,
    async_setup_entry,
)


def _make_entity(
    EntityClass: type[Any],
    data: dict[str, Any] | None = None,
    ws: bool = True,
    **kwargs: Any,
) -> tuple[Any, MagicMock]:
    coordinator = MagicMock()
    coordinator.data = data or {}
    coordinator.host = "192.168.1.1"
    coordinator.ws = MagicMock() if ws else None
    if ws:
        coordinator.ws.send_json = AsyncMock()
    coordinator.mark_control_action = MagicMock()
    coordinator.bypass_duration_minutes = 60
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
        entity = EntityClass(coordinator, entry, **kwargs)
    entity.async_write_ha_state = MagicMock()
    return entity, coordinator


@pytest.mark.asyncio
async def test_switch_async_setup_entry_adds_entities():
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
    assert len(entities) == 6


# ---------------------------------------------------------------------------
# EcostreamScheduleSwitch
# ---------------------------------------------------------------------------


def test_schedule_is_on_true():
    entity, _ = _make_entity(
        EcostreamScheduleSwitch, {"config": {"schedule_enabled": True}}
    )
    assert entity.is_on is True


def test_schedule_is_on_false():
    entity, _ = _make_entity(EcostreamScheduleSwitch)
    assert entity.is_on is False


def test_schedule_unique_id():
    entity, _ = _make_entity(EcostreamScheduleSwitch)
    assert entity.unique_id == "test_entry_schedule_enabled"


def test_schedule_handle_update():
    entity, _ = _make_entity(EcostreamScheduleSwitch)
    entity._handle_coordinator_update()
    cast(MagicMock, entity.async_write_ha_state).assert_called_once()


@pytest.mark.asyncio
async def test_schedule_turn_on():
    entity, coordinator = _make_entity(EcostreamScheduleSwitch)
    await entity.async_turn_on()
    coordinator.ws.send_json.assert_called_once_with(
        {"config": {"schedule_enabled": True}}
    )


@pytest.mark.asyncio
async def test_schedule_turn_off():
    entity, coordinator = _make_entity(EcostreamScheduleSwitch)
    await entity.async_turn_off()
    coordinator.ws.send_json.assert_called_once_with(
        {"config": {"schedule_enabled": False}}
    )


@pytest.mark.asyncio
async def test_schedule_no_ws_returns_early():
    entity, _ = _make_entity(EcostreamScheduleSwitch, ws=False)
    await entity.async_turn_on()


@pytest.mark.asyncio
async def test_schedule_marks_control_action():
    entity, coordinator = _make_entity(EcostreamScheduleSwitch)
    await entity.async_turn_on()
    coordinator.mark_control_action.assert_called_once()


# ---------------------------------------------------------------------------
# EcostreamSummerComfortSwitch
# ---------------------------------------------------------------------------


def test_summer_comfort_is_on_true():
    entity, _ = _make_entity(
        EcostreamSummerComfortSwitch,
        {"config": {"sum_com_enabled": True}},
    )
    assert entity.is_on is True


def test_summer_comfort_is_on_false():
    entity, _ = _make_entity(EcostreamSummerComfortSwitch)
    assert entity.is_on is False


def test_summer_comfort_unique_id():
    entity, _ = _make_entity(EcostreamSummerComfortSwitch)
    assert entity.unique_id == "test_entry_summer_comfort"


@pytest.mark.asyncio
async def test_summer_comfort_turn_on():
    entity, coordinator = _make_entity(EcostreamSummerComfortSwitch)
    await entity.async_turn_on()
    coordinator.ws.send_json.assert_called_once_with(
        {"config": {"sum_com_enabled": True, "sum_com_temp": 22}}
    )


@pytest.mark.asyncio
async def test_summer_comfort_turn_on_uses_option_temp():
    entity, coordinator = _make_entity(EcostreamSummerComfortSwitch)
    entity._entry.options = {CONF_SUMMER_COMFORT_TEMP: 26}
    await entity.async_turn_on()
    coordinator.ws.send_json.assert_called_once_with(
        {"config": {"sum_com_enabled": True, "sum_com_temp": 26}}
    )


@pytest.mark.asyncio
async def test_summer_comfort_turn_on_invalid_temp_uses_default():
    entity, coordinator = _make_entity(EcostreamSummerComfortSwitch)
    entity._entry.options = {CONF_SUMMER_COMFORT_TEMP: "bad"}
    await entity.async_turn_on()
    coordinator.ws.send_json.assert_called_once_with(
        {"config": {"sum_com_enabled": True, "sum_com_temp": 22}}
    )


@pytest.mark.asyncio
async def test_summer_comfort_turn_on_out_of_range_uses_default():
    entity, coordinator = _make_entity(EcostreamSummerComfortSwitch)
    entity._entry.options = {CONF_SUMMER_COMFORT_TEMP: 99}
    await entity.async_turn_on()
    coordinator.ws.send_json.assert_called_once_with(
        {"config": {"sum_com_enabled": True, "sum_com_temp": 22}}
    )


@pytest.mark.asyncio
async def test_summer_comfort_turn_off():
    entity, coordinator = _make_entity(EcostreamSummerComfortSwitch)
    await entity.async_turn_off()
    coordinator.ws.send_json.assert_called_once_with(
        {"config": {"sum_com_enabled": False}}
    )


@pytest.mark.asyncio
async def test_summer_comfort_no_ws():
    entity, _ = _make_entity(EcostreamSummerComfortSwitch, ws=False)
    await entity.async_turn_on()


# ---------------------------------------------------------------------------
# EcostreamBypassSwitch
# ---------------------------------------------------------------------------


def test_bypass_switch_unique_id():
    entity, _ = _make_entity(EcostreamBypassSwitch)
    assert entity.unique_id == "test_entry_bypass_valve"


def test_bypass_switch_is_on_from_position():
    entity, _ = _make_entity(
        EcostreamBypassSwitch, {"status": {"bypass_pos": 100}}
    )
    assert entity.is_on is True


@pytest.mark.asyncio
async def test_bypass_switch_turn_on_sends_payload():
    entity, coordinator = _make_entity(EcostreamBypassSwitch)
    await entity.async_turn_on()
    coordinator.ws.send_json.assert_called_once_with(
        {"config": {"man_override_bypass": 100, "man_override_bypass_time": 3600}}
    )


@pytest.mark.asyncio
async def test_bypass_switch_turn_off_sends_payload():
    entity, coordinator = _make_entity(EcostreamBypassSwitch)
    await entity.async_turn_off()
    coordinator.ws.send_json.assert_called_once_with(
        {"config": {"man_override_bypass": 0}}
    )



# ---------------------------------------------------------------------------
# EcostreamPresetSwitch
# ---------------------------------------------------------------------------


def test_preset_switch_unique_id_low():
    entity, _ = _make_entity(EcostreamPresetSwitch, preset=PRESET_LOW)
    assert entity.unique_id == "test_entry_preset_low"


def test_preset_switch_is_on_matches_qset():
    entity, _ = _make_entity(
        EcostreamPresetSwitch,
        {
            "config": {"setpoint_mid": 180},
            "status": {"qset": 180},
        },
        preset=PRESET_MID,
    )
    assert entity.is_on is True


def test_preset_switch_get_setpoint_unknown_preset():
    entity, _ = _make_entity(
        EcostreamPresetSwitch,
        {"config": {"setpoint_low": 90}},
        preset="unknown",
    )
    assert entity._get_setpoint() is None


def test_preset_switch_get_setpoint_invalid_value():
    entity, _ = _make_entity(
        EcostreamPresetSwitch,
        {"config": {"setpoint_low": "bad"}},
        preset=PRESET_LOW,
    )
    assert entity._get_setpoint() is None


def test_preset_switch_is_active_invalid_qset_returns_false():
    entity, _ = _make_entity(
        EcostreamPresetSwitch,
        {"config": {"setpoint_low": 90}, "status": {"qset": "bad"}},
        preset=PRESET_LOW,
    )
    assert entity.is_on is False


def test_preset_switch_handle_update_writes_state():
    entity, _ = _make_entity(
        EcostreamPresetSwitch,
        {"config": {"setpoint_low": 90}, "status": {"qset": 90}},
        preset=PRESET_LOW,
    )
    entity._handle_coordinator_update()
    cast(MagicMock, entity.async_write_ha_state).assert_called_once()


@pytest.mark.asyncio
async def test_preset_switch_turn_on_without_setpoint_skips_send():
    entity, coordinator = _make_entity(
        EcostreamPresetSwitch,
        {"config": {}},
        preset=PRESET_LOW,
    )
    await entity.async_turn_on()
    coordinator.ws.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_apply_config_uses_async_send_config_awaitable():
    entity, coordinator = _make_entity(EcostreamScheduleSwitch)
    coordinator.async_send_config = AsyncMock(return_value=True)
    await entity.async_turn_on()
    coordinator.async_send_config.assert_awaited_once_with(
        {"schedule_enabled": True}, "schedule"
    )


@pytest.mark.asyncio
async def test_preset_switch_turn_on_sends_payload():
    entity, coordinator = _make_entity(
        EcostreamPresetSwitch,
        {"config": {"setpoint_high": 270}},
        preset=PRESET_HIGH,
    )
    entity._entry.options = {CONF_PRESET_OVERRIDE_MINUTES: 30}
    await entity.async_turn_on()
    coordinator.ws.send_json.assert_called_once_with(
        {
            "config": {
                "man_override_set": 270.0,
                "man_override_set_time": 1800,
            }
        }
    )


@pytest.mark.asyncio
async def test_preset_switch_turn_on_uses_default_minutes():
    entity, coordinator = _make_entity(
        EcostreamPresetSwitch,
        {"config": {"setpoint_low": 90}},
        preset=PRESET_LOW,
    )
    await entity.async_turn_on()
    coordinator.ws.send_json.assert_called_once_with(
        {
            "config": {
                "man_override_set": 90.0,
                "man_override_set_time": DEFAULT_PRESET_OVERRIDE_MINUTES
                * 60,
            }
        }
    )


@pytest.mark.asyncio
async def test_preset_switch_turn_off_clears_override():
    entity, coordinator = _make_entity(
        EcostreamPresetSwitch,
        {"config": {"setpoint_low": 90}},
        preset=PRESET_LOW,
    )
    await entity.async_turn_off()
    coordinator.ws.send_json.assert_called_once_with(
        {"config": {"man_override_set_time": 0}}
    )


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.skip(reason="Fixtures not implemented")
async def test_switch_turn_on_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test error handling when turning on switch."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.ecostream.EcostreamApiClient",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(
            mock_config_entry.entry_id
        )
        await hass.async_block_till_done()

    mock_client.async_set_bypass.side_effect = Exception("Error")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.ecostream_192_168_1_1_bypass"},
            blocking=True,
        )
