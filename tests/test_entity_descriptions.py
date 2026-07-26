"""Tests for entity descriptions."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock

from custom_components.homeconnect_ws import HCData, entity_descriptions
from custom_components.homeconnect_ws.entity_descriptions import (
    HCBinarySensorEntityDescription,
    HCLightEntityDescription,
    HCSelectEntityDescription,
    HCSensorEntityDescription,
    HCSwitchEntityDescription,
)
from custom_components.homeconnect_ws.entity_descriptions.common import (
    generate_power_switch,
    generate_program,
)
from custom_components.homeconnect_ws.entity_descriptions.cooking import generate_hood_light
from custom_components.homeconnect_ws.helpers import merge_dicts
from custom_components.homeconnect_ws.select import HCSelect
from home_disconnect.entities import Access, DeviceDescription, EntityDescription
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.switch import SwitchDeviceClass

if TYPE_CHECKING:
    import pytest
    from home_disconnect.testutils import MockAppliance, MockApplianceType


def test_merge_dicts() -> None:
    """Test merge dicts."""
    dict1 = {"a": [1, 2], "b": [3, 4]}
    dict2 = {"b": [5, 6], "c": [7, 8]}
    out_dict = merge_dicts(dict1, dict2)
    assert out_dict == {"a": [1, 2], "b": [3, 4, 5, 6], "c": [7, 8]}


MOCK_ENTITY_DESCRIPTIONS = {
    "binary_sensor": [
        HCBinarySensorEntityDescription(key="binary_sensor_available", entity="Test.BinarySensor"),
        HCBinarySensorEntityDescription(
            key="binary_sensor_not_available", entity="Test.BinarySensor2"
        ),
    ],
    "event_sensor": [
        HCSensorEntityDescription(
            key="sensor_event_available",
            entities=[
                "Test.Event1",
                "Test.Event2",
            ],
        ),
        HCSensorEntityDescription(
            key="sensor_event_not_available",
            entities=[
                "Test.Event1",
                "Test.Event3",
            ],
        ),
    ],
}


def test_get_available_entities(
    mock_appliance: MockAppliance, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test get_available_entities."""
    monkeypatch.setattr(
        entity_descriptions,
        "get_all_entity_description",
        Mock(return_value=MOCK_ENTITY_DESCRIPTIONS),
    )
    entities = entity_descriptions.get_available_entities(mock_appliance)
    assert entities["binary_sensor"] == [
        HCBinarySensorEntityDescription(key="binary_sensor_available", entity="Test.BinarySensor")
    ]
    assert entities["event_sensor"] == [
        HCSensorEntityDescription(
            key="sensor_event_available",
            entities=[
                "Test.Event1",
                "Test.Event2",
            ],
        )
    ]


POWER_SWITCH = {
    "setting": [
        {
            "access": "readwrite",
            "available": True,
            "enumeration": {"0": "MainsOff", "1": "Off", "2": "On", "3": "Standby"},
            "min": 0,
            "max": 2,
            "uid": 539,
            "name": "BSH.Common.Setting.PowerState",
        },
    ]
}


