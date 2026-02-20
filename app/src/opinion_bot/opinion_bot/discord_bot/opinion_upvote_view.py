from __future__ import annotations

from typing import Callable, Awaitable

import discord
import structlog

from opinion_bot.opinion_bot.discord_bot.discord_bot_const import UPVOTE_BUTTON_ID


logger = structlog.get_logger(__name__)

class OpinionUpvoteView(discord.ui.View):
    """
    View wrapping an opinion message with a custom Upvote button.
    Used for registering a persistent view (upvote_handler should be passed then),
    and for posting an opinion (only as a UI template then, no handler needed)
    """

    def __init__(self, *, upvote_handler: Callable[[discord.Interaction], Awaitable[None]] | None = None) -> None:
        super().__init__(timeout=None)
        self._upvote_handler = upvote_handler

    @discord.ui.button(
        label="Upvote", # FIXME: move to const
        style=discord.ButtonStyle.primary,
        custom_id=UPVOTE_BUTTON_ID,
    )
    async def upvote(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self._upvote_handler is not None:
            await self._upvote_handler(interaction)
        else:
            # FIXME: turn into exception so this is reported
            logger.error("discord_bot.no_upvote_handler", custom_id=UPVOTE_BUTTON_ID)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        logger.exception(
            "discord_bot.view_error",
            item_type=type(item).__name__,
            custom_id=getattr(item, "custom_id", None),
        )
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Something went wrong handling that click. Please try again.",
                    ephemeral=True,
                )
        except Exception:
            logger.exception("discord_bot.view_error_failed_to_respond")