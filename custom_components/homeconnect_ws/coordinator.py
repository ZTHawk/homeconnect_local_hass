"""Home Connect Coordinator."""

from __future__ import annotations

import asyncio
import logging
import time
from copy import deepcopy
from datetime import timedelta
from typing import TYPE_CHECKING

import aiohttp
from home_disconnect import (
    AllreadyConnectedError,
    ConnectionFailedError,
    ConnectionState,
    HCHandshakeError,
    HomeAppliance,
)
from homeassistant.const import CONF_DESCRIPTION, CONF_DEVICE_ID, CONF_HOST
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AES_IV,
    CONF_PSK,
    DOMAIN,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from homeassistant.core import HomeAssistant

    from . import HCConfigEntry

_LOGGER = logging.getLogger(__name__)

# A sustained "Can't connect" failure has more than one real cause (a stale/
# wrong encryption key, a genuinely offline appliance, or a stuck local API
# needing a power cycle - see the README's "websocket shutdown" section) -
# not something a single log line can diagnose, so point at the doc instead
# of guessing which one it is.
TROUBLESHOOTING_URL = (
    "https://github.com/vemboy200/homeconnect_local_hass"
    "#home-assistant-cannot-connect-to-my-appliance-what-should-i-do"
)

CONNECT_RETRY_INITIAL_DELAY = 5  # seconds
CONNECT_RETRY_MAX_DELAY = 60  # seconds

# Non-exempt appliance types block setup on a single successful connection
# (see test-before-setup in quality_scale.yaml), but a bare single attempt
# turned out to be too fragile: a momentary connection hiccup (e.g. a
# ConnectionResetError mid-handshake, confirmed live on fork issue #9 for a
# WasherDryer combo that was otherwise fully reachable) failed the whole
# config entry instead of just that one attempt, something 1.6.0's always-
# retrying background setup never did for any appliance type. A couple of
# quick attempts smooths over that class of blip without meaningfully
# delaying the case where the appliance really is unreachable - HA's own
# ConfigEntryNotReady backoff still takes over after this gives up.
SETUP_CONNECT_ATTEMPTS = 2
SETUP_CONNECT_RETRY_DELAY = 3  # seconds

# Standalone washers/dryers disable home-disconnect's own auto-reconnect (see
# reconect=False below) - this is the fallback that takes its place. Fixed,
# not exponential: unlike a connect failure at startup, we have no evidence
# a temporarily-offline laundry appliance takes long to come back once it
# does, and this is the guaranteed path (works even on networks where mDNS
# doesn't route multicast) - an mDNS-triggered immediate reconnect is a
# planned follow-up to shortcut this wait when discovery does work.
LAUNDRY_RECONNECT_POLL_INTERVAL = timedelta(seconds=20)

# Standalone washers and dryers routinely cut their own WiFi radio entirely
# when powered off between cycles (confirmed via fork issue #7 - a clean
# WebSocket close code 1000 followed by the device dropping off the LAN
# entirely, not just closing the local API). Being unreachable is a normal,
# expected state for these, not a fault: setup doesn't block on a successful
# connection, and connect failures don't get escalated past debug-level
# logging (see also upstream chris-mc1/homeconnect_local_hass issues #274 and
# #293). Washer/dryer *combo* units are deliberately excluded here - the one
# combo model checked (WNC254A0BY) stayed connected over Wi-Fi while powered
# off instead, closer to the dishwasher pattern, so combos get the same
# test-before-setup treatment as every other appliance type until there's
# evidence a given combo actually needs the exemption too.
EXPECTED_OFFLINE_APPLIANCE_TYPES = frozenset({"Washer", "Dryer"})


