"""Fan entities."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, NamedTuple

from home_disconnect.entities import Access
from home_disconnect.message import Action
from home_disconnect.message import Message as HC_Message
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util.percentage import percentage_to_ranged_value, ranged_value_to_percentage

from .const import DOMAIN
from .entity import HCEntity
from .helpers import (
    build_full_option_set,
    create_entities,
    entity_is_available,
    error_decorator,
    needs_full_option_set,
)

if TYPE_CHECKING:
    from home_disconnect.entities import Entity as HcEntity
    from home_disconnect.entities import Program
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import HCConfigEntry, HCData
    from .entity_descriptions.descriptions_definitions import HCFanEntityDescription

PARALLEL_UPDATES = 0


class SpeedMapping(NamedTuple):
    """Mapping of entity name / value and speed."""

    entity_name: str
    entity_value: int
    speed: int


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    config_entry: HCConfigEntry,
    async_add_entites: AddEntitiesCallback,
) -> None:
    """Set up fan platform."""
    entities = create_entities({"fan": HCFan}, config_entry.runtime_data)
    async_add_entites(entities)


_OPERATION_STATE_ENTITY = "BSH.Common.Status.OperationState"
_INACTIVE_OPERATION_STATES = frozenset({"inactive", "ready"})

_HOOD_FAN_STATE_ENTITIES = (
    "BSH.Common.Root.ActiveProgram",
    _OPERATION_STATE_ENTITY,
)


class HCFan(HCEntity, FanEntity):
    """Fan Entity."""

    entity_description: HCFanEntityDescription
    _speed_entities: dict[str, HcEntity]
    _speed_range: tuple[float, float]
    _speed_mapping: list[SpeedMapping]

    def __init__(
        self,
        entity_description: HCFanEntityDescription,
        runtime_data: HCData,
    ) -> None:
        super().__init__(entity_description, runtime_data)
        self._attr_supported_features = (
            FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_OFF | FanEntityFeature.TURN_ON
        )
        self._speed_mapping = []
        self._speed_entities = {}
        self._attr_speed_count = 0
        for entity_name in entity_description.entities or []:
            entity = self._runtime_data.appliance.entities[entity_name]
            self._speed_entities[entity_name] = entity
            for option in entity.enum or {}:
                if option != 0:
                    self._attr_speed_count += 1
                    self._speed_mapping.append(
                        SpeedMapping(
                            entity_name=entity_name,
                            entity_value=option,
                            speed=self._attr_speed_count,
                        )
                    )

        self._speed_range = (1, self._attr_speed_count)

    async def async_added_to_hass(self) -> None:
        if self.entity_description.key == "fan_hood":
            appliance = self._runtime_data.appliance
            for name in _HOOD_FAN_STATE_ENTITIES:
                entity = appliance.entities.get(name)
                if entity is not None and entity not in self._entities:
                    self._entities.append(entity)
        await super().async_added_to_hass()

    @property
    def available(self) -> bool:
        available = super().available
        for entity in self._speed_entities.values():
            available &= entity_is_available(entity, self.entity_description.available_access)
        return available

    @property
    def is_on(self) -> bool:
        appliance = self._runtime_data.appliance
        # Some hoods keep reporting an active Venting program with a non-zero
        # venting level after being switched off. OperationState is the
        # authoritative signal in that case.
        operation_state = appliance.entities.get(_OPERATION_STATE_ENTITY)
        if (
            operation_state is not None
            and str(operation_state.value or "").lower() in _INACTIVE_OPERATION_STATES
        ):
            return False
        if appliance.active_program is None:
            return False
        return any(entity.value_raw not in (None, 0) for entity in self._speed_entities.values())

    @property
    def percentage(self) -> int | None:
        if not self.is_on:
            return 0
        for speed in self._speed_mapping:
            if self._speed_entities[speed.entity_name].value_raw == speed.entity_value:
                return ranged_value_to_percentage(self._speed_range, speed.speed)
        return 0

    def _venting_program(self) -> Program:
        default_program = self.entity_description.default_program
        if default_program is None:
            msg = "Hood fan is missing default_program"
            raise ServiceValidationError(msg)
        if self._runtime_data.appliance.active_program is not None:
            return self._runtime_data.appliance.active_program
        return self._runtime_data.appliance.programs[default_program]

    def _speed_options(
        self,
        program: Program,
        *,
        entity_name: str | None = None,
        value: int = 0,
    ) -> dict[int, str | int | bool]:
        """Build writable fan option uids for the given program."""
        options: dict[int, str | int | bool] = {}
        # Program.options has no public accessor in the library yet.
        for option in program._options:  # noqa: SLF001
            if option.name not in self._speed_entities:
                continue
            if option.access != Access.READ_WRITE:
                continue
            if entity_name is None or option.name == entity_name:
                options[option.uid] = value
            else:
                options[option.uid] = 0
        return options

    @error_decorator
    async def async_set_percentage(self, percentage: int) -> None:
        new_speed = math.ceil(percentage_to_ranged_value(self._speed_range, percentage))
        if new_speed == 0:
            await self.async_turn_off()
            return

        new_speed_entity: str | None = None
        new_speed_value: int | None = None
        for speed in self._speed_mapping:
            if speed.speed == new_speed:
                new_speed_entity = speed.entity_name
                new_speed_value = speed.entity_value

        if new_speed_entity is None or new_speed_value is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="speed_invalid",
                translation_placeholders={"percentage": str(percentage)},
            )

        program = self._venting_program()
        options = self._speed_options(
            program,
            entity_name=new_speed_entity,
            value=new_speed_value,
        )
        if not options:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="speed_invalid",
                translation_placeholders={"percentage": str(percentage)},
            )

        await program.start(options)
        self.async_write_ha_state()

    @error_decorator
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        if percentage is None:
            program = self._venting_program()
            # Same 400 BadRequest as the start button / program select: an
            # appliance whose ActiveProgram is flagged fullOptionSet validates
            # a program write against the program's complete option set and
            # rejects an empty one. Confirmed live on a Bosch hood.
            options = (
                build_full_option_set(self._runtime_data.appliance, program)
                if needs_full_option_set(program)
                else {}
            )
            await program.start(options, override_options=True)
        else:
            await self.async_set_percentage(int(percentage))
        self.async_write_ha_state()

    @error_decorator
    async def async_turn_off(self, **kwargs: Any) -> None:
        appliance = self._runtime_data.appliance
        if appliance.active_program is None:
            return

        # Writing 0 to the speed options (the previous approach) is rejected
        # by some hoods - confirmed live via debug log (fork issue #17): the
        # appliance's confirmation echoes the option back at its old,
        # non-zero value instead of accepting 0. Deleting the active program
        # is the correct way to stop it, matching upstream issue #386.
        message = HC_Message(resource="/ro/activeProgram", action=Action.DELETE, data=[])
        await appliance.session.send_sync(message)
        self.async_write_ha_state()
