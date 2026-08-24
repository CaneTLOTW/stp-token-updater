"""Central provider status, source and renewal coordinator."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import (
    EvccAuthenticationError,
    EvccClient,
    EvccConnectionError,
    EvccError,
    EvccRateLimitError,
    SponsorStatusError,
    parse_datetime,
    parse_sponsor_status,
)
from .const import (
    CONF_AUTOMATIC_UPDATES,
    CONF_DRY_RUN,
    CONF_RENEWAL_WINDOW_HOURS,
    CONF_STATUS_REFRESH_MINUTES,
    CONF_VERIFICATION_DELAY_SECONDS,
    CONF_WARNING_HOURS,
    DEFAULT_DRY_RUN,
    DOMAIN,
    EVENT_WARNING,
    REPAIR_AUTH,
    REPAIR_CRITICAL,
    REPAIR_EXPIRED,
    REPAIR_SOURCE,
    REPAIR_WARNING,
    REPAIR_YAML_CONFLICT,
    SOURCE_REFRESH_NORMAL,
    SOURCE_REFRESH_RENEWAL,
    SOURCE_REFRESH_WARNING,
)
from .models import TrialTokenCandidate, TrialTokenMetadata, UpdaterState, UpdaterStatus
from .repairs import async_create_or_update, async_delete
from .scheduler import calculate_schedule, escalation_level, remaining_hours
from .storage import MetadataStore
from .trial_source import TrialSourceError, TrialTokenSource
from .verification import async_apply_and_verify

_LOGGER = logging.getLogger(__name__)


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value else None


def _dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(UTC)
    return parse_datetime(value)


class EvccTokenCoordinator(DataUpdateCoordinator[UpdaterState]):
    """One polling/update pipeline shared by all entities."""

    def __init__(
        self,
        hass,
        *,
        entry,
        client: EvccClient,
        source: TrialTokenSource,
        store: MetadataStore,
    ) -> None:
        self.entry = entry
        self.client = client
        self.source = source
        self.store = store
        options = {**entry.data, **entry.options}
        self.automatic_updates = bool(options.get(CONF_AUTOMATIC_UPDATES, True))
        self.dry_run = bool(options.get(CONF_DRY_RUN, DEFAULT_DRY_RUN))
        self.renewal_window_hours = int(options.get(CONF_RENEWAL_WINDOW_HOURS, 48))
        self.warning_hours = int(options.get(CONF_WARNING_HOURS, 6))
        self.verification_delay_seconds = float(
            options.get(CONF_VERIFICATION_DELAY_SECONDS, 3)
        )
        refresh_minutes = max(1, int(options.get(CONF_STATUS_REFRESH_MINUTES, 5)))
        self._candidate: TrialTokenCandidate | None = None
        self._state = UpdaterState(dry_run=self.dry_run)
        self._hydrate_from_store()
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(minutes=refresh_minutes),
        )

    @property
    def state(self) -> UpdaterState:
        return self.data or self._state

    async def _async_update_data(self) -> UpdaterState:
        return await self._run_cycle()

    async def _run_cycle(
        self,
        *,
        force_source: bool = False,
        force_apply: bool = False,
        automatic: bool = True,
    ) -> UpdaterState:
        now = datetime.now(UTC)
        current = self._state
        current.dry_run = self.dry_run
        current.updater_status = UpdaterStatus.CHECKING
        stored_active_before = self._stored_active_expiry()

        try:
            payload = await self.client.async_get_state()
            sponsor = parse_sponsor_status(payload)
            observed_expiry = sponsor.expires_at if sponsor and sponsor.expires_at else None
            current.reachable = True
            current.sponsor = sponsor
            current.active_expiry = observed_expiry or stored_active_before
            current.remaining = (
                current.active_expiry - now if current.active_expiry else None
            )
            current.last_check = now
            current.evcc_version = _extract_version(payload)
            current.last_error = None
            current.last_error_class = None
            self._handle_observed_token_cycle(
                current,
                observed_expiry=observed_expiry,
                stored_expiry=stored_active_before,
            )
        except EvccAuthenticationError as exc:
            return await self._failure_state(
                current, now, "auth_error", exc, REPAIR_AUTH
            )
        except (EvccConnectionError, EvccRateLimitError) as exc:
            return await self._failure_state(current, now, "evcc_error", exc, None)
        except (EvccError, SponsorStatusError) as exc:
            return await self._failure_state(current, now, "evcc_error", exc, None)

        if current.active_expiry is None:
            current.updater_status = UpdaterStatus.EVCC_ERROR
            current.last_error = "provider returned no sponsor expiry"
            current.last_error_class = "sponsor_status_missing"
            self.store.data.update(
                last_error_text=current.last_error,
                last_error_class=current.last_error_class,
                last_check_at=_iso(now),
            )
            await self.store.async_save()
            return await self._publish(current)

        if current.candidate and current.candidate.expires_at <= now:
            current.candidate = None
            current.candidate_is_newer = False
            self._clear_candidate_metadata()
        elif current.candidate:
            current.candidate_is_newer = (
                current.candidate.expires_at > current.active_expiry
            )

        last_schedule_action = _dt(self.store.data.get("last_schedule_action_at"))
        if last_schedule_action is None:
            last_schedule_action = _dt(self.store.data.get("last_update_attempt_at"))

        schedule = calculate_schedule(
            now=now,
            expires_at=current.active_expiry,
            last_attempt_at=last_schedule_action,
            renewal_window_hours=self.renewal_window_hours,
        )
        current.next_attempt = schedule.next_attempt

        scheduled_action_due = bool(
            automatic and self.automatic_updates and schedule.due
        )
        source_due = (
            force_source
            or force_apply
            or scheduled_action_due
            or self._source_due(now)
        )

        source_error: Exception | None = None
        if source_due:
            try:
                self._candidate = await self.source.async_get_latest(now=now)
                current.candidate = self._candidate.metadata
                current.candidate_is_newer = (
                    self._candidate.metadata.expires_at > current.active_expiry
                )
                current.last_source_check = now
                self.store.data.update(
                    candidate_expires_at=_iso(self._candidate.metadata.expires_at),
                    candidate_iat=_iso(self._candidate.metadata.issued_at),
                    candidate_token_fingerprint=self._candidate.metadata.fingerprint,
                    candidate_seen_at=_iso(now),
                    last_source_check_at=_iso(now),
                )
                async_delete(self.hass, REPAIR_SOURCE)
            except TrialSourceError as exc:
                source_error = exc
                current.last_source_check = now
                current.last_error = str(exc)
                current.last_error_class = "trial_source"
                self.store.data["last_source_check_at"] = _iso(now)
                async_create_or_update(self.hass, REPAIR_SOURCE)

        apply_requested = force_apply or scheduled_action_due
        schedule_action_processed = bool(
            scheduled_action_due or (force_apply and schedule.due)
        )
        if schedule_action_processed:
            self.store.data["last_schedule_action_at"] = _iso(now)

        yaml_conflict = bool(
            current.sponsor and current.sponsor.yaml_source == "file"
        )
        if yaml_conflict:
            async_create_or_update(self.hass, REPAIR_YAML_CONFLICT, critical=True)
        else:
            async_delete(self.hass, REPAIR_YAML_CONFLICT)

        if apply_requested:
            if yaml_conflict:
                current.last_error = "sponsor_token_managed_by_yaml"
                current.last_error_class = "configuration_conflict"
            elif source_error is None and self._candidate and current.candidate_is_newer:
                if self.dry_run:
                    current.last_update_attempt = now
                    current.update_attempts += 1
                    self.store.data.update(
                        last_update_attempt_at=_iso(now),
                        update_attempts=current.update_attempts,
                    )
                    current.last_error = "dry_run: sponsor token write was not sent"
                    current.last_error_class = "dry_run"
                else:
                    current.updater_status = UpdaterStatus.APPLYING
                    current.last_update_attempt = now
                    self.store.data["last_update_attempt_at"] = _iso(now)
                    self.store.data["update_attempts"] = int(
                        self.store.data.get("update_attempts", 0)
                    ) + 1
                    current.update_attempts = self.store.data["update_attempts"]
                    await self.store.async_save()
                    try:
                        result = await async_apply_and_verify(
                            self.client,
                            self._candidate,
                            first_delay=self.verification_delay_seconds,
                        )
                    except EvccAuthenticationError as exc:
                        await self._record_failure(current, now, type(exc).__name__)
                        async_create_or_update(self.hass, REPAIR_AUTH, critical=True)
                        result = None
                    except EvccRateLimitError as exc:
                        await self._record_failure(current, now, type(exc).__name__)
                        result = None
                    except EvccError as exc:
                        await self._record_failure(current, now, type(exc).__name__)
                        result = None
                    if result and result.success:
                        current.last_success = result.verified_at
                        current.active_expiry = (
                            result.observed_expiry or result.candidate_expiry
                        )
                        current.remaining = current.active_expiry - now
                        current.consecutive_failures = 0
                        current.last_error = None
                        current.last_error_class = None
                        self.store.data.update(
                            active_expires_at=_iso(current.active_expiry),
                            active_token_cycle_identifier=_iso(current.active_expiry),
                            active_token_fingerprint=self._candidate.metadata.fingerprint,
                            candidate_expires_at=None,
                            candidate_iat=None,
                            candidate_token_fingerprint=None,
                            candidate_seen_at=None,
                            last_success_at=_iso(result.verified_at),
                            consecutive_failures=0,
                            announced_escalation=None,
                        )
                        self._candidate = None
                        current.candidate = None
                        current.candidate_is_newer = False
                        async_delete(self.hass, REPAIR_AUTH)
                        async_delete(self.hass, REPAIR_WARNING)
                        async_delete(self.hass, REPAIR_CRITICAL)
                        async_delete(self.hass, REPAIR_EXPIRED)
                        _LOGGER.info(
                            "Sponsor token verified: new_expiry=%s",
                            _iso(current.active_expiry),
                        )
                    elif result:
                        await self._record_failure(
                            current,
                            now,
                            result.reason or "verification_failed",
                        )
                        if result.reason and "yaml" in result.reason:
                            async_create_or_update(
                                self.hass, REPAIR_YAML_CONFLICT, critical=True
                            )
            elif source_error is None:
                current.last_error = "no_newer_candidate"
                current.last_error_class = "no_newer_candidate"

        current.remaining = (
            current.active_expiry - now if current.active_expiry else None
        )
        if current.active_expiry:
            self.store.data["active_expires_at"] = _iso(current.active_expiry)
            self.store.data.setdefault(
                "active_token_cycle_identifier", _iso(current.active_expiry)
            )

        last_schedule_action = _dt(self.store.data.get("last_schedule_action_at"))
        schedule = calculate_schedule(
            now=now,
            expires_at=current.active_expiry,
            last_attempt_at=last_schedule_action,
            renewal_window_hours=self.renewal_window_hours,
        )
        current.next_attempt = schedule.next_attempt

        self.store.data["last_check_at"] = _iso(current.last_check)
        self.store.data["next_attempt_at"] = _iso(current.next_attempt)
        self.store.data["last_error_text"] = current.last_error
        self.store.data["last_error_class"] = current.last_error_class

        base_status = self._status_for(current, now, schedule)
        if source_error and base_status not in {
            UpdaterStatus.WARNING,
            UpdaterStatus.CRITICAL,
            UpdaterStatus.EXPIRED,
        }:
            current.updater_status = UpdaterStatus.SOURCE_ERROR
        else:
            current.updater_status = base_status

        await self._escalate(current, now)
        await self.store.async_save()
        return await self._publish(current)

    def _handle_observed_token_cycle(
        self,
        state: UpdaterState,
        *,
        observed_expiry: datetime | None,
        stored_expiry: datetime | None,
    ) -> None:
        """Reset escalation state when a genuinely newer token appears externally."""
        if observed_expiry is None:
            return
        observed_id = _iso(observed_expiry)
        stored_cycle = self.store.data.get("active_token_cycle_identifier")
        if stored_expiry is None:
            self.store.data["active_token_cycle_identifier"] = observed_id
            return
        if observed_expiry > stored_expiry and stored_cycle != observed_id:
            self.store.data.update(
                active_token_cycle_identifier=observed_id,
                announced_escalation=None,
                consecutive_failures=0,
            )
            state.consecutive_failures = 0
            async_delete(self.hass, REPAIR_WARNING)
            async_delete(self.hass, REPAIR_CRITICAL)
            async_delete(self.hass, REPAIR_EXPIRED)

    def _clear_candidate_metadata(self) -> None:
        self._candidate = None
        self.store.data.update(
            candidate_expires_at=None,
            candidate_iat=None,
            candidate_token_fingerprint=None,
            candidate_seen_at=None,
        )

    def _hydrate_from_store(self) -> None:
        data = self.store.data
        state = self._state
        state.active_expiry = _dt(data.get("active_expires_at"))
        state.last_check = _dt(data.get("last_check_at"))
        state.last_source_check = _dt(data.get("last_source_check_at"))
        state.last_update_attempt = _dt(data.get("last_update_attempt_at"))
        state.last_success = _dt(data.get("last_success_at"))
        state.next_attempt = _dt(data.get("next_attempt_at"))
        state.consecutive_failures = int(
            data.get("consecutive_failures", 0) or 0
        )
        state.update_attempts = int(data.get("update_attempts", 0) or 0)
        state.last_error = data.get("last_error_text")
        state.last_error_class = data.get("last_error_class")
        candidate_expiry = _dt(data.get("candidate_expires_at"))
        candidate_fingerprint = data.get("candidate_token_fingerprint")
        if candidate_expiry and isinstance(candidate_fingerprint, str):
            state.candidate = TrialTokenMetadata(
                issuer="evcc.io",
                subject="trial",
                issued_at=_dt(data.get("candidate_iat")),
                expires_at=candidate_expiry,
                fingerprint=candidate_fingerprint,
            )

    def _stored_active_expiry(self) -> datetime | None:
        return _dt(self.store.data.get("active_expires_at"))

    def _source_due(self, now: datetime) -> bool:
        last = _dt(self.store.data.get("last_source_check_at"))
        if last is None or self._state.active_expiry is None:
            return True
        remaining = self._state.active_expiry - now
        interval = SOURCE_REFRESH_NORMAL
        if remaining <= timedelta(hours=12):
            interval = SOURCE_REFRESH_WARNING
        elif remaining <= timedelta(hours=48):
            interval = SOURCE_REFRESH_RENEWAL
        return now - last >= interval

    async def _record_failure(
        self, state: UpdaterState, now: datetime, reason: str
    ) -> None:
        state.consecutive_failures += 1
        state.last_error = reason
        state.last_error_class = reason.split("_and_")[-1]
        self.store.data.update(
            consecutive_failures=state.consecutive_failures,
            last_error_class=state.last_error_class,
            last_error_text=state.last_error,
        )

    def _status_for(self, state: UpdaterState, now: datetime, schedule) -> UpdaterStatus:
        if state.active_expiry is None:
            return UpdaterStatus.EVCC_ERROR
        level = escalation_level(now, state.active_expiry, self.warning_hours)
        if level == "expired":
            return UpdaterStatus.EXPIRED
        if level == "critical":
            return UpdaterStatus.CRITICAL
        if level == "warning":
            return UpdaterStatus.WARNING
        if schedule.due:
            return UpdaterStatus.UPDATE_DUE
        if state.candidate_is_newer:
            return UpdaterStatus.NEW_TOKEN_AVAILABLE
        return UpdaterStatus.HEALTHY

    async def _escalate(self, state: UpdaterState, now: datetime) -> None:
        if not state.active_expiry:
            return
        level = escalation_level(now, state.active_expiry, self.warning_hours)
        announced = self.store.data.get("announced_escalation")
        order = {None: 0, "warning": 1, "critical": 2, "expired": 3}
        current = level if level in {"warning", "critical", "expired"} else None
        if current and order[current] > order.get(announced, 0):
            if current == "warning":
                async_create_or_update(self.hass, REPAIR_WARNING)
            elif current == "critical":
                async_create_or_update(self.hass, REPAIR_CRITICAL, critical=True)
            else:
                async_create_or_update(self.hass, REPAIR_EXPIRED, critical=True)
            self.hass.bus.async_fire(
                EVENT_WARNING,
                {
                    "level": current,
                    "remaining_hours": round(
                        remaining_hours(now, state.active_expiry), 3
                    ),
                    "expires_at": _iso(state.active_expiry),
                    "new_token_available": state.candidate_is_newer,
                    "consecutive_failures": state.consecutive_failures,
                    "error_class": state.last_error_class,
                    "next_attempt_at": _iso(state.next_attempt),
                },
            )
            self.store.data["announced_escalation"] = current

    async def _failure_state(
        self,
        state: UpdaterState,
        now: datetime,
        status: str,
        exc: Exception,
        repair: str | None,
    ) -> UpdaterState:
        state.reachable = False
        state.last_check = now
        state.last_error = str(exc)
        state.last_error_class = type(exc).__name__
        if state.active_expiry is None:
            state.active_expiry = self._stored_active_expiry()
        state.remaining = (
            state.active_expiry - now if state.active_expiry else None
        )
        if state.active_expiry:
            last_schedule_action = _dt(
                self.store.data.get("last_schedule_action_at")
            )
            schedule = calculate_schedule(
                now=now,
                expires_at=state.active_expiry,
                last_attempt_at=last_schedule_action,
                renewal_window_hours=self.renewal_window_hours,
            )
            state.next_attempt = schedule.next_attempt
            level = escalation_level(now, state.active_expiry, self.warning_hours)
            if level == "expired":
                state.updater_status = UpdaterStatus.EXPIRED
            elif level == "critical":
                state.updater_status = UpdaterStatus.CRITICAL
            elif level == "warning":
                state.updater_status = UpdaterStatus.WARNING
            else:
                state.updater_status = (
                    UpdaterStatus.AUTH_ERROR
                    if status == "auth_error"
                    else UpdaterStatus.EVCC_ERROR
                )
        else:
            state.updater_status = (
                UpdaterStatus.AUTH_ERROR
                if status == "auth_error"
                else UpdaterStatus.EVCC_ERROR
            )
        self.store.data.update(
            last_check_at=_iso(now),
            last_error_text=state.last_error,
            last_error_class=state.last_error_class,
            next_attempt_at=_iso(state.next_attempt),
        )
        if repair:
            async_create_or_update(
                self.hass, repair, critical=status == "auth_error"
            )
        await self._escalate(state, now)
        await self.store.async_save()
        return await self._publish(state)

    async def _publish(self, state: UpdaterState) -> UpdaterState:
        self._state = state
        return state

    async def async_check_now(self) -> None:
        result = await self._run_cycle(force_source=True, automatic=False)
        self.async_set_updated_data(result)

    async def async_apply_now(self) -> None:
        result = await self._run_cycle(
            force_source=True,
            force_apply=True,
            automatic=False,
        )
        self.async_set_updated_data(result)

    async def async_verify_now(self) -> None:
        result = await self._run_cycle(force_source=False, automatic=False)
        self.async_set_updated_data(result)


def _extract_version(payload: dict[str, Any]) -> str | None:
    for path in (("version",), ("result", "version"), ("info", "version")):
        value: Any = payload
        for part in path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(part)
        if isinstance(value, str) and value:
            return value
    return None
