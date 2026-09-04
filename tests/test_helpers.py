"""Helper functions."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from custom_components.homeconnect_ws.helpers import (
    EntityMatch,
    ensure_writable,
    get_entities_from_regex,
    get_groups_from_regex,
    is_locked_option,
    is_option,
)
from homeassistant.exceptions import ServiceValidationError

from .const import DEVICE_DESCRIPTION

if TYPE_CHECKING:
    from home_disconnect.testutils import MockApplianceType


async def test_get_entities_from_regex(mock_homeconnect_appliance: MockApplianceType) -> None:
    """Test get_entities_from_regex helper."""
    appliance = await mock_homeconnect_appliance(description=DEVICE_DESCRIPTION)
    pattern = re.compile(r"^Test\.RegEx\.(.*)\..*$")
    result = get_entities_from_regex(appliance, pattern)
    assert result == [
        EntityMatch(entity="Test.RegEx.001.Sensor", groups=("001",)),
        EntityMatch(entity="Test.RegEx.002.Sensor", groups=("002",)),
        EntityMatch(entity="Test.RegEx.001.Switch", groups=("001",)),
        EntityMatch(entity="Test.RegEx.002.Switch", groups=("002",)),
    ]


async def test_get_groups_from_regex(mock_homeconnect_appliance: MockApplianceType) -> None:
    """Test get_groups_from_regex helper."""
    appliance = await mock_homeconnect_appliance(description=DEVICE_DESCRIPTION)
    pattern = re.compile(r"^Test\.RegEx\.(.*)\..*$")
    result = get_groups_from_regex(appliance, pattern)
    assert result == {("001",), ("002",)}


async def test_is_locked_option_true_when_option_read_only(
    mock_homeconnect_appliance: MockApplianceType,
) -> None:
    """
    Test an Option locked to read-only is reported as a locked option.

    Confirmed live on fork issue #59: Home Connect appliances lock some
    Options (e.g. iDos1) to read-only while a program runs, rather than
    making them unavailable - the official app shows them as
    visible-but-disabled, not hidden.
    """
    appliance = await mock_homeconnect_appliance(description=DEVICE_DESCRIPTION)
    option = appliance.entities["Test.Option1"]
    await option.update({"access": "read"})

    assert is_locked_option(option) is True


async def test_is_locked_option_false_when_option_writable(
    mock_homeconnect_appliance: MockApplianceType,
) -> None:
    """Test a normally writable Option is not treated as locked."""
    appliance = await mock_homeconnect_appliance(description=DEVICE_DESCRIPTION)
    option = appliance.entities["Test.Option1"]
    await option.update({"access": "readwrite"})

    assert is_locked_option(option) is False


async def test_is_locked_option_false_when_option_inapplicable(
    mock_homeconnect_appliance: MockApplianceType,
) -> None:
    """
    Test access=NONE stays genuinely unavailable rather than read-only.

    NONE means the option isn't applicable at all right now, a different
    signal from READ ("still readable, just not writable").
    """
    appliance = await mock_homeconnect_appliance(description=DEVICE_DESCRIPTION)
    option = appliance.entities["Test.Option1"]
    await option.update({"access": "none"})

    assert is_locked_option(option) is False


async def test_is_locked_option_false_for_non_option_entity(
    mock_homeconnect_appliance: MockApplianceType,
) -> None:
    """Test a Setting (not an Option) is never treated as a locked option."""
    appliance = await mock_homeconnect_appliance(description=DEVICE_DESCRIPTION)
    setting = appliance.entities["Test.Switch"]
    await setting.update({"access": "read"})

    assert is_locked_option(setting) is False


async def test_is_option_true_for_any_access(
    mock_homeconnect_appliance: MockApplianceType,
) -> None:
    """Test is_option is true for an Option regardless of its current access."""
    appliance = await mock_homeconnect_appliance(description=DEVICE_DESCRIPTION)
    option = appliance.entities["Test.Option1"]

    for access in ("none", "read", "readwrite"):
        await option.update({"access": access})
        assert is_option(option) is True


async def test_is_option_false_for_non_option_entity(
    mock_homeconnect_appliance: MockApplianceType,
) -> None:
    """Test a Setting (not an Option) is never treated as an Option."""
    appliance = await mock_homeconnect_appliance(description=DEVICE_DESCRIPTION)
    setting = appliance.entities["Test.Switch"]

    assert is_option(setting) is False


async def test_ensure_writable_raises_for_locked_option(
    mock_homeconnect_appliance: MockApplianceType,
) -> None:
    """Test ensure_writable raises a clear error for a read-only Option."""
    appliance = await mock_homeconnect_appliance(description=DEVICE_DESCRIPTION)
    option = appliance.entities["Test.Option1"]
    await option.update({"access": "read"})

    with pytest.raises(ServiceValidationError):
        ensure_writable(option)


async def test_ensure_writable_noop_for_writable_option(
    mock_homeconnect_appliance: MockApplianceType,
) -> None:
    """Test ensure_writable is a no-op for a writable Option."""
    appliance = await mock_homeconnect_appliance(description=DEVICE_DESCRIPTION)
    option = appliance.entities["Test.Option1"]
    await option.update({"access": "readwrite"})

    ensure_writable(option)
