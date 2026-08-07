"""Tests for button entity."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from home_disconnect.message import Action, Message
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.button import SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME
from homeassistant.exceptions import HomeAssistantError

from . import setup_config_entry
from .const import MOCK_CONFIG_DATA

if TYPE_CHECKING:
    from home_disconnect.testutils import MockAppliance
    from homeassistant.core import HomeAssistant


async def test_setup(
    hass: HomeAssistant,
    mock_appliance: MockAppliance,  # noqa: ARG001
    patch_entity_description: None,  # noqa: ARG001
) -> None:
    """Test setting up entity."""
    assert await setup_config_entry(hass, MOCK_CONFIG_DATA)

    state = hass.states.get("button.fake_brand_homeappliance_activeprogram")
    assert state
    assert state.name == "Fake_brand HomeAppliance ActiveProgram"
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Fake_brand HomeAppliance ActiveProgram"

    state = hass.states.get("button.fake_brand_homeappliance_abortprogram")
    assert state
    assert state.name == "Fake_brand HomeAppliance AbortProgram"
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Fake_brand HomeAppliance AbortProgram"


async def test_start(
    hass: HomeAssistant,
    mock_appliance: MockAppliance,
    patch_entity_description: None,  # noqa: ARG001
) -> None:
    """Test pressing start button."""
    entity_id = "button.fake_brand_homeappliance_activeprogram"
    assert await setup_config_entry(hass, MOCK_CONFIG_DATA)
    await mock_appliance.entities["Test.SelectedProgram"].update({"value": 500})
    await hass.async_block_till_done()

    await hass.services.async_call(
        domain=BUTTON_DOMAIN,
        service=SERVICE_PRESS,
        service_data={ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_appliance.session.send_sync.assert_awaited_once_with(
        Message(
            resource="/ro/activeProgram",
            action=Action.POST,
            data={
                "program": 500,
                "options": [{"uid": 401, "value": None}, {"uid": 402, "value": None}],
            },
        )
    )


async def test_start_available_for_select_only_program(
    hass: HomeAssistant,
    mock_appliance: MockAppliance,
    patch_entity_description: None,  # noqa: ARG001
) -> None:
    """
    The start button must work for SELECT_ONLY programs too, not just SELECT_AND_START.

    Confirmed live on fork issue #21: selecting a SELECT_ONLY program only
    stages it and its options (a write to SelectedProgram), it doesn't start
    anything - a separate write to ActiveProgram is what starts it, and the
    official cloud integration's own debug log showed exactly that as two
    distinct requests. Program.start() already posts to ActiveProgram
    unconditionally regardless of execution type, so this was a pure
    availability-gating bug, not a protocol one.
    """
    entity_id = "button.fake_brand_homeappliance_activeprogram"
    assert await setup_config_entry(hass, MOCK_CONFIG_DATA)
    await mock_appliance.entities["Test.SelectedProgram"].update({"value": 506})
    await hass.async_block_till_done()

    await hass.services.async_call(
        domain=BUTTON_DOMAIN,
        service=SERVICE_PRESS,
        service_data={ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_appliance.session.send_sync.assert_awaited_once_with(
        Message(
            resource="/ro/activeProgram",
            action=Action.POST,
            data={
                "program": 506,
                "options": [{"uid": 401, "value": None}, {"uid": 402, "value": None}],
            },
        )
    )


async def test_start_stays_available_when_remote_start_not_allowed(
    hass: HomeAssistant,
    mock_appliance: MockAppliance,
    patch_entity_description: None,  # noqa: ARG001
) -> None:
    """
    The start button must stay visible/pressable even when remote start is currently refused.

    BSH.Common.Status.RemoteControlStartAllowed can only ever be flipped by a
    human physically at the appliance - no client, local or cloud, can set it
    remotely. Gating the button's availability on it made an expected, common
    appliance state look like an integration bug instead of a silently
    greyed-out button. async_press() is responsible for surfacing that state
    instead (see the test below).
    """
    entity_id = "button.fake_brand_homeappliance_activeprogram"
    assert await setup_config_entry(hass, MOCK_CONFIG_DATA)
    await mock_appliance.entities["Test.SelectedProgram"].update({"value": 500})
    await mock_appliance.entities["Test.ActiveProgram"].update({"access": "read"})
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state != "unavailable"


async def test_start_raises_when_remote_start_not_allowed(
    hass: HomeAssistant,
    mock_appliance: MockAppliance,
    patch_entity_description: None,  # noqa: ARG001
) -> None:
    """Pressing start while remote start isn't allowed must error, not silently no-op."""
    entity_id = "button.fake_brand_homeappliance_activeprogram"
    assert await setup_config_entry(hass, MOCK_CONFIG_DATA)
    await mock_appliance.entities["Test.SelectedProgram"].update({"value": 500})
    await mock_appliance.entities["Test.ActiveProgram"].update({"access": "read"})
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            domain=BUTTON_DOMAIN,
            service=SERVICE_PRESS,
            service_data={ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    assert exc_info.value.translation_key == "remote_start_not_allowed"
    mock_appliance.session.send_sync.assert_not_awaited()


async def test_abort(
    hass: HomeAssistant,
    mock_appliance: MockAppliance,
    patch_entity_description: None,  # noqa: ARG001
) -> None:
    """Test pressing abort button."""
    entity_id = "button.fake_brand_homeappliance_abortprogram"
    assert await setup_config_entry(hass, MOCK_CONFIG_DATA)

    await hass.services.async_call(
        domain=BUTTON_DOMAIN,
        service=SERVICE_PRESS,
        service_data={ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_appliance.session.send_sync.assert_awaited_once_with(
        Message(
            resource="/ro/values",
            action=Action.POST,
            data={"uid": 300, "value": True},
        )
    )
