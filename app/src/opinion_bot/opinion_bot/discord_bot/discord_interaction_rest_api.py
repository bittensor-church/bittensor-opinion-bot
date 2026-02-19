from typing import runtime_checkable, Protocol


@runtime_checkable
class DiscordInteractionRestAsyncAPI(Protocol):
    """
    Abstraction over Discord REST calls using interaction token to be used in the bot process.
    """
    async def delete_original_response(self, *, interaction_token: str):
        """Delete the original response to the interaction."""


@runtime_checkable
class DiscordInteractionRestAPI(Protocol):
    """
    Abstraction over Discord REST calls using interaction token to be used in celery workers.
    """
    def delete_original_response(self, *, interaction_token: str):
        """Delete the original response to the interaction."""
