import emoji
import structlog

from opinion_bot.opinion_bot.models import (
    Opinion,
)

from .discord_interaction_sdk_api import DiscordInteractionSdkAPI
from .domain import OpinionCommandEvent, OpinionMessage
from .persistence import get_channel, any_key_role, get_user_valid_opinions_for_channel, save_opinion, mark_opinion_valid
from .utils import create_user_mention, create_opinion_slug

logger = structlog.get_logger(__name__)

async def handle_opinion_command_event(
        *,
        event: OpinionCommandEvent,
        discord_interaction_sdk_adapter: DiscordInteractionSdkAPI,
) -> None:

    if not emoji.is_emoji(event.emoji):
        await discord_interaction_sdk_adapter.respond_ephemeral(f"Invalid emoji: {event.emoji}")
        return

    await discord_interaction_sdk_adapter.defer_ephemeral()

    discord_channel = await get_channel(channel_id=event.channel_id)
    if discord_channel is None:
        # FIXME: confirm text, move to const
        await discord_interaction_sdk_adapter.respond_ephemeral("Posting opinions is not allowed in this channel.")
        return

    if discord_channel.is_archived:
        # FIXME: confirm text, move to const
        await discord_interaction_sdk_adapter.respond_ephemeral("This channel is archived. Posting opinions is not allowed.")
        return

    # FIXME: validate emoji, stop with error message if invalid

    previous_opinions = await get_user_valid_opinions_for_channel(user_id=event.user.user_id, channel_id=event.channel_id)
    if previous_opinions:
        confirmed = await _confirm_replacing_opinion(adapter=discord_interaction_sdk_adapter, opinion=previous_opinions[0])
        if confirmed:
            await discord_interaction_sdk_adapter.respond_ephemeral("Posting opinion...")
    else:
        confirmed = True

    if not confirmed:
        await discord_interaction_sdk_adapter.delete_response()
        return

    is_featured = await any_key_role(event.user.roles_ids)

    opinion = await save_opinion(
        event=event,
        is_featured=is_featured,
        previous_opinion_ids=[opinion.id for opinion in previous_opinions],
    )

    if is_featured:
        message_id = await _publish_opinion(
            event=event,
            opinion_id=opinion.id,
            discord_interaction_sdk_adapter=discord_interaction_sdk_adapter
        )
        await mark_opinion_valid(opinion=opinion, message_id=message_id)
        await discord_interaction_sdk_adapter.delete_response()
    else:
        # FIXME: cannot follow after deleting response as it results with "Message could not be loaded"
        # FIXME: move text to const
        await discord_interaction_sdk_adapter.respond_ephemeral(
            "Thank you for your message - it will be available in the API and various clients can display it, "
            "but it will not be displayed publicly to prevent flooding the subnet channels with too many opinions.\n"
            "Thank you for your understanding."
        )

    # FIXME: exception handling, show error message instead of deleting response


async def _confirm_replacing_opinion(*, adapter: DiscordInteractionSdkAPI, opinion: Opinion) -> bool:
    # TODO: confirm text, move to const
    content = f"You have already posted the opinion in this channel.\n\n{opinion.emoji} {opinion.content}\n\nDo you want to replace it?"
    return await adapter.show_confirmation_dialog(content=content)


async def _publish_opinion(
        *,
        event: OpinionCommandEvent,
        opinion_id: int,
        discord_interaction_sdk_adapter: DiscordInteractionSdkAPI
) -> int:
    user_mention = create_user_mention(event.user.user_id)
    # TODO: keep slug in DB
    opinion_ref = f"#{create_opinion_slug(opinion_id)}"
    message_header = f"{user_mention} posted opinion {opinion_ref}" # TODO: move text to const
    message_content = f"{event.emoji} {event.message}"

    opinion_message = OpinionMessage(header=message_header, content=message_content)
    try:
        message_id = await discord_interaction_sdk_adapter.publish_opinion(opinion_message=opinion_message)
        logger.info(
            "discord_bot.opinion_posted",
            opinion=opinion_message,
        )
    except Exception:
        logger.exception(
            "discord_bot.opinion_post_failed",
            opinion=opinion_message,
        )
        raise
    return message_id


