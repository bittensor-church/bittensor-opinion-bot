from __future__ import annotations

import logging

import discord
from discord import app_commands
from django.conf import settings

from .discord_interaction_sdk_adapter import create_discord_interaction_sdk_adapter
from .domain import OpinionCommandEvent, OpinionUpvoteEvent
from .exceptions import BotRuntimeError
from .opinion import handle_opinion_command_event
from .opinion_upvote_view import OpinionUpvoteView
from .upvote import handle_opinion_upvote_event

logger = logging.getLogger(__name__)

# TODO: add "I am alive" tick metrics (like every 5 minutes)
class OpinionBotClient(discord.Client):
    def __init__(
        self,
        *,
        intents: discord.Intents,
    ) -> None:
        # TODO: set max_ratelimit_timeout and handle discord.RateLimited
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

        self._register_commands()

    def _register_commands(self) -> None:
        guild = discord.Object(id=settings.DISCORD_GUILD_ID)

        @self.tree.command(guild=guild, name="opinion", description="Post an opinion to the current channel.")
        @app_commands.describe(emoji="Emoji", message="Your opinion text")
        async def opinion_command(
            interaction: discord.Interaction, emoji: str, message: app_commands.Range[str, 1, 2000]
        ) -> None:
            await self.opinion(interaction, emoji, message)

    async def opinion(self, interaction: discord.Interaction, emoji: str, message: str) -> None:
        try:
            logger.debug(
                "Opinion command received channel_id=%s, user_id=%s, %s %s",
                interaction.channel_id,
                interaction.guild_id,
                emoji,
                message,
            )
            adapter = create_discord_interaction_sdk_adapter(interaction)

            if interaction.channel_id is None:
                await adapter.respond_ephemeral("This command must be used in a channel.")
                return

            adapter = create_discord_interaction_sdk_adapter(interaction)

            opinion_event = OpinionCommandEvent(
                channel_id=interaction.channel_id,
                user=adapter.user,
                emoji=emoji.strip(),
                message=message,
            )

            await handle_opinion_command_event(
                event=opinion_event,
                discord_interaction_sdk_adapter=adapter,
            )

            # TODO: log outcome (accepted / rejected)
            logger.info("Opinion command successfully processed %s", opinion_event)
        except Exception:
            # TODO: handle 429 separately
            logger.exception("Opinion command failed", exc_info=True)
            await self._try_respond_generic_error(interaction, message="Posting opinion failed. Please try again.")

    async def upvote(self, interaction: discord.Interaction) -> None:
        try:
            logger.debug(
                "Upvote received channel_id=%s, message_id=%s, user_id=%s",
                interaction.channel_id,
                interaction.message.id if interaction.message is not None else None,
                interaction.user.id,
            )
            adapter = create_discord_interaction_sdk_adapter(interaction)

            if interaction.channel_id is None:
                raise BotRuntimeError("Unexpected upvote outside channel")

            if interaction.message is None:
                raise BotRuntimeError("Unexpected upvote without message")

            upvote_event = OpinionUpvoteEvent(
                channel_id=interaction.channel_id,
                message_id=interaction.message.id,
                user=adapter.user,
            )

            await handle_opinion_upvote_event(
                event=upvote_event,
                discord_interaction_sdk_adapter=adapter,
            )

            # TODO: log outcome (accepted / rejected)
            logger.info("Opinion upvote successfully processed %s", upvote_event)
        except Exception:
            # TODO: handle 429 separately
            logger.exception("Opinion upvote failed", exc_info=True)
            # TODO: when error occurred while showing final confirmation message the upvote was actually saved
            #       so this message is not adequate
            await self._try_respond_generic_error(interaction, message="Upvoting opinion failed. Please try again.")

    # TODO: handle user data changes including role changes
    # async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
    #     pass

    async def setup_hook(self) -> None:
        # Register persistent view for handling upvotes.
        self.add_view(OpinionUpvoteView(upvote_handler=self.upvote))

        # Sync app commands.
        guild = discord.Object(id=settings.DISCORD_GUILD_ID)
        try:
            synced = await self.tree.sync(guild=guild)
            logger.info("Slash command synced: %s", [c.name for c in synced])
        except discord.DiscordException:
            logger.exception("Slash commands sync failed", exc_info=True)
            raise

    async def _try_respond_generic_error(self, interaction: discord.Interaction, *, message: str) -> None:
        """
        Best-effort: try to tell the user something went wrong without raising secondary errors.
        Works whether we already responded/deferred or not (adapter handles that).
        """
        try:
            adapter = create_discord_interaction_sdk_adapter(interaction)
            await adapter.followup_ephemeral(message)
        except Exception:
            logger.debug("Failed to respond with error message")

    async def on_ready(self) -> None:
        logger.info("Discord bot ready")

    # TODO: the following methods only for logging purposes (diagnosing interaction failures)
    async def on_disconnect(self) -> None:
        logger.debug("Discord bot disconnected")

    async def on_resumed(self) -> None:
        logger.debug("Discord bot resumed")

    async def on_error(self, event_method: str, /, *args, **kwargs) -> None:
        logger.exception("Unhandled discord bot error", exc_info=True)


def run_bot() -> None:
    try:
        intents = discord.Intents.none()
        intents.guilds = True
        # TODO: the following line needed for GUILD_MEMBER_UPDATE / on_member_update
        # intents.members = True

        bot_client = OpinionBotClient(intents=intents)
        # Prevent discord.py from installing its own logging handlers.
        bot_client.run(settings.DISCORD_BOT_TOKEN, log_handler=None)
    except Exception:
        logger.exception("Discord bot run crashed", exc_info=True)
        raise
