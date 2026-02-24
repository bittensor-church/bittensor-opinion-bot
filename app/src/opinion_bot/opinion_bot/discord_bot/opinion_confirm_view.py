from __future__ import annotations

import discord

from opinion_bot.opinion_bot.discord_bot.exceptions import BotRuntimeError, discord_exception


class OpinionConfirmView(discord.ui.View):
    def __init__(self, *, author_id: int, timeout: float = 60.0) -> None:
        super().__init__(timeout=timeout)
        self._author_id = author_id
        self.confirmed: bool | None = None  # True/False when decided, None on timeout

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._author_id:
            raise BotRuntimeError("Unexpected public confirmation dialog")
        return True

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    @discord_exception
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._disable_buttons(interaction=interaction)
        self.confirmed = False
        self.stop()

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.primary)
    @discord_exception
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._disable_buttons(interaction=interaction)
        self.confirmed = True
        self.stop()

    @discord_exception
    async def _disable_buttons(self, interaction: discord.Interaction) -> None:
        for child in self.children:
            child.disabled = True
        try:
            # Try to give visual feedback (grey out buttons)
            await interaction.response.edit_message(view=self)
        except discord.NotFound:
            # Message gone, user dismissed it? Nothing to do.
            pass
