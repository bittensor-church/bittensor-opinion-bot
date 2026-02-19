# app/src/opinion_bot/opinion_bot/discord_bot/discord_bot_service.py
from __future__ import annotations

import asyncio
import os
import sys
import threading
from typing import Callable, Awaitable

import discord
import httpx
import structlog
from discord import app_commands

from .discord_bot_const import UPVOTE_BUTTON_ID
from .discord_bot_rest_api import DiscordBotRestAsyncAPI
from .discord_bot_settings import DiscordBotSettings, load_settings_from_env
from .discord_interaction_rest_api import DiscordInteractionRestAsyncAPI
from .discord_interaction_sdk_adapter import create_discord_interaction_sdk_adapter
from .domain import OpinionCommandEvent, OpinionUpvoteEvent
from .opinion import handle_opinion_command_event
from .upvote import handle_opinion_upvote_event

logger = structlog.get_logger(__name__)

_thread: threading.Thread | None = None

class OpinionUpvoteView(discord.ui.View):
    """
    Persistent view that handles button clicks for messages created via REST,
    as long as the message has a component button with custom_id == UPVOTE_BUTTON_ID.
    """

    def __init__(self, *, upvote_handler: Callable[[discord.Interaction], Awaitable[None]]) -> None:
        super().__init__(timeout=None) # FIXME: dlaczego None?
        self._upvote_handler = upvote_handler

    # FIXME: czy label i style mają znaczenie
    @discord.ui.button(
        label="Upvote",
        style=discord.ButtonStyle.primary,
        custom_id=UPVOTE_BUTTON_ID,
    )
    async def upvote(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._upvote_handler(interaction)

class OpinionBotClient(discord.Client):
    def __init__(
        self,
        *,
        intents: discord.Intents,
        settings: DiscordBotSettings,
        discord_interaction_rest_client: DiscordInteractionRestAsyncAPI,
        discord_bot_rest_client: DiscordBotRestAsyncAPI,
    ) -> None:
        super().__init__(intents=intents)
        self._settings = settings
        self._discord_interaction_rest_client = discord_interaction_rest_client
        self._discord_bot_rest_client = discord_bot_rest_client
        self.tree = app_commands.CommandTree(self)

        self._register_commands()

    def _register_commands(self) -> None:
        guild = discord.Object(id=self._settings.guild_id)

        # TODO: confirm available emojis and their labels
        @self.tree.command(guild=guild, name="opinion", description="Post an opinion to the current channel.")
        @app_commands.describe(emoji="Emoji", message="Your opinion text")
        @app_commands.choices(
            emoji=[
                app_commands.Choice(name="👍 Agree", value="👍"),
                app_commands.Choice(name="👎 Disagree", value="👎"),
                app_commands.Choice(name="🤔 Unsure", value="🤔"),
            ]
        )
        async def opinion_command(
                interaction: discord.Interaction,
                emoji: app_commands.Choice[str],
                message: app_commands.Range[str, 0, 240] | None = None
        ) -> None:
            await self.opinion(interaction, emoji.value, message)

        # FIXME: now arg validation version
        # @self.tree.command(guild=guild, name="opinion", description="Post an opinion to the current channel.")
        # @app_commands.describe(emoji="Emoji", message="Your opinion text")
        # async def opinion_command(
        #         interaction: discord.Interaction,
        #         emoji: str,
        #         message: str | None = None,
        # ) -> None:
        #     await self.opinion(interaction, emoji, message)

    async def opinion(self, interaction: discord.Interaction, emoji: str, message: str) -> None:
        if interaction.channel is None:
            # TODO: how is this possible
            await interaction.response.send_message("This command must be used in a channel.", ephemeral=True)
            return

        adapter = create_discord_interaction_sdk_adapter(interaction)
        event = OpinionCommandEvent(emoji=emoji, message=message)

        await handle_opinion_command_event(
            event=event,
            discord_interaction_sdk_adapter=adapter,
            discord_interaction_rest_client=self._discord_interaction_rest_client,
            discord_bot_rest_client=self._discord_bot_rest_client,
        )

    async def upvote(self, interaction: discord.Interaction) -> None:
        adapter = create_discord_interaction_sdk_adapter(interaction)
        upvote_event = OpinionUpvoteEvent(message_id=interaction.message.id, channel_id=interaction.channel.id)
        await handle_opinion_upvote_event(
            upvote_event=upvote_event,
            discord_interaction_sdk_adapter=adapter,
            discord_bot_rest_client=self._discord_bot_rest_client,
        )

    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
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

    async def setup_hook(self) -> None:
        # Register persistent view for REST-created message components.
        self.add_view(OpinionUpvoteView(upvote_handler=self.upvote))

        # Sync app commands.
        guild = discord.Object(id=self._settings.guild_id)
        try:
            synced = await self.tree.sync(guild=guild)
            logger.info(
                "discord_bot.slash_commands_synced",
                command_count=len(synced),
                commands=[c.name for c in synced],
            )
        except Exception:
            logger.exception("discord_bot.slash_commands_sync_failed")


def start_in_background(
        discord_bot_settings: DiscordBotSettings | None = None,
        discord_interaction_rest_client: DiscordBotRestAsyncAPI | None = None,
        discord_bot_rest_client: DiscordBotRestAsyncAPI | None = None,
) -> None:
    """
    Start the Discord gateway client in a background thread.
    """
    global _thread

    if _thread is not None and _thread.is_alive():
        logger.info("discord_bot.already_running")
        return

    discord_bot_settings = discord_bot_settings or load_settings_from_env()

    if discord_interaction_rest_client is None or discord_bot_rest_client is None:
        from .discord_interaction_rest_async_client import create_discord_interaction_rest_async_client # noqa: WPS433 (intentional local import)
        from .discord_bot_rest_async_client import create_discord_bot_rest_async_client # noqa: WPS433 (intentional local import)

        http_client = httpx.AsyncClient(timeout=10.0) # TODO: verity timeout

        discord_interaction_rest_client = discord_interaction_rest_client or create_discord_interaction_rest_async_client(
            discord_bot_settings=discord_bot_settings,
            client=http_client,
        )

        discord_bot_rest_client = discord_bot_rest_client or create_discord_bot_rest_async_client(
            settings=discord_bot_settings,
            client=http_client,
        )

    def _runner() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        intents = discord.Intents.none()
        intents.guilds = True
        intents.members = True  # needed for GUILD_MEMBER_UPDATE / on_member_update

        bot_client = OpinionBotClient(
            intents=intents,
            settings=discord_bot_settings,
            discord_interaction_rest_client=discord_interaction_rest_client,
            discord_bot_rest_client=discord_bot_rest_client,
        )

        try:
            # Prevent discord.py from installing its own logging handlers; we use structlog.
            bot_client.run(discord_bot_settings.token, log_handler=None)
        except Exception:
            logger.exception("discord_bot.run_crashed")

    _thread = threading.Thread(target=_runner, name="discord-bot-thread", daemon=True)
    _thread.start()
    logger.info("discord_bot.started_in_background", pid=os.getpid(), argv=sys.argv)