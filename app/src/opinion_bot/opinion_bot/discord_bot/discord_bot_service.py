# app/src/opinion_bot/opinion_bot/discord_bot/discord_bot_service.py
from __future__ import annotations

import asyncio
import os
import sys
import threading
from typing import Final

import discord
import structlog

logger = structlog.get_logger(__name__)

# Temporary: hardcoded dev-server #general channel id (will be removed later)
GENERAL_CHANNEL_ID: Final[int] = 1470784158769873070

_thread: threading.Thread | None = None


def start_in_background() -> None:
    """
    Start the Discord gateway client in a background thread.

    Keeps Django's runserver responsive while the bot maintains a websocket connection.
    """
    global _thread

    if _thread is not None and _thread.is_alive():
        logger.info("discord_bot.already_running")
        return

    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        logger.warning("discord_bot.missing_token", env_var="DISCORD_BOT_TOKEN")
        return

    def _runner() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        intents = discord.Intents.none()
        intents.guilds = True
        intents.members = True  # needed for GUILD_MEMBER_UPDATE / on_member_update

        client = discord.Client(intents=intents)

        @client.event
        async def on_ready() -> None:
            logger.info("discord_bot.ready", user=str(client.user))

            channel = client.get_channel(GENERAL_CHANNEL_ID)
            if channel is None:
                try:
                    channel = await client.fetch_channel(GENERAL_CHANNEL_ID)
                except Exception:
                    logger.exception("discord_bot.fetch_channel_failed", channel_id=GENERAL_CHANNEL_ID)
                    return

            if not isinstance(channel, (discord.TextChannel, discord.Thread)):
                logger.warning(
                    "discord_bot.channel_not_text_like",
                    channel_id=GENERAL_CHANNEL_ID,
                    channel_type=type(channel).__name__,
                )
                return

            try:
                await channel.send("Opinion Bot connected (test message).")
                logger.info("discord_bot.test_message_sent", channel_id=GENERAL_CHANNEL_ID)
            except Exception:
                logger.exception("discord_bot.send_failed", channel_id=GENERAL_CHANNEL_ID)

        @client.event
        async def on_member_update(before: discord.Member, after: discord.Member) -> None:
            # Minimal logging: proves we receive GUILD_MEMBER_UPDATE.
            if before.roles != after.roles:
                logger.info(
                    "discord_bot.member_roles_updated",
                    guild_id=getattr(after.guild, "id", None),
                    member_id=after.id,
                    before_roles=len(before.roles),
                    after_roles=len(after.roles),
                )
            else:
                logger.info(
                    "discord_bot.member_updated",
                    guild_id=getattr(after.guild, "id", None),
                    member_id=after.id,
                )

        try:
            # Prevent discord.py from installing its own logging handlers; we use structlog.
            client.run(token, log_handler=None)
        except Exception:
            logger.exception("discord_bot.run_crashed")

    _thread = threading.Thread(target=_runner, name="discord-bot-thread", daemon=True)
    _thread.start()
    logger.info("discord_bot.started_in_background", channel_id=GENERAL_CHANNEL_ID, pid=os.getpid(), argv=sys.argv)