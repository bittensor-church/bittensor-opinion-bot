from __future__ import annotations

from typing import Protocol, runtime_checkable

@runtime_checkable
class DiscordInteractionSdkAPI(Protocol):
    """
    Opaque-to-the-app, but *capability based* interaction context.

    Real impl: wraps discord.Interaction (or adapts it).
    Fake impl: simple dataclass/stub implementing these members.
    """

    @property
    def interaction_token(self) -> str:
        """Interaction token."""

    @property
    def channel_id(self) -> int | None:
        """Channel where the interaction happened, if any."""

    @property
    def user_id(self) -> int:
        """Interacting user's id."""

    async def defer_ephemeral(self) -> None:
        """Defer an ephemeral response to the interaction."""

    async def respond_ephemeral(self, content: str) -> None:
        """Send an ephemeral response to the interaction."""

    async def followup_ephemeral(self, content: str) -> None:
        """Send an ephemeral followup to the interaction."""

    # TODO: possible via REST API but breaks flow as response will be received via Websocket Gateway
    #       and we have to keep the state in DB
    async def show_confirmation_message(self, *, content: str) -> bool:
        """Show a confirmation dialog to the user, return True if confirmed."""
