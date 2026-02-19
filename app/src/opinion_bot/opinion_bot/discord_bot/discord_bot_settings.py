from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final

_DISCORD_BOT_TOKEN_ENV_VAR: Final[str] = "DISCORD_BOT_TOKEN"
_DISCORD_GUILD_ID_ENV_VAR: Final[str] = "DISCORD_GUILD_ID"
_DISCORD_APPLICATION_ID_ENV_VAR: Final[str] = "DISCORD_APPLICATION_ID"

@dataclass(frozen=True, slots=True)
class DiscordBotSettings:
    token: str
    guild_id: int
    application_id: int


def load_settings_from_env() -> DiscordBotSettings:
    """
    Load Discord bot settings from environment variables.
    """
    token = os.environ.get(_DISCORD_BOT_TOKEN_ENV_VAR)
    if not token:
        raise RuntimeError(f"Missing required env var: {_DISCORD_BOT_TOKEN_ENV_VAR}")

    guild_id_raw = os.environ.get(_DISCORD_GUILD_ID_ENV_VAR)
    if not guild_id_raw:
        raise RuntimeError(f"Missing required env var: {_DISCORD_GUILD_ID_ENV_VAR}")

    try:
        guild_id = int(guild_id_raw)
    except ValueError as exc:
        raise RuntimeError(
            f"Invalid {_DISCORD_GUILD_ID_ENV_VAR}: expected integer, got {guild_id_raw!r}"
        ) from exc

    application_id_raw = os.environ.get(_DISCORD_APPLICATION_ID_ENV_VAR)
    if not application_id_raw:
        raise RuntimeError(f"Missing required env var: {_DISCORD_APPLICATION_ID_ENV_VAR}")

    try:
        application_id = int(application_id_raw)
    except ValueError as exc:
        raise RuntimeError(
            f"Invalid {_DISCORD_APPLICATION_ID_ENV_VAR}: expected integer, got {application_id_raw!r}"
        ) from exc

    return DiscordBotSettings(token=token, guild_id=guild_id, application_id=application_id)