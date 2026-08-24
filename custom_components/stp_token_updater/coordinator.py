"""Central provider status, source and renewal coordinator."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    ProviderApiError,
    ProviderAuthenticationError,
    ProviderClient,
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
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
    DEFAULT_AUTOMATIC_UPDATES,
    DEFAULT_DRY_RUN,
    DEFAULT_RENEWAL_WINDOW_HOURS,
    DEFAULT_STATUS_REFRESH_MINUTES,
    DEFAULT_VERIFICATION_DELAY_SECONDS,
    DEFAULT_WARNING_HOURS,
    DOMAIN,
    EVENT_WARNING,
    REPAIR_AUTH,
    REPAIR_CRITICAL,
    REPAIR_EXPIRED,
    REPAIR_RATE_LIMIT,
    REPAIR_SOURCE,
    REPAIR_WARNING,
    REPAIR_YAML_CONFLICT,
    SOURCE_REFRESH_EXPIRED,
    SOURCE_REFRESH_NORMAL,
    SOURCE_REFRESH_RENEWAL,
    SOURCE_REFRESH_WARNING,
    TRIAL_ISSUER,
    TRIAL_SUBJECT,
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


def _retry_seconds(now: datetime, retry_at: datetime | None) -> float | None:
    if retry_at is None:
        return None
    return max(1.0, (retry_at - now).total_seconds())


class StpTokenCoordinator(DataUpdateCoordinator[UpdaterState]):
    """One controlled pipeline shared by every STP entity."""

    def __init__(
        self,
        hass,
        *,
        entry,
        client: ProviderClient,
        source: TrialTokenSource,
        store: MetadataStore,
    ) -> None:
        self.entry = entry
        self.client = client
        self.source = source
        self.store = store
        options = {**entry.data, **entry.options}
        self.automatic_updates = bool(
            options.get(CONF_AUTOMATIC_UPDATES, DEFAULT_AUTOMATIC_UPDATES)
        )
        self.dry_run = bool(options.get(CONF_DRY_RUN, DEFAULT_DRY_RUN))
        self.renewal_window_hours = int(
            options.get(CONF_RENEWAL_WINDOW_HOURS, DEFAULT_RENEWAL_WINDOW_HOURS)
        )
        self.warning_hours = int(options.get(CONF_WARNING_HOURS, DEFAULT_WARNING_HOURS))
        self.verification_delay_seconds = float(
            options.get(
                CONF_VERIFICATION_DELAY_SECONDS,
                DEFAULT_VERIFICATION_DELAY_SECONDS,
            )
        )
        refresh_minutes = max(
            1,
            int(options.get(CONF_STATUS_REFRESH_MINUTES, DEFAULT_STATUS_REFRESH_MINUTES)),
        )
        self._candidate: TrialTokenCandidate | None = None
        self._state = UpdaterState(dry_run=self.dry_run)
        self._hydrate_from_store()
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(minutes=refresh_minutes),
            always_update=True,
        )

    @property
    def state(self) -> UpdaterState:
        return self.data if self.data is not None else self._state

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
        initial_refresh = self.data is None

        retry_not_before = _dt(self.store.data.get("retry_not_before"))
        rate_scope = self.store.data.get("rate_limit_scope")
        retry_apply_pending = bool(self.store.data.get("retry_apply_pending", False))
        current.retry_not_before = retry_not_before

        # If the provider itself asked us not to contact it yet, do not turn the
        # coordinator's 5-minute local tick into a rate-limit hammer.
        if (
            retry_not_before
            and retry_not_before > now
            and rate_scope in {"state", "auth"}
        ):
            current.reachable = False
            current.last_check = now
            current.last_error = "rate_limit_active"
            current.last_error_class = "rate_limited"
            current.updater_status = self._status_with_severity(
                current, now, UpdaterStatus.RATE_LIMITED
            )
            current.next_attempt = retry_not_before
            await self._persist_common(current)
            return self._publish(current)

        stored_active_before = self._stored_active_expiry()
        try:
            payload = await self.client.async_get_state()
            sponsor = parse_sponsor_status(payload)
        except ProviderAuthenticationError as exc:
            self._clear_expired_rate_limit_if_due(now, {"state", "auth"})
            async_create_or_update(self.hass, REPAIR_AUTH, critical=True)
            raise ConfigEntryAuthFailed("Token provider authentication failed") from exc
        except ProviderRateLimitError as exc:
            self._set_rate_limit(
                current,
                retry_at=exc.retry_after,
                scope="state",
                apply_pending=retry_apply_pending,
            )
            if initial_refresh:
                raise UpdateFailed(
                    "Token provider rate limited initial state request",
                    retry_after=_retry_seconds(now, exc.retry_after),
                ) from exc
            return await self._provider_failure(current, now, exc, rate_limited=True)
        except (ProviderConnectionError, ProviderApiError, SponsorStatusError) as exc:
            self._clear_expired_rate_limit_if_due(now, {"state", "auth"})
            if initial_refresh:
                raise UpdateFailed("Unable to read token provider state") from exc
            return await self._provider_failure(current, now, exc)

        self._clear_rate_limit_if_scope({"state", "auth"})
        async_delete(self.hass, REPAIR_AUTH)
        observed_expiry = sponsor.expires_at if sponsor and sponsor.expires_at else None
        current.reachable = True
        current.sponsor = sponsor
        current.active_expiry = observed_expiry or stored_active_before
        current.remaining = current.active_expiry - now if current.active_expiry else None
        current.last_check = now
        current.provider_version = _extract_version(payload)
        current.last_error = None
        current.last_error_class = None
        self._handle_observed_token_cycle(
            current,
            observed_expiry=observed_expiry,
            stored_expiry=stored_active_before,
        )

        if current.active_expiry is None:
            current.updater_status = UpdaterStatus.PROVIDER_ERROR
            current.last_error = "provider returned no sponsor expiry"
            current.last_error_class = "sponsor_status_missing"
            await self._persist_common(current)
            return self._publish(current)

        if current.candidate and current.candidate.expires_at <= now:
            current.candidate = None
            current.candidate_is_newer = False
            self._clear_candidate_metadata()
        elif current.candidate:
            current.candidate_is_newer = current.candidate.expires_at > current.active_expiry

        last_schedule_action = _dt(self.store.data.get("last_schedule_action_at"))
        schedule = calculate_schedule(
            now=now,
            expires_at=current.active_expiry,
            last_action_at=last_schedule_action,
            renewal_window_hours=self.renewal_window_hours,
        )

        rate_retry_due = bool(
            retry_apply_pending
            and retry_not_before
            and now >= retry_not_before
        )
        scheduled_action_due = bool(
            automatic and self.automatic_updates and schedule.due
        )
        apply_requested = force_apply or scheduled_action_due or rate_retry_due

        # A known future write/source Retry-After blocks only those network actions.
        rate_blocked = bool(
            retry_not_before
            and retry_not_before > now
            and rate_scope in {"write", "source"}
        )
        if rate_blocked and apply_requested:
            apply_requested = False
            current.retry_not_before = retry_not_before
            current.next_attempt = retry_not_before

        source_due = (
            force_source
            or force_apply
            or scheduled_action_due
            or rate_retry_due
            or self._source_due(now)
        ) and not (rate_blocked and rate_scope == "source")

        source_error: TrialSourceError | None = None
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
                self._clear_rate_limit_if_scope({"source"})
                async_delete(self.hass, REPAIR_SOURCE)
            except TrialSourceError as exc:
                source_error = exc
                current.last_source_check = now
                current.last_error = str(exc)
                current.last_error_class = "trial_source"
                self.store.data["last_source_check_at"] = _iso(now)
                async_create_or_update(self.hass, REPAIR_SOURCE)
                if exc.retry_after:
                    self._set_rate_limit(
                        current,
                        retry_at=exc.retry_after,
                        scope="source",
                        apply_pending=apply_requested,
                    )
                    rate_blocked = True

        # A scheduled checkpoint is considered processed even if no newer token
        # exists or the source is temporarily unavailable. This prevents the local
        # status poll from replaying the same checkpoint every five minutes.
        if scheduled_action_due:
            self.store.data["last_schedule_action_at"] = _iso(now)

        yaml_conflict = bool(current.sponsor and current.sponsor.yaml_source == "file")
        if yaml_conflict:
            async_create_or_update(self.hass, REPAIR_YAML_CONFLICT, critical=True)
        else:
            async_delete(self.hass, REPAIR_YAML_CONFLICT)

        if apply_requested and not rate_blocked:
            if yaml_conflict:
                current.last_error = "sponsor_token_managed_by_yaml"
                current.last_error_class = "configuration_conflict"
                self.store.data["retry_apply_pending"] = False
            elif source_error is None and self._candidate and current.candidate_is_newer:
                if self.dry_run:
                    # Dry-run deliberately does not increment the real POST counter.
                    current.last_error = "dry_run: sponsor token write was not sent"
                    current.last_error_class = "dry_run"
                    self.store.data["retry_apply_pending"] = False
                else:
                    current.updater_status = UpdaterStatus.APPLYING
                    current.last_update_attempt = now
                    current.update_attempts += 1
                    self.store.data.update(
                        last_update_attempt_at=_iso(now),
                        update_attempts=current.update_attempts,
                    )
                    await self.store.async_save()
                    try:
                        result = await async_apply_and_verify(
                            self.client,
                            self._candidate,
                            first_delay=self.verification_delay_seconds,
                        )
                    except ProviderAuthenticationError as exc:
                        await self._record_failure(current, type(exc).__name__)
                        async_create_or_update(self.hass, REPAIR_AUTH, critical=True)
                        raise ConfigEntryAuthFailed(
                            "Token provider authentication failed during update"
                        ) from exc
                    except ProviderRateLimitError as exc:
                        await self._record_failure(current, "rate_limited")
                        self._set_rate_limit(
                            current,
                            retry_at=exc.retry_after,
                            scope="write",
                            apply_pending=exc.retry_after is not None,
                        )
                        result = None
                    except ProviderError as exc:
                        await self._record_failure(current, type(exc).__name__)
                        self.store.data["retry_apply_pending"] = False
                        result = None
                    if result and result.success:
                        self._record_success(current, result.verified_at, result.observed_expiry)
                    elif result:
                        await self._record_failure(
                            current,
                            result.reason or "verification_failed",
                        )
                        self.store.data["retry_apply_pending"] = False
                        if result.reason and "yaml" in result.reason:
                            async_create_or_update(
                                self.hass, REPAIR_YAML_CONFLICT, critical=True
                            )
            elif source_error is None:
                current.last_error = "no_newer_candidate"
                current.last_error_class = "no_newer_candidate"
                self.store.data["retry_apply_pending"] = False

        # A Retry-After gate is only a temporary block. Once the due retry has
        # actually reached its source/write decision, remove the old gate and
        # its Repair unless that decision received a new future Retry-After.
        # This intentionally happens *after* the apply path so a pending write
        # cannot be discarded before its mandatory fresh source check.
        if rate_retry_due:
            self._clear_expired_rate_limit_if_due(now, {"source", "write"})

        current.remaining = current.active_expiry - now
        self.store.data["active_expires_at"] = _iso(current.active_expiry)
        self.store.data.setdefault(
            "active_token_cycle_identifier", _iso(current.active_expiry)
        )

        last_schedule_action = _dt(self.store.data.get("last_schedule_action_at"))
        schedule = calculate_schedule(
            now=now,
            expires_at=current.active_expiry,
            last_action_at=last_schedule_action,
            renewal_window_hours=self.renewal_window_hours,
        )
        retry_not_before = _dt(self.store.data.get("retry_not_before"))
        current.retry_not_before = retry_not_before
        current.next_attempt = (
            retry_not_before
            if bool(self.store.data.get("retry_apply_pending"))
            and retry_not_before
            and retry_not_before > now
            else schedule.next_attempt
        )

        base_status = self._status_for(
            current,
            now,
            schedule_stage=schedule.stage,
            yaml_conflict=yaml_conflict,
        )
        if source_error and base_status not in {
            UpdaterStatus.WARNING,
            UpdaterStatus.CRITICAL,
            UpdaterStatus.EXPIRED,
            UpdaterStatus.CONFIGURATION_CONFLICT,
        }:
            current.updater_status = UpdaterStatus.SOURCE_ERROR
        elif (
            retry_not_before
            and retry_not_before > now
            and base_status not in {
                UpdaterStatus.WARNING,
                UpdaterStatus.CRITICAL,
                UpdaterStatus.EXPIRED,
                UpdaterStatus.CONFIGURATION_CONFLICT,
            }
        ):
            current.updater_status = UpdaterStatus.RATE_LIMITED
        else:
            current.updater_status = base_status

        await self._escalate(current, now)
        await self._persist_common(current)
        return self._publish(current)

    def _record_success(
        self,
        state: UpdaterState,
        verified_at: datetime,
        observed_expiry: datetime | None,
    ) -> None:
        assert self._candidate is not None
        state.last_success = verified_at
        state.active_expiry = observed_expiry or self._candidate.metadata.expires_at
        state.consecutive_failures = 0
        state.last_error = None
        state.last_error_class = None
        self.store.data.update(
            active_expires_at=_iso(state.active_expiry),
            active_token_cycle_identifier=_iso(state.active_expiry),
            active_token_fingerprint=self._candidate.metadata.fingerprint,
            candidate_expires_at=None,
            candidate_iat=None,
            candidate_token_fingerprint=None,
            candidate_seen_at=None,
            last_success_at=_iso(verified_at),
            consecutive_failures=0,
            announced_escalation=None,
            retry_not_before=None,
            rate_limit_scope=None,
            retry_apply_pending=False,
        )
        self._candidate = None
        state.candidate = None
        state.candidate_is_newer = False
        state.retry_not_before = None
        for issue_id in (
            REPAIR_AUTH,
            REPAIR_RATE_LIMIT,
            REPAIR_WARNING,
            REPAIR_CRITICAL,
            REPAIR_EXPIRED,
        ):
            async_delete(self.hass, issue_id)
        _LOGGER.info("Sponsor token verified: new_expiry=%s", _iso(state.active_expiry))

    def _set_rate_limit(
        self,
        state: UpdaterState,
        *,
        retry_at: datetime | None,
        scope: str,
        apply_pending: bool,
    ) -> None:
        state.last_error = "rate_limited"
        state.last_error_class = "rate_limited"
        state.retry_not_before = retry_at
        self.store.data.update(
            retry_not_before=_iso(retry_at),
            rate_limit_scope=scope,
            retry_apply_pending=bool(apply_pending and retry_at),
            last_error_text="rate_limited",
            last_error_class="rate_limited",
        )
        async_create_or_update(self.hass, REPAIR_RATE_LIMIT)

    def _clear_rate_limit_if_scope(self, scopes: set[str]) -> None:
        if self.store.data.get("rate_limit_scope") not in scopes:
            return
        self.store.data.update(
            retry_not_before=None,
            rate_limit_scope=None,
            retry_apply_pending=False,
        )
        self._state.retry_not_before = None
        async_delete(self.hass, REPAIR_RATE_LIMIT)

    def _clear_expired_rate_limit_if_due(
        self,
        now: datetime,
        scopes: set[str],
    ) -> None:
        """Clear only a completed rate-limit gate, never a renewed one."""
        if self.store.data.get("rate_limit_scope") not in scopes:
            return
        retry_at = _dt(self.store.data.get("retry_not_before"))
        if retry_at is not None and retry_at > now:
            return
        self._clear_rate_limit_if_scope(scopes)

    def _handle_observed_token_cycle(
        self,
        state: UpdaterState,
        *,
        observed_expiry: datetime | None,
        stored_expiry: datetime | None,
    ) -> None:
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
                retry_not_before=None,
                rate_limit_scope=None,
                retry_apply_pending=False,
            )
            state.consecutive_failures = 0
            state.retry_not_before = None
            for issue_id in (
                REPAIR_RATE_LIMIT,
                REPAIR_WARNING,
                REPAIR_CRITICAL,
                REPAIR_EXPIRED,
            ):
                async_delete(self.hass, issue_id)

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
        state.retry_not_before = _dt(data.get("retry_not_before"))
        state.consecutive_failures = int(data.get("consecutive_failures", 0) or 0)
        state.update_attempts = int(data.get("update_attempts", 0) or 0)
        state.last_error = data.get("last_error_text")
        state.last_error_class = data.get("last_error_class")
        candidate_expiry = _dt(data.get("candidate_expires_at"))
        candidate_fingerprint = data.get("candidate_token_fingerprint")
        if candidate_expiry and isinstance(candidate_fingerprint, str):
            state.candidate = TrialTokenMetadata(
                issuer=TRIAL_ISSUER,
                subject=TRIAL_SUBJECT,
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
        if remaining <= timedelta(0):
            interval = SOURCE_REFRESH_EXPIRED
        elif remaining <= timedelta(hours=12):
            interval = SOURCE_REFRESH_WARNING
        elif remaining <= timedelta(hours=48):
            interval = SOURCE_REFRESH_RENEWAL
        else:
            interval = SOURCE_REFRESH_NORMAL
        return now - last >= interval

    async def _record_failure(self, state: UpdaterState, reason: str) -> None:
        state.consecutive_failures += 1
        state.last_error = reason
        state.last_error_class = reason.split("_and_")[-1]
        self.store.data.update(
            consecutive_failures=state.consecutive_failures,
            last_error_class=state.last_error_class,
            last_error_text=state.last_error,
        )

    def _status_for(
        self,
        state: UpdaterState,
        now: datetime,
        *,
        schedule_stage: str,
        yaml_conflict: bool,
    ) -> UpdaterStatus:
        assert state.active_expiry is not None
        level = escalation_level(now, state.active_expiry, self.warning_hours)
        if level == "expired":
            return UpdaterStatus.EXPIRED
        if level == "critical":
            return UpdaterStatus.CRITICAL
        if level == "warning":
            return UpdaterStatus.WARNING
        if yaml_conflict:
            return UpdaterStatus.CONFIGURATION_CONFLICT
        if schedule_stage in {"renewal_window", "t_minus_12h", "t_minus_6h", "t_minus_1h", "expiry"}:
            if state.candidate_is_newer:
                return UpdaterStatus.NEW_TOKEN_AVAILABLE
            return UpdaterStatus.RENEWAL_WINDOW
        if state.candidate_is_newer:
            return UpdaterStatus.NEW_TOKEN_AVAILABLE
        return UpdaterStatus.HEALTHY

    def _status_with_severity(
        self,
        state: UpdaterState,
        now: datetime,
        fallback: UpdaterStatus,
    ) -> UpdaterStatus:
        if not state.active_expiry:
            return fallback
        level = escalation_level(now, state.active_expiry, self.warning_hours)
        return {
            "expired": UpdaterStatus.EXPIRED,
            "critical": UpdaterStatus.CRITICAL,
            "warning": UpdaterStatus.WARNING,
        }.get(level, fallback)

    async def _escalate(self, state: UpdaterState, now: datetime) -> None:
        if not state.active_expiry:
            return
        level = escalation_level(now, state.active_expiry, self.warning_hours)
        announced = self.store.data.get("announced_escalation")
        order = {None: 0, "warning": 1, "critical": 2, "expired": 3}
        current = level if level in {"warning", "critical", "expired"} else None
        if not current or order[current] <= order.get(announced, 0):
            return
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
                "remaining_hours": round(remaining_hours(now, state.active_expiry), 3),
                "expires_at": _iso(state.active_expiry),
                "new_token_available": state.candidate_is_newer,
                "consecutive_failures": state.consecutive_failures,
                "error_class": state.last_error_class,
                "next_attempt_at": _iso(state.next_attempt),
            },
        )
        self.store.data["announced_escalation"] = current

    async def _provider_failure(
        self,
        state: UpdaterState,
        now: datetime,
        exc: Exception,
        *,
        rate_limited: bool = False,
    ) -> UpdaterState:
        state.reachable = False
        state.last_check = now
        state.last_error = str(exc)
        state.last_error_class = "rate_limited" if rate_limited else type(exc).__name__
        if state.active_expiry is None:
            state.active_expiry = self._stored_active_expiry()
        state.remaining = state.active_expiry - now if state.active_expiry else None
        fallback = UpdaterStatus.RATE_LIMITED if rate_limited else UpdaterStatus.PROVIDER_ERROR
        state.updater_status = self._status_with_severity(state, now, fallback)
        retry_at = _dt(self.store.data.get("retry_not_before"))
        state.retry_not_before = retry_at
        state.next_attempt = retry_at or state.next_attempt
        await self._escalate(state, now)
        await self._persist_common(state)
        return self._publish(state)

    async def _persist_common(self, state: UpdaterState) -> None:
        self.store.data.update(
            last_check_at=_iso(state.last_check),
            next_attempt_at=_iso(state.next_attempt),
            last_error_text=state.last_error,
            last_error_class=state.last_error_class,
            consecutive_failures=state.consecutive_failures,
            update_attempts=state.update_attempts,
        )
        await self.store.async_save()

    def _publish(self, state: UpdaterState) -> UpdaterState:
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
