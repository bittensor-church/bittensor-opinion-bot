from __future__ import annotations

from dataclasses import dataclass

import discord

from .discord_interaction_sdk_api import DiscordInteractionSdkAPI
from .domain import InteractionUser, OpinionMessage
from .exceptions import BotRuntimeError, discord_exception
from .opinion_confirm_view import OpinionConfirmView
from .opinion_upvote_view import OpinionUpvoteView


@dataclass(slots=True)
class DiscordInteractionSdkAdapter(DiscordInteractionSdkAPI):
    _interaction: discord.Interaction

    @property
    def user(self) -> InteractionUser:
        roles_ids = (
            [role.id for role in self._interaction.user.roles]
            if isinstance(self._interaction.user, discord.Member)
            else []
        )

        return InteractionUser(
            user_id=self._interaction.user.id,
            username=self._interaction.user.name,
            display_name=self._interaction.user.display_name,
            roles_ids=roles_ids,
        )

    @discord_exception
    async def defer_ephemeral(self) -> None:
        await self._interaction.response.defer(ephemeral=True)

    @discord_exception
    async def respond_ephemeral(self, content: str) -> None:
        if self._interaction.response.is_done():
            try:
                await self._interaction.edit_original_response(
                    content=content,
                    view=None,  # to handle replacing a confirmation message (that uses a view) with a plain one
                )
            except discord.NotFound:
                # Message gone, user dismissed it? Nothing to do.
                pass
        else:
            await self._interaction.response.send_message(content, ephemeral=True)

    @discord_exception
    async def delete_response(self) -> None:
        try:
            if self._interaction.response.is_done():
                await self._interaction.delete_original_response()
        except discord.NotFound:
            # Message gone, user dismissed it? Nothing to do.
            pass

    @discord_exception
    async def followup_ephemeral(self, content: str) -> None:
        if self._interaction.response.is_done():
            await self._interaction.followup.send(content, ephemeral=True)
        else:
            await self._interaction.response.send_message(content, ephemeral=True)

    # TODO: IDE shows incompatible signature
    @discord_exception
    async def show_confirmation_dialog(self, *, content: str) -> bool:
        view = OpinionConfirmView(author_id=self._interaction.user.id, timeout=60.0)
        if self._interaction.response.is_done():
            try:
                await self._interaction.edit_original_response(content=content, view=view)
            except discord.NotFound:
                # Message gone, user dismissed it? Assume they didn't want to proceed.
                return False
        else:
            await self._interaction.response.send_message(content, view=view, ephemeral=True)

        await view.wait()
        return bool(view.confirmed)

    # TODO: IDE shows incompatible signature
    @discord_exception
    async def publish_opinion(self, *, opinion_message: OpinionMessage) -> int:
        if not isinstance(self._interaction.channel, discord.TextChannel):
            raise BotRuntimeError("Unexpected non-text channel")
        view = OpinionUpvoteView()
        message = await self._interaction.channel.send(
            content=opinion_message.header,
            embed=discord.Embed(color=discord.Color.gold(), description=opinion_message.content),
            view=view,
        )
        view.stop()
        return message.id


def create_discord_interaction_sdk_adapter(interaction: discord.Interaction) -> DiscordInteractionSdkAPI:
    return DiscordInteractionSdkAdapter(interaction)
