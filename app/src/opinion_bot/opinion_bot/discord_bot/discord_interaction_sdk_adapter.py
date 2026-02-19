from __future__ import annotations

from dataclasses import dataclass

import discord
import structlog

from .discord_bot_const import UPVOTE_BUTTON_ID
from .discord_interaction_sdk_api import DiscordInteractionSdkAPI
from .domain import OpinionMessage
from .opinion_upvote_view import OpinionUpvoteView

logger = structlog.get_logger(__name__)

_POSTED_OPINION_TEXT = "posted opinion"

# TODO: move to separate file
class OpinionConfirmView(discord.ui.View):
    def __init__(self, *, author_id: int, timeout: float = 60.0) -> None:
        super().__init__(timeout=timeout)
        self._author_id = author_id
        self.confirmed: bool | None = None  # True/False when decided, None on timeout

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._author_id:
            # TODO: should not occur, ignore with log? show ephemeral?
            raise RuntimeError("Unexpected public dialog")
        return True

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._disable_buttons(interaction=interaction)
        self.confirmed = False
        self.stop()

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.primary)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._disable_buttons(interaction=interaction)
        self.confirmed = True
        self.stop()

    async def _disable_buttons(self, interaction: discord.Interaction) -> None:
        for child in self.children:
            child.disabled = True
        try:
            # Try to give visual feedback (grey out buttons)
            await interaction.response.edit_message(view=self)
        except discord.NotFound:
            # Message gone, user dismissed it? Nothing to do.
            pass
        except Exception:
            # Any other error: log warning but don't crash, we will delete/cleanup soon anyway
            logger.warning("discord_interaction.cancel_edit_failed")

# FIXME: exception handling in each method, consider using a decorator, some methods may require handling discord.NotFound separately
@dataclass(slots=True)
class DiscordInteractionSdkAdapter(DiscordInteractionSdkAPI):
    _interaction: discord.Interaction

    @property
    def channel_id(self) -> int | None:
        channel = self._interaction.channel
        return getattr(channel, "id", None)

    @property
    def user_id(self) -> int:
        return self._interaction.user.id

    @property
    def user_role_ids(self) -> set[int]:
        return set([role.id for role in self._interaction.user.roles])

    async def defer_ephemeral(self) -> None:
        await self._interaction.response.defer(ephemeral=True)

    async def respond_ephemeral(self, content: str) -> None:
        if self._interaction.response.is_done():
            await self._interaction.edit_original_response(content=content)
        else:
            await self._interaction.response.send_message(content, ephemeral=True)

    async def delete_response(self) -> None:
        if self._interaction.response.is_done():
            await self._interaction.delete_original_response()

    async def followup_ephemeral(self, content: str) -> None:
        await self._interaction.followup.send(content, ephemeral=True)

    async def show_confirmation_dialog(self, *, content: str) -> bool: # FIXME: why bad signature? is it because of '*'?
        # FIXME: test timeout, move timeout to const
        view = OpinionConfirmView(author_id=self._interaction.user.id, timeout=60.0)
        try:
            if self._interaction.response.is_done():
                    await self._interaction.edit_original_response(content=content, view=view)
            else:
                await self._interaction.response.send_message(content, view=view, ephemeral=True)
        except Exception:
            # FIXME: error handling, do not treat it like no confirmation
            logger.exception("discord_interaction.confirmation_dialog_failed")
            return False

        await view.wait()
        # TODO: handle timeout by showing some ephemeral message

        return view.confirmed == True

    async def publish_opinion(self, *, opinion_message: OpinionMessage) -> None:  # FIXME: bad signature
        user_mention = f"<@{opinion_message.user_id}>"
        opinion_ref = f"#{format(opinion_message.opinion_id, 'x')}" # TODO: create hash ???
        message_header = f"{user_mention} {_POSTED_OPINION_TEXT} {opinion_ref}"
        message_content = f"{opinion_message.emoji} {opinion_message.message}"

        await self._interaction.channel.send(
            content=message_header,
            embed=discord.Embed(
                color=discord.Color.gold(),
                description=message_content
            ),
            view=OpinionUpvoteView()
        )
        # FIXME: exception handling


def create_discord_interaction_sdk_adapter(interaction: discord.Interaction) -> DiscordInteractionSdkAPI:
    return DiscordInteractionSdkAdapter(interaction)