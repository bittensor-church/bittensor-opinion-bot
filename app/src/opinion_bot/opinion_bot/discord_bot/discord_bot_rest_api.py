from __future__ import annotations

from typing import runtime_checkable, Protocol

from opinion_bot.opinion_bot.discord_bot.domain import OpinionMessage, OpinionUpvoteEvent


@runtime_checkable
class DiscordBotRestAsyncAPI(Protocol):
    """
    Abstraction over Discord REST calls using bot token to be used in the bot process.
    """

    # TODO: we need discord message id from the response
    async def post_opinion_message(self, *, opinion_message: OpinionMessage) -> None:
        """Create a message in the given channel."""

    async def update_upvote_count(self, *, upvote_event: OpinionUpvoteEvent, upvote_count: int) -> None:
        """Update the upvote count for the given opinion."""

@runtime_checkable
class DiscordBotRestAPI(Protocol):
    """
    Abstraction over Discord REST calls using bot token to be used in celery workers.
    """

    # TODO: we need discord message id from the response
    def post_opinion_message(self, *, opinion_message: OpinionMessage) -> None:
        """Create a message in the given channel."""

    def update_upvote_count(self, *, upvote_event: OpinionUpvoteEvent, upvote_count: int) -> None:
        """Update the upvote count for the given opinion."""
