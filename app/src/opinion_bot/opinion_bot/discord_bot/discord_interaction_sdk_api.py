from __future__ import annotations

from typing import Protocol, runtime_checkable

from opinion_bot.opinion_bot.discord_bot.domain import OpinionMessage


@runtime_checkable
class DiscordInteractionSdkAPI(Protocol):
    """
    Opaque-to-the-app, but *capability based* interaction context.
    """

    @property
    def channel_id(self) -> int | None:
        """Channel where the interaction happened, if any."""

    @property
    def user_id(self) -> int:
        """Interacting user's id."""

    @property
    def user_role_ids(self) -> set[int]:
        """Interacting user's role ids."""

    async def defer_ephemeral(self) -> None:
        """Defer an ephemeral response to the interaction."""

    async def respond_ephemeral(self, content: str) -> None:
        """Send an ephemeral response to the interaction."""

    async def delete_response(self) -> None:
        """Delete the response to the interaction if sent."""

    async def followup_ephemeral(self, content: str) -> None:
        """Send an ephemeral followup message to the interaction."""

    async def show_confirmation_dialog(self, *, content: str) -> bool:
        """Show a confirmation dialog message to the user, return True if confirmed."""

    async def publish_opinion(self, *, opinion_message: OpinionMessage) -> None:
        """Publish opinion to the channel."""
