import asyncio

import structlog

from opinion_bot.opinion_bot.discord_bot.discord_bot_rest_api import DiscordBotRestAsyncAPI
from opinion_bot.opinion_bot.discord_bot.discord_interaction_rest_api import DiscordInteractionRestAsyncAPI
from opinion_bot.opinion_bot.discord_bot.discord_interaction_sdk_api import DiscordInteractionSdkAPI
from opinion_bot.opinion_bot.discord_bot.domain import OpinionUpvoteEvent

logger = structlog.get_logger(__name__)

async def handle_opinion_upvote_event(
        *,
        upvote_event: OpinionUpvoteEvent,
        discord_interaction_sdk_adapter: DiscordInteractionSdkAPI,
        discord_bot_rest_client: DiscordBotRestAsyncAPI,
) -> None:
    await discord_interaction_sdk_adapter.defer_ephemeral()

    await asyncio.sleep(1) # FIXME: temporary delay

    # TODO: confirm upvote, confirm message cannot be done as edit_original_response because it replaces the original opinion message
    # previous_upvote = True # TODO: check in DB
    #
    # if previous_upvote:
    #     # TODO: upvote button leaves "working" state for a while before confirmation message is shown
    #     content = "**You have already upvoted the opinion**\n\n:heart: Some opinion text\n\nDo you want to move your upvote?"
    #     confirmed = await discord_interaction_sdk_adapter.show_confirmation_message(content=content)
    #     if confirmed:
    #         await discord_interaction_sdk_adapter.respond_ephemeral("Saving upvote...")
    # else:
    #     confirmed = True

    # TODO: save upvote in DB
    try:
        await discord_bot_rest_client.update_upvote_count(upvote_event=upvote_event, upvote_count=1)
        logger.info(
            "discord_bot.opinion_upvoted",
            message_id=upvote_event.message_id,
        )
    except Exception:
        logger.exception(
            "discord_bot.opinion_upvote_failed",
            message_id=upvote_event.message_id,
        )

    # TODO: inform about moving the previous upvote
    await discord_interaction_sdk_adapter.followup_ephemeral("Upvoted!")
