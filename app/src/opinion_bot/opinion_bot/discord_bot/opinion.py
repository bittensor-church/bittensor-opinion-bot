import asyncio

from asgiref.sync import sync_to_async
import structlog

from .discord_interaction_sdk_api import DiscordInteractionSdkAPI
from .domain import OpinionCommandEvent, OpinionMessage
from ...core.utils import is_user_important

logger = structlog.get_logger(__name__)

async def handle_opinion_command_event(
        *,
        event: OpinionCommandEvent,
        discord_interaction_sdk_adapter: DiscordInteractionSdkAPI,
) -> None:
    # FIXME: validate emoji, stop with error message if invalid
    await discord_interaction_sdk_adapter.defer_ephemeral()

    await asyncio.sleep(1) # FIXME: temporary delay

    # TODO: find previous opinion, present its date, move to helper function
    if event.message and "dialog" in event.message:
        content = "**You have already posted the opinion**\n\n:heart: Some opinion text\n\nDo you want to replace it?"
        confirmed = await discord_interaction_sdk_adapter.show_confirmation_dialog(content=content)
        if confirmed:
            await discord_interaction_sdk_adapter.respond_ephemeral("Posting opinion...")
    else:
        confirmed = True

    if not confirmed:
        await discord_interaction_sdk_adapter.delete_response()
        return

    # FIXME: handle unimportant user variant
    await asyncio.sleep(1) # FIXME: temporary delay for emulating DB work

    important_user = await sync_to_async(is_user_important)(discord_interaction_sdk_adapter.user_role_ids)
    if important_user:
        await publish_opinion(event=event, discord_interaction_sdk_adapter=discord_interaction_sdk_adapter)
        await discord_interaction_sdk_adapter.delete_response()
    else:
        await discord_interaction_sdk_adapter.respond_ephemeral("You don't have permission to post opinion.") # FIXME: confirm text, move to const

    # FIXME: exception handling, show error message instead of deleting response

async def publish_opinion(*, event: OpinionCommandEvent, discord_interaction_sdk_adapter: DiscordInteractionSdkAPI) -> None:
    opinion_message = OpinionMessage(
        opinion_id=73461,  # TODO: set DB opinion_id
        channel_id=discord_interaction_sdk_adapter.channel_id,
        user_id=discord_interaction_sdk_adapter.user_id,
        emoji=event.emoji,
        message=event.message,
    )
    try:
        await discord_interaction_sdk_adapter.publish_opinion(opinion_message=opinion_message)
        logger.info(
            "discord_bot.opinion_posted",
            opinion=opinion_message,
        )
    except Exception:
        logger.exception(
            "discord_bot.opinion_post_failed",
            opinion=opinion_message,
        )

