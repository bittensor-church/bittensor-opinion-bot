from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, ParamSpec, TypeVar

import discord


class BotException(Exception):
    """Base class for all bot exceptions."""


class BotRuntimeError(BotException):
    """Raised when the bot encounters an unexpected state."""


class DiscordInteractionException(BotException):
    """Raised when discord interaction via discord sdk fails."""


P = ParamSpec("P")
R = TypeVar("R")


def discord_exception(func: Callable[P, Coroutine[Any, Any, R]]) -> Callable[P, Coroutine[Any, Any, R]]:
    """
    Decorator wrapping discord.DiscordException in bot's internal DiscordInteractionException
    """

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        # TODO: handle 429 separately
        try:
            return await func(*args, **kwargs)
        except discord.DiscordException as exc:
            raise DiscordInteractionException("Discord interaction failed.") from exc

    return wrapper
