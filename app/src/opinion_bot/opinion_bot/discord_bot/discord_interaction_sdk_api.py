from __future__ import annotations

from typing import Protocol, runtime_checkable

from opinion_bot.opinion_bot.discord_bot.domain import OpinionMessage, InteractionUser


@runtime_checkable
class DiscordInteractionSdkAPI(Protocol):
    """
    Opaque-to-the-app, but *capability based* interaction context.
    """

    @property
    def user(self) -> InteractionUser:
        """Interacting user's id."""

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

    async def publish_opinion(self, *, opinion_message: OpinionMessage) -> int:
        """Publish opinion to the channel, returns discord message id."""
