import asyncio

import structlog

from opinion_bot.opinion_bot.discord_bot.discord_interaction_sdk_api import DiscordInteractionSdkAPI
from opinion_bot.opinion_bot.discord_bot.domain import OpinionUpvoteEvent

logger = structlog.get_logger(__name__)

async def handle_opinion_upvote_event(
        *,
        upvote_event: OpinionUpvoteEvent,
        discord_interaction_sdk_adapter: DiscordInteractionSdkAPI,
) -> None:
    await discord_interaction_sdk_adapter.defer_ephemeral()

    await asyncio.sleep(5) # FIXME: temporary delay

    # TODO: save upvote in DB
    # FIXME: handle the case when users active upvote is already on this opinion

    # TODO: inform about moving the previous upvote
    # TODO: handle unimportant user variant
    await discord_interaction_sdk_adapter.followup_ephemeral("Upvoted!")
