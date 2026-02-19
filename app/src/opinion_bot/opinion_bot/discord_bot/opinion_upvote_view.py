from __future__ import annotations

from typing import Callable, Awaitable

import discord

from opinion_bot.opinion_bot.discord_bot.discord_bot_const import UPVOTE_BUTTON_ID


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
