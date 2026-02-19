import asyncio

import structlog

from .discord_bot_rest_api import DiscordBotRestAsyncAPI
from .discord_interaction_rest_api import DiscordInteractionRestAsyncAPI
from .discord_interaction_sdk_api import DiscordInteractionSdkAPI
from .domain import OpinionCommandEvent, OpinionMessage

logger = structlog.get_logger(__name__)

async def handle_opinion_command_event(
        *,
        event: OpinionCommandEvent,
        discord_interaction_sdk_adapter: DiscordInteractionSdkAPI,
        discord_interaction_rest_client: DiscordInteractionRestAsyncAPI,
        discord_bot_rest_client: DiscordBotRestAsyncAPI,
) -> None:
    # TODO: decide which to use, remove the other method (we use "Posting..." after confirmation!)
    await discord_interaction_sdk_adapter.defer_ephemeral()
    # await discord_interaction_sdk_adapter.respond_ephemeral("Posting...") # TODO: confirm message text

    await asyncio.sleep(1) # FIXME: temporary delay

    # TODO: find previous opinion, present its date, move to helper function
    if event.message and "dialog" in event.message:
        content = "**You have already posted the opinion**\n\n:heart: Some opinion text\n\nDo you want to replace it?"
        confirmed = await discord_interaction_sdk_adapter.show_confirmation_message(content=content)
        if confirmed:
            await discord_interaction_sdk_adapter.respond_ephemeral("Posting opinion...")
    else:
        confirmed = True

    if confirmed:
        await asyncio.sleep(2) # FIXME: temporary delay for emulating DB work
        # TODO: move to helper function
        opinion_message = OpinionMessage(
            opinion_id=73461, # TODO: set DB opinion_id
            channel_id=discord_interaction_sdk_adapter.channel_id,
            user_id=discord_interaction_sdk_adapter.user_id,
            emoji=event.emoji,
            message=event.message,
            featured=event.message and "featured" in event.message, # FIXME: remove temporary making featured based on message
            upvote_count=3 if event.message and "upvoted" in event.message else 0, # FIXME: remove temporary mock
        )

        try:
            await discord_bot_rest_client.post_opinion_message(opinion_message=opinion_message)
            logger.info(
                "discord_bot.opinion_posted",
                opinion=opinion_message,
            )
        except Exception:
            logger.exception(
                "discord_bot.opinion_post_failed",
                opinion=opinion_message,
            )

    try:
        await discord_interaction_rest_client.delete_original_response(interaction_token=discord_interaction_sdk_adapter.interaction_token)
        logger.info("discord_interaction.response_deleted")
    except Exception:
        logger.exception("discord_interaction.response_delete_failed")


