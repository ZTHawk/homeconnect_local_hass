"""Button entities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from home_disconnect.entities import Execution
from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import HCEntity
from .helpers import create_entities, entity_is_available, error_decorator

if TYPE_CHECKING:
    from home_disconnect.entities import ActiveProgram, Command
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import HCConfigEntry
    from .entity_descriptions.descriptions_definitions import HCButtonEntityDescription

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    config_entry: HCConfigEntry,
    async_add_entites: AddEntitiesCallback,
) -> None:
    """Set up button platform."""
    entities = create_entities(
        {"button": HCButton, "start_button": HCStartButton}, config_entry.runtime_data
    )
    async_add_entites(entities)


class HCButton(HCEntity, ButtonEntity):
    """Abort Button Entity."""

    _entity: Command
    entity_description: HCButtonEntityDescription

    async def async_press(self) -> None:
        await self._entity.set_value(True)


class HCStartButton(HCEntity, ButtonEntity):
    """Start Button Entity."""

    _entity: ActiveProgram
    entity_description: HCButtonEntityDescription

    @property
    def available(self) -> bool:
        # Deliberately skips entity_is_available()'s access check (unlike
        # HCEntity.available): keep this button visible and pressable even
        # when the appliance is currently refusing remote start
        # (BSH.Common.Status.RemoteControlStartAllowed is false) - that's a
        # normal, common appliance state, not an integration bug. async_press
        # below checks access itself and raises a clear, actionable error
        # instead of a silently-greyed-out button, mirroring how the official
        # Home Connect cloud integration keeps its active-program select
        # always available regardless of remote-control state.
        if not self._runtime_data.appliance.session.connected:
            return False
        if not getattr(self._entity, "available", True):
            return False
        selected_program = self._runtime_data.appliance.selected_program
        if selected_program is None:
            return False
        # SELECT_ONLY needs this button too - see generate_start_button.
        return selected_program.execution in (
            Execution.SELECT_AND_START,
            Execution.SELECT_ONLY,
        )

    @error_decorator
    async def async_press(self) -> None:
        selected_program = self._runtime_data.appliance.selected_program
        if selected_program is None:
            return
        if not entity_is_available(self._entity, self.entity_description.available_access):
            device_name = self._runtime_data.device_info.get("name", "your appliance")
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="remote_start_not_allowed",
                translation_placeholders={"device_name": device_name},
            )
        await selected_program.start()
