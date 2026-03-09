from __future__ import annotations

import logging

import discord
import prometheus_client
from discord import app_commands
from django.conf import settings

from ..metrics import registry
from .discord_interaction_sdk_adapter import create_discord_interaction_sdk_adapter
from .discord_interaction_sdk_api import DiscordInteractionSdkAPI
from .domain import OpinionCommandEvent, OpinionUpvoteEvent
from .exceptions import BotRuntimeError
from .metrics import DiscordEventMeasurement, event_measurement_decorator
from .opinion import handle_opinion_command_event
from .opinion_upvote_view import OpinionUpvoteView
from .upvote import handle_opinion_upvote_event

logger = logging.getLogger(__name__)


# TODO: add "I am alive" tick metrics (like every 5 minutes)
# TODO: implement graceful shutdown
class OpinionBotClient(discord.Client):
    def __init__(
        self,
        *,
        intents: discord.Intents,
    ) -> None:
        super().__init__(intents=intents, max_ratelimit_timeout=30)
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

        @self.tree.command(
            guild=guild, name="opinion-upvote", description="Upvote given opinion on the current channel."
        )
        @app_commands.describe(opinion_id="Opinion Id")
        async def upvote_command(interaction: discord.Interaction, opinion_id: int) -> None:
            await self.upvote_command(interaction, opinion_id)

    @event_measurement_decorator("opinion_command")
    async def opinion(
        self, measurement: DiscordEventMeasurement, interaction: discord.Interaction, emoji: str, message: str
    ) -> None:
        adapter = create_discord_interaction_sdk_adapter(interaction, measurement)
        try:
            logger.debug(
                "Opinion command received channel_id=%s, user_id=%s, %s %s",
                interaction.channel_id,
                interaction.guild_id,
                emoji,
                message,
            )

            if interaction.channel_id is None:
                raise BotRuntimeError("Unexpected opinion command outside channel")

            opinion_event = OpinionCommandEvent(
                channel_id=interaction.channel_id,
                user=adapter.user,
                emoji=emoji.strip(),
                message=message,
            )

            outcome = await handle_opinion_command_event(
                event=opinion_event,
                discord_interaction_sdk_adapter=adapter,
            )
            logger.info("Opinion command processed [%s] %s", outcome, opinion_event)
            measurement.set_outcome(outcome)
        except Exception as exc:
            logger.exception("Opinion command failed")
            await self._try_respond_generic_error(adapter, message="Posting opinion failed. Please try again.")
            measurement.set_outcome_from_exception(exc)

    @event_measurement_decorator("upvote_command")
    async def upvote_command(
        self, measurement: DiscordEventMeasurement, interaction: discord.Interaction, opinion_id: int
    ) -> None:
        adapter = create_discord_interaction_sdk_adapter(interaction, measurement)
        try:
            logger.debug(
                "Upvote command received channel_id=%s, user_id=%s, opinion_id=%s",
                interaction.channel_id,
                interaction.guild_id,
                opinion_id,
            )

            if interaction.channel_id is None:
                raise BotRuntimeError("Unexpected upvote command outside channel")

            upvote_event = OpinionUpvoteEvent(
                channel_id=interaction.channel_id,
                opinion_id=opinion_id,
                user=adapter.user,
            )

            outcome = await handle_opinion_upvote_event(
                event=upvote_event,
                discord_interaction_sdk_adapter=adapter,
            )

            logger.info("Upvote command processed [%s] %s", outcome, upvote_event)
            measurement.set_outcome(outcome)
        except Exception as exc:
            logger.exception("Upvote command failed")
            await self._try_respond_generic_error(adapter, message="Posting opinion failed. Please try again.")
            measurement.set_outcome_from_exception(exc)

    @event_measurement_decorator("upvote_button_click")
    async def upvote_button_click(self, measurement: DiscordEventMeasurement, interaction: discord.Interaction) -> None:
        adapter = create_discord_interaction_sdk_adapter(interaction, measurement)
        try:
            logger.debug(
                "Upvote received channel_id=%s, message_id=%s, user_id=%s",
                interaction.channel_id,
                interaction.message.id if interaction.message is not None else None,
                interaction.user.id,
            )

            if interaction.channel_id is None:
                raise BotRuntimeError("Unexpected upvote outside channel")

            if interaction.message is None:
                raise BotRuntimeError("Unexpected upvote without message")

            upvote_event = OpinionUpvoteEvent(
                channel_id=interaction.channel_id,
                message_id=interaction.message.id,
                user=adapter.user,
            )

            outcome = await handle_opinion_upvote_event(
                event=upvote_event,
                discord_interaction_sdk_adapter=adapter,
            )

            logger.info("Opinion upvote processed [%s] %s", outcome, upvote_event)
            measurement.set_outcome(outcome)
        except Exception as exc:
            logger.exception("Opinion upvote failed")
            # TODO: when error occurred while showing final confirmation message the upvote was actually saved
            #       so this message is not adequate
            await self._try_respond_generic_error(adapter, message="Upvoting opinion failed. Please try again.")
            measurement.set_outcome_from_exception(exc)

    # TODO: handle user data changes including role changes
    # async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
    #     pass

    async def setup_hook(self) -> None:
        # Register persistent view for handling upvotes.
        self.add_view(OpinionUpvoteView(upvote_handler=self.upvote_button_click))

        # Sync app commands.
        guild = discord.Object(id=settings.DISCORD_GUILD_ID)
        try:
            synced = await self.tree.sync(guild=guild)
            logger.info("Slash command synced: %s", [c.name for c in synced])
        except discord.DiscordException:
            logger.exception("Slash commands sync failed")
            raise

    async def _try_respond_generic_error(self, adapter: DiscordInteractionSdkAPI, *, message: str) -> None:
        """
        Best-effort: try to tell the user something went wrong without raising secondary errors.
        Works whether we already responded/deferred or not (adapter handles that).
        """
        try:
            await adapter.followup_ephemeral(message)
        except Exception:
            logger.debug("Failed to respond with generic error message")

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
        if settings.DEBUG:
            logger.info(f"Starting prometheus metrics server on port 9000")
            prometheus_client.start_http_server(9000, registry=registry)

        intents = discord.Intents.none()
        intents.guilds = True
        # TODO: the following line needed for GUILD_MEMBER_UPDATE / on_member_update
        # intents.members = True

        bot_client = OpinionBotClient(intents=intents)
        # Prevent discord.py from installing its own logging handlers.
        bot_client.run(settings.DISCORD_BOT_TOKEN, log_handler=None)
    except Exception:
        logger.exception("Discord bot run crashed")
        raise