async def test_power_switch(mock_homeconnect_appliance: MockApplianceType) -> None:
    """Test dynamic Power switch."""
    device_description = POWER_SWITCH.copy()

    # On/Off Switch
    device_description["setting"][0]["min"] = 1
    device_description["setting"][0]["max"] = 2
    appliance = await mock_homeconnect_appliance(description=device_description)
    switch_description = generate_power_switch(appliance)

    assert switch_description["switch"][0] == HCSwitchEntityDescription(
        key="switch_power_state",
        entity="BSH.Common.Setting.PowerState",
        device_class=SwitchDeviceClass.SWITCH,
        value_mapping=("On", "Off"),
        force_off_when_expected_offline=True,
    )
    assert switch_description["select"][0].force_option_when_expected_offline == "off"
    assert switch_description["sensor"][0].force_option_when_expected_offline == "off"

    # No Switch
    device_description["setting"][0]["min"] = 0
    device_description["setting"][0]["max"] = 4
    appliance = await mock_homeconnect_appliance(description=device_description)
    switch_description = generate_power_switch(appliance)

    assert "switch" not in switch_description
    assert switch_description["select"][0].force_option_when_expected_offline == "off"
    assert switch_description["sensor"][0].force_option_when_expected_offline == "off"

    # On/MainsOff Switch - "Off" isn't one of this appliance's power states at
    # all, only "MainsOff" is, so forcing to "off" would return an option
    # SelectEntity doesn't recognize (confirmed live on fork issue #7 as the
    # entity's state silently degrading to "Unknown").
    device_description["setting"][0]["enumeration"] = {"0": "MainsOff", "2": "On"}
    appliance = await mock_homeconnect_appliance(description=device_description)
    switch_description = generate_power_switch(appliance)

    assert switch_description["switch"][0] == HCSwitchEntityDescription(
        key="switch_power_state",
        entity="BSH.Common.Setting.PowerState",
        device_class=SwitchDeviceClass.SWITCH,
        value_mapping=("On", "MainsOff"),
        force_off_when_expected_offline=True,
    )
    assert switch_description["select"][0].force_option_when_expected_offline == "mainsoff"
    assert switch_description["sensor"][0].force_option_when_expected_offline == "mainsoff"

    # Standby/Off Switch
    device_description["setting"][0]["enumeration"] = {"1": "Off", "3": "Standby"}
    appliance = await mock_homeconnect_appliance(description=device_description)
    switch_description = generate_power_switch(appliance)

    assert switch_description["switch"][0] == HCSwitchEntityDescription(
        key="switch_power_state",
        entity="BSH.Common.Setting.PowerState",
        device_class=SwitchDeviceClass.SWITCH,
        value_mapping=("Standby", "Off"),
        force_off_when_expected_offline=True,
    )
    assert switch_description["select"][0].force_option_when_expected_offline == "off"
    assert switch_description["sensor"][0].force_option_when_expected_offline == "off"

    # Neither "Off" nor "MainsOff" is a valid state for this appliance at all -
    # nothing to force to, so it should fall back to None rather than an
    # invalid option.
    device_description["setting"][0]["enumeration"] = {"2": "On", "3": "Standby"}
    appliance = await mock_homeconnect_appliance(description=device_description)
    switch_description = generate_power_switch(appliance)

    assert switch_description["select"][0].force_option_when_expected_offline is None
    assert switch_description["sensor"][0].force_option_when_expected_offline is None


HOOD_LIGHT = {
    "setting": [
        {
            "access": "readwrite",
            "available": True,
            "uid": 700,
            "name": "Cooking.Common.Setting.Lighting",
        },
        {
            "access": "readwrite",
            "available": True,
            "uid": 701,
            "name": "Cooking.Common.Setting.LightingBrightness",
        },
        {
            "access": "readwrite",
            "available": False,
            "uid": 702,
            "name": "Cooking.Hood.Setting.ColorTemperaturePercent",
        },
    ]
}


async def test_hood_light(mock_homeconnect_appliance: MockApplianceType) -> None:
    """
    A declared-but-unavailable ColorTemperaturePercent shouldn't be used.

    Confirmed live on fork issue #15 (Bosch DWK91LT60): the appliance
    declares ColorTemperaturePercent in its profile but marks it
    unavailable - checking membership alone picked that branch anyway,
    referencing an unavailable entity and making the whole light report
    Unavailable even though on/off + brightness control works fine.
    """
    appliance = await mock_homeconnect_appliance(description=HOOD_LIGHT)

    assert generate_hood_light(appliance) == HCLightEntityDescription(
        key="light_cooking_lighting",
        entity="Cooking.Common.Setting.Lighting",
        brightness_entity="Cooking.Common.Setting.LightingBrightness",
    )

    # Once the appliance actually reports it available, the color
    # temperature branch should be used.
    await appliance.entities["Cooking.Hood.Setting.ColorTemperaturePercent"].update(
        {"available": True}
    )
    assert generate_hood_light(appliance) == HCLightEntityDescription(
        key="light_cooking_lighting",
        entity="Cooking.Common.Setting.Lighting",
        brightness_entity="Cooking.Common.Setting.LightingBrightness",
        color_temperature_entity="Cooking.Hood.Setting.ColorTemperaturePercent",
    )


PROGRAM = DeviceDescription(
    setting=[
        EntityDescription(
            uid=101,
            name="BSH.Common.Setting.Favorite.001.Name",
            access=Access.READ_WRITE,
            available=True,
            max=30,
            min=0,
            default="Named Favorite",
        ),
        EntityDescription(
            uid=102,
            name="BSH.Common.Setting.Favorite.002.Name",
            access=Access.READ_WRITE,
            available=True,
            max=30,
            min=0,
            default="",
        ),
    ],
    program=[
        EntityDescription(
            uid=201,
            name="BSH.Common.Program.Favorite.001",
            available=True,
        ),
        EntityDescription(
            uid=202,
            name="BSH.Common.Program.Favorite.002",
            available=True,
        ),
        EntityDescription(
            uid=500,
            name="BSH.Common.Program.Program1",
        ),
    ],
)


