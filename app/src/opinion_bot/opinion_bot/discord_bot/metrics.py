import datetime
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import wraps
from typing import Concatenate, ParamSpec, TypeVar

import discord
from prometheus_client import Histogram

from .domain import DiscordEventOutcome
from .exceptions import BotRuntimeError, DiscordInteractionRateLimited

DISCORD_EVENT_DURATION_SECONDS = Histogram(
    "discord_event_duration_seconds",
    "Discord event handling duration split by time type",
    labelnames=("operation", "time_type", "outcome"),
    buckets=(0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 30, 45, 60),
)

DISCORD_SDK_CALL_DURATION_SECONDS = Histogram(
    "discord_sdk_call_duration_seconds",
    "Discord SDK call duration",
    labelnames=("operation", "sdk_call_name", "sdk_outcome"),
    buckets=(0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 30, 45, 60),
)


@dataclass
class DiscordEventMeasurement:
    operation: str
    latency: float
    _start_time: float = 0.0
    _discord_seconds: float = 0.0
    _discord_user_confirmation_seconds: float = 0.0
    _finished: bool = False
    _discord_call_processing: bool = False
    _discord_span_start: float = 0.0
    _outcome: DiscordEventOutcome = "success"

    @classmethod
    @asynccontextmanager
    async def start_measurement(cls, *, operation: str, latency: float):
        m = cls(operation=operation, latency=latency)
        m.start()
        try:
            yield m
            m.finish()
        except Exception:
            m.set_outcome("unhandled_error")
            m.finish()
            raise

    def set_outcome(self, outcome: DiscordEventOutcome) -> None:
        self._outcome = outcome

    def set_outcome_from_exception(self, exc: Exception) -> None:
        outcome: DiscordEventOutcome = "rate_limited" if isinstance(exc, DiscordInteractionRateLimited) else "error"
        self.set_outcome(outcome)

    def start(self) -> None:
        self._start_time = time.perf_counter()

    def finish(self) -> None:
        if self._finished:
            return
        self._finished = True

        # NOTE: user confirmation time not included in event_handling_time (and total) but reported separately
        event_handling_time = max(0.0, time.perf_counter() - self._start_time - self._discord_user_confirmation_seconds)
        bot_time = max(0.0, event_handling_time - self._discord_seconds)

        labels = {"operation": self.operation, "outcome": self._outcome}
        DISCORD_EVENT_DURATION_SECONDS.labels(**labels, time_type="total").observe(event_handling_time + self.latency)
        DISCORD_EVENT_DURATION_SECONDS.labels(**labels, time_type="latency").observe(self.latency)
        DISCORD_EVENT_DURATION_SECONDS.labels(**labels, time_type="discord").observe(self._discord_seconds)
        DISCORD_EVENT_DURATION_SECONDS.labels(**labels, time_type="bot").observe(bot_time)
        DISCORD_EVENT_DURATION_SECONDS.labels(**labels, time_type="user").observe(
            self._discord_user_confirmation_seconds
        )

    @asynccontextmanager
    async def discord_sdk_call(self, *, sdk_call_name: str, is_confirmation_message: bool = False):
        outcome: DiscordEventOutcome = "success"
        self.start_sdk_call()
        try:
            yield
        except discord.RateLimited:
            outcome = "rate_limited"
            raise
        except Exception:
            outcome = "error"
            raise
        finally:
            self.finish_sdk_call(
                sdk_call_name=sdk_call_name, outcome=outcome, is_confirmation_message=is_confirmation_message
            )

    def start_sdk_call(self) -> None:
        if self._discord_call_processing:
            raise BotRuntimeError("Nested discord SDK call")
        self._discord_call_processing = True
        self._discord_span_start = time.perf_counter()

    def finish_sdk_call(
        self, *, sdk_call_name: str, outcome: DiscordEventOutcome, is_confirmation_message: bool = False
    ) -> None:
        self._discord_call_processing = False
        processing_time = time.perf_counter() - self._discord_span_start
        self._discord_seconds += processing_time
        if is_confirmation_message:
            self._discord_user_confirmation_seconds += processing_time
        else:
            self._discord_seconds += processing_time
        DISCORD_SDK_CALL_DURATION_SECONDS.labels(
            operation=self.operation, sdk_call_name=sdk_call_name, sdk_outcome=outcome
        ).observe(processing_time)


P = ParamSpec("P")
R = TypeVar("R")
S = TypeVar("S")


def event_measurement_decorator(
    operation: str,
) -> Callable[
    [Callable[Concatenate[S, DiscordEventMeasurement, discord.Interaction, P], Awaitable[R]]],
    Callable[Concatenate[S, discord.Interaction, P], Awaitable[R]],
]:
    def decorator(
        func: Callable[Concatenate[S, DiscordEventMeasurement, discord.Interaction, P], Awaitable[R]],
    ) -> Callable[Concatenate[S, discord.Interaction, P], Awaitable[R]]:
        @wraps(func)
        async def wrapper(self: S, interaction: discord.Interaction, *args: P.args, **kwargs: P.kwargs) -> R:
            latency = (datetime.datetime.now(datetime.UTC) - interaction.created_at).total_seconds()
            async with DiscordEventMeasurement.start_measurement(operation=operation, latency=latency) as measurement:
                return await func(self, measurement, interaction, *args, **kwargs)

        return wrapper

    return decorator