class HomeConnectCoordinator(DataUpdateCoordinator[None]):
    """My custom coordinator."""

    config_entry: HCConfigEntry
    appliance: HomeAppliance
    _connecting: bool = True
    connected: bool = False
    _escalate_connectivity_logging: bool
    _poll_unsub: Callable[[], None] | None = None
    # Laundry appliances have three independent triggers that can each call
    # appliance.connect() (the initial _connect() loop, the fallback poll, and
    # the mDNS nudge) - without this, two overlapping attempts would race:
    # the second one raises AllreadyConnectedError, whose handler closes the
    # shared session, tearing down the first attempt's in-progress connection
    # too. Serializes them so at most one is ever actually in flight.
    _connect_lock: asyncio.Lock

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HCConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=config_entry.data["description"]["info"]["vib"],
            config_entry=config_entry,
            always_update=True,
        )
        appliance_info = config_entry.data[CONF_DESCRIPTION].get("info", {})
        if not appliance_info:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="no_device_info",
            )
        self._escalate_connectivity_logging = (
            appliance_info.get("type") not in EXPECTED_OFFLINE_APPLIANCE_TYPES
        )
        self.appliance = HomeAppliance(
            description=deepcopy(config_entry.data[CONF_DESCRIPTION]),
            host=config_entry.data[CONF_HOST],
            app_name="Homeassistant",
            app_id=config_entry.data[CONF_DEVICE_ID],
            psk64=config_entry.data[CONF_PSK],
            iv64=config_entry.data.get(CONF_AES_IV, None),
            session=async_get_clientsession(hass),
            connection_callback=self._connection_state_callback,
            # Standalone washers/dryers get their own fallback-poll-based
            # reconnect (see LAUNDRY_RECONNECT_POLL_INTERVAL) instead of
            # home-disconnect's built-in one, so the two don't hammer the
            # appliance in parallel once the poll and the mDNS-triggered
            # reconnect (a planned follow-up) both exist.
            reconect=self._escalate_connectivity_logging,
        )
        self.disconnect_time = time.time()
        self._connect_lock = asyncio.Lock()

    @property
    def expected_offline(self) -> bool:
        """
        Whether being disconnected right now is expected, not a fault.

        True for appliance types confirmed to legitimately cut their own WiFi
        (EXPECTED_OFFLINE_APPLIANCE_TYPES), unless the *most recent* close
        code is positively known to be something other than a clean code-1000
        closure. No close code observed yet at all (None) also counts as
        expected here, not just 1000 - a fresh HA restart rebuilds the
        session from scratch, wiping last_close_code back to None before this
        process has ever connected, which otherwise made every entity show
        Unavailable on restart whenever the appliance simply happened to be
        off (confirmed live on fork issue #7). These appliance types are
        already treated as "unreachable is normal" everywhere else (no setup
        blocking, debug-only connect-failure logging), so a restart
        shouldn't be the one place that starts them out looking broken.
        """
        if self._escalate_connectivity_logging:
            return False
        return self.appliance.session.last_close_code in {None, 1000}

    async def close(self) -> None:
        self._connecting = False
        if self._poll_unsub is not None:
            self._poll_unsub()
            self._poll_unsub = None
        await self.appliance.close()

    async def _async_setup(self) -> None:
        if not self._escalate_connectivity_logging:
            # Standalone washer/dryer: connect in the background, non-blocking.
            # Being unreachable at setup is expected for these (see
            # EXPECTED_OFFLINE_APPLIANCE_TYPES), so we don't want a temporarily
            # powered-off appliance to prevent its entities from being created
            # at all. async_create_task() would still be tracked and waited on
            # by HA's own startup sequencing, which defeats the point - a
            # washer that's been off since before HA started could keep
            # _connect() retrying for a long time, blocking the rest of HA's
            # bootstrap for minutes (confirmed live on fork issue #16).
            # async_create_background_task() is explicitly documented not to
            # block startup or be waited on by async_block_till_done().
            self.config_entry.async_create_background_task(
                self.hass, self._connect(), "homeconnect_ws laundry connect"
            )
            # _connect() above only covers the *first* connection - it returns
            # for good once that succeeds. reconect=False (see __init__) means
            # home-disconnect won't auto-reconnect after a *later* drop either,
            # so this poll is what actually notices the appliance coming back.
            self._poll_unsub = async_track_time_interval(
                self.hass, self._async_poll_reconnect, LAUNDRY_RECONNECT_POLL_INTERVAL
            )
            return

        self.logger.debug(
            "Connecting to %s", self.config_entry.data[CONF_DESCRIPTION]["info"].get("vib")
        )
        last_err: Exception | None = None
        for attempt in range(SETUP_CONNECT_ATTEMPTS):
            if attempt:
                # A momentary connection hiccup (e.g. a reset mid-handshake)
                # shouldn't fail the whole config entry by itself - give the
                # appliance one more quick chance before falling back to HA's
                # own, much slower, ConfigEntryNotReady retry loop.
                await asyncio.sleep(SETUP_CONNECT_RETRY_DELAY)
            try:
                await self.appliance.connect()
            except Exception as err:  # noqa: BLE001 - retried, then re-raised below
                await self.appliance.close()
                last_err = err
                continue

            if self.appliance.session.connected:
                self.connected = True
                self.async_set_updated_data(None)
                return

            await self.appliance.close()

        msg = f"Can't connect to {self.config_entry.data[CONF_HOST]}"
        if last_err is not None:
            msg += f" ({type(last_err).__name__}: {last_err})"
        msg += f" - see {TROUBLESHOOTING_URL} if this doesn't resolve on its own"
        raise ConfigEntryNotReady(msg) from last_err

    async def _connect(self) -> None:
        self.logger.debug(
            "Connecting to %s", self.config_entry.data[CONF_DESCRIPTION]["info"].get("vib")
        )
        first_failure = True
        retry_delay = CONNECT_RETRY_INITIAL_DELAY
        while self._connecting:
            async with self._connect_lock:
                if self.connected:
                    # Another caller (poll/nudge) already connected while we
                    # were waiting for the lock.
                    return
                try:
                    await self.appliance.connect()
                    if self.appliance.session.connected:
                        self.connected = True
                        self.async_set_updated_data(None)
                        return
                except (ConnectionFailedError, HCHandshakeError, aiohttp.ClientResponseError):
                    # aiohttp.ClientResponseError (e.g. a 404 on the websocket upgrade)
                    # isn't wrapped by the library into ConnectionFailedError/
                    # HCHandshakeError, and doesn't trigger a connection state change
                    # either, so it needs to be handled here directly.
                    await self.appliance.close()
                    self.connected = False
                    msg = f"Can't connect to {self.config_entry.data[CONF_HOST]}, retrying"
                    if first_failure and self._escalate_connectivity_logging:
                        self.logger.error(msg)  # noqa: TRY400
                        first_failure = False  # first_failure_fix
                    else:
                        self.logger.debug(msg)
                except AllreadyConnectedError:
                    # Shouldn't happen now that _connect_lock serializes every
                    # caller - kept as a defensive fallback, not the expected path.
                    await self.appliance.close()
                    msg = f"Allready connected to {self.config_entry.data[CONF_HOST]}"
                    self.logger.error(msg)  # noqa: TRY400
                    return
                except Exception:
                    await self.appliance.close()
                    msg = f"Can't connect to {self.config_entry.data[CONF_HOST]}"
                    self.logger.exception(msg)

            if not self._connecting:
                # mypy can't see that close() (a different method) may have
                # flipped this flag while we were suspended on an await above.
                return  # type: ignore[unreachable]
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, CONNECT_RETRY_MAX_DELAY)

    async def _async_poll_reconnect(self, _now: datetime) -> None:
        """
        Fallback reconnect for standalone washers/dryers (reconect=False).

        Runs unconditionally, regardless of mDNS: it's the guaranteed path,
        not a backstop for a separate mDNS-driven reconnect (that's a planned
        follow-up, layered on top of this rather than replacing it).
        """
        if self.connected:
            return
        async with self._connect_lock:
            # Re-check: _connect()'s own loop, or an earlier poll/nudge
            # invocation, may have already connected while we waited for
            # the lock - mypy can't see that awaiting the lock above is a
            # suspension point where that can happen.
            if self.connected:
                return  # type: ignore[unreachable]
            try:
                await self.appliance.connect()
            except (
                ConnectionFailedError,
                HCHandshakeError,
                aiohttp.ClientResponseError,
                AllreadyConnectedError,
            ):
                self.logger.debug(
                    "Reconnect poll: still can't reach %s", self.config_entry.data[CONF_HOST]
                )
                await self.appliance.close()
            except Exception:
                self.logger.exception(
                    "Reconnect poll: unexpected error connecting to %s",
                    self.config_entry.data[CONF_HOST],
                )
                await self.appliance.close()
            else:
                if self.appliance.session.connected:
                    self.connected = True
                    self.async_set_updated_data(None)
                else:
                    await self.appliance.close()

    def async_nudge_reconnect(self) -> None:
        """
        Retry immediately instead of waiting out the fallback poll's interval.

        Called from the zeroconf discovery flow (see async_step_zeroconf) when
        this appliance re-announces itself on mDNS - the same discovery that
        drives initial setup already fires on every re-announcement, so this
        rides it rather than running a second, redundant listener. A no-op for
        non-exempt appliance types or while already connected.
        """
        if self._escalate_connectivity_logging or self.connected:
            return
        self.config_entry.async_create_background_task(
            self.hass,
            self._async_poll_reconnect(dt_util.utcnow()),
            "homeconnect_ws nudge reconnect",
        )

    async def _async_update_data(self) -> None:
        return None

    async def _connection_state_callback(self, event: ConnectionState) -> None:
        if event == ConnectionState.CONNECTED:
            if not self.connected:
                self.logger.info(
                    "Connection to %s restored",
                    self.config_entry.data[CONF_DESCRIPTION]["info"].get("vib"),
                )
            self.connected = True

        elif event in (ConnectionState.RECONNECTING, ConnectionState.ABNORMAL_CLOSURE):
            # ABNORMAL_CLOSURE covers a connection that has never succeeded yet
            # (e.g. the appliance is already unreachable when HA starts), since
            # the library only enters RECONNECTING after a prior successful
            # connection drops.
            if self.connected and self._escalate_connectivity_logging:
                self.logger.warning(
                    "Connection to %s lost",
                    self.config_entry.data[CONF_DESCRIPTION]["info"].get("vib"),
                )
            self.connected = False

        elif event == ConnectionState.CLOSED:
            self.connected = False

        self.async_set_updated_data(None)
