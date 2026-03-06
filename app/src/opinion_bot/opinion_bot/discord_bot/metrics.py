import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import wraps
from typing import Concatenate, ParamSpec, TypeVar

from prometheus_client import Histogram

from .domain import DiscordEventOutcome
from .exceptions import BotRuntimeError

# TODO: deal with discord.RateLimited (outcome = 'rate-limited') + separate histogram for rate limits with higher bucket sizes
# TODO: measure individual discord operations calls


# Buckets are examples; tune to your workload.
DISCORD_EVENT_DURATION_SECONDS = Histogram(
    "discord_event_duration_seconds",
    "Discord event handling duration split by time type",
    labelnames=("operation", "time_type", "outcome"),
    buckets=(0.1, 0.2, 0.5, 1, 2, 5, 10, 30),
)


@dataclass
class DiscordEventMeasurement:
    operation: str
    _start: float = 0.0
    _discord_seconds: float = 0.0
    _discord_user_confirmation_seconds: float = 0.0
    _finished: bool = False
    _discord_call_processing: bool = False
    _discord_span_start: float = 0.0
    _outcome: DiscordEventOutcome = "success"

    @classmethod
    @asynccontextmanager
    async def start_measurement(cls, operation: str):
        m = cls(operation=operation)
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

    def start(self) -> None:
        self._start = time.perf_counter()

    def finish(self) -> None:
        if self._finished:
            return
        self._finished = True

        # NOTE: user confirmation time not included in total (which include only processing time), but reported separately
        total = max(0.0, time.perf_counter() - self._start - self._discord_user_confirmation_seconds)
        bot = max(0.0, total - self._discord_seconds)

        labels = {"operation": self.operation, "outcome": self._outcome}
        DISCORD_EVENT_DURATION_SECONDS.labels(**labels, time_type="total").observe(total)
        DISCORD_EVENT_DURATION_SECONDS.labels(**labels, time_type="discord").observe(self._discord_seconds)
        DISCORD_EVENT_DURATION_SECONDS.labels(**labels, time_type="bot").observe(bot)
        DISCORD_EVENT_DURATION_SECONDS.labels(**labels, time_type="user_confirmation").observe(
            self._discord_user_confirmation_seconds
        )

    @asynccontextmanager
    async def discord_sdk_call(self, *, confirmation_message: bool = False):
        if self._discord_call_processing:
            raise BotRuntimeError("Nested discord SDK call")

        self._discord_call_processing = True
        discord_sdk_call_start_time = time.perf_counter()
        try:
            yield
        finally:
            self._discord_call_processing = False
            processing_time = time.perf_counter() - discord_sdk_call_start_time
            if confirmation_message:
                self._discord_user_confirmation_seconds += processing_time
            else:
                self._discord_seconds += processing_time


P = ParamSpec("P")
R = TypeVar("R")
S = TypeVar("S")


def event_measurement_decorator(
    operation: str,
) -> Callable[
    [Callable[Concatenate[S, DiscordEventMeasurement, P], Awaitable[R]]],
    Callable[Concatenate[S, P], Awaitable[R]],
]:
    def decorator(
        func: Callable[Concatenate[S, DiscordEventMeasurement, P], Awaitable[R]],
    ) -> Callable[Concatenate[S, P], Awaitable[R]]:
        @wraps(func)
        async def wrapper(self: S, *args: P.args, **kwargs: P.kwargs) -> R:
            async with DiscordEventMeasurement.start_measurement(operation) as measurement:
                return await func(self, measurement, *args, **kwargs)

        return wrapper

    return decorator