async def test_program(mock_homeconnect_appliance: MockApplianceType) -> None:
    """Test dynamic Program."""
    appliance = await mock_homeconnect_appliance(description=PROGRAM)
    program_description = generate_program(appliance)
    assert program_description["program"][0] == HCSelectEntityDescription(
        key="select_program",
        entity="BSH.Common.Root.SelectedProgram",
        has_state_translation=False,
        mapping={
            "BSH.Common.Program.Favorite.001": "Named Favorite",
            "BSH.Common.Program.Favorite.002": "favorite_002",
            "BSH.Common.Program.Program1": "bsh_common_program_program1",
        },
    )
    assert program_description["active_program"][0] == HCSensorEntityDescription(
        key="sensor_active_program",
        entity="BSH.Common.Root.ActiveProgram",
        has_state_translation=False,
        device_class=SensorDeviceClass.ENUM,
        mapping={
            "BSH.Common.Program.Favorite.001": "Named Favorite",
            "BSH.Common.Program.Favorite.002": "favorite_002",
            "BSH.Common.Program.Program1": "bsh_common_program_program1",
        },
        clear_on_expected_offline=True,
    )

    appliance = await mock_homeconnect_appliance(description={})


HOOD_BOOST = DeviceDescription(
    info={"deviceID": "test_device_id"},
    option=[
        {
            "access": "readwrite",
            "available": True,
            # Matches the real IntensiveStage enum from a hood's own
            # FeatureMapping (confirmed live on fork issue #17) - a 3-way
            # stage, not a boolean, which is why this is a select rather
            # than a switch.
            "enumeration": {
                "0": "IntensiveStageOff",
                "1": "IntensiveStage1",
                "2": "IntensiveStage2",
            },
            "uid": 5000,
            "name": "Cooking.Common.Option.Hood.Boost",
        },
    ],
)


async def test_hood_boost_is_a_three_stage_select(
    mock_homeconnect_appliance: MockApplianceType,
) -> None:
    """switch_hood_boost was replaced by select_hood_boost - a boolean can't represent 2 stages."""
    appliance = await mock_homeconnect_appliance(description=HOOD_BOOST)
    runtime_data = HCData(
        appliance=appliance,
        device_info=MagicMock(),
        available_entity_descriptions=MagicMock(),
        coordinator=MagicMock(expected_offline=False),
    )
    entity_description = HCSelectEntityDescription(
        key="select_hood_boost",
        entity="Cooking.Common.Option.Hood.Boost",
        has_state_translation=True,
    )
    entity = HCSelect(entity_description, runtime_data)

    assert entity._attr_options == [
        "intensivestageoff",
        "intensivestage1",
        "intensivestage2",
    ]

    await appliance.entities["Cooking.Common.Option.Hood.Boost"].update({"value": 2})
    assert entity.current_option == "intensivestage2"


HOOD_COLOR_TEMPERATURE = DeviceDescription(
    info={"deviceID": "test_device_id"},
    setting=[
        {
            "access": "readwrite",
            "available": True,
            # Matches the real ColorTemperature enum from a hood's own
            # FeatureMapping (confirmed live on fork issue #15) - a mode
            # selector, distinct from ColorTemperaturePercent's raw value.
            "enumeration": {
                "0": "custom",
                "1": "warm",
                "2": "warmToNeutral",
                "3": "neutral",
                "4": "neutralToCold",
                "5": "cold",
            },
            "uid": 6000,
            "name": "Cooking.Hood.Setting.ColorTemperature",
        },
    ],
)


async def test_hood_color_temperature_mode_select(
    mock_homeconnect_appliance: MockApplianceType,
) -> None:
    """select_hood_color_temperature_mode exposes the hood's warm/neutral/cold enum."""
    appliance = await mock_homeconnect_appliance(description=HOOD_COLOR_TEMPERATURE)
    runtime_data = HCData(
        appliance=appliance,
        device_info=MagicMock(),
        available_entity_descriptions=MagicMock(),
        coordinator=MagicMock(expected_offline=False),
    )
    entity_description = HCSelectEntityDescription(
        key="select_hood_color_temperature_mode",
        entity="Cooking.Hood.Setting.ColorTemperature",
        has_state_translation=True,
    )
    entity = HCSelect(entity_description, runtime_data)

    assert entity._attr_options == [
        "custom",
        "warm",
        "warmtoneutral",
        "neutral",
        "neutraltocold",
        "cold",
    ]

    await appliance.entities["Cooking.Hood.Setting.ColorTemperature"].update({"value": 4})
    assert entity.current_option == "neutraltocold"
