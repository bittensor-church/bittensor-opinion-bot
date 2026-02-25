import logging

import emoji

from opinion_bot.opinion_bot.models import (
    Opinion,
)

from .discord_interaction_sdk_api import DiscordInteractionSdkAPI
from .domain import OpinionCommandEvent, OpinionMessage
from .persistence import (
    any_key_role,
    get_channel,
    get_user_valid_opinions_for_channel,
    mark_opinion_valid,
    save_opinion,
)
from .utils import create_opinion_slug, create_user_mention

logger = logging.getLogger(__name__)


async def handle_opinion_command_event(
    *,
    event: OpinionCommandEvent,
    discord_interaction_sdk_adapter: DiscordInteractionSdkAPI,
) -> None:

    discord_channel = await get_channel(channel_id=event.channel_id)
    if discord_channel is None:
        await discord_interaction_sdk_adapter.respond_ephemeral("Posting opinions is not allowed in this channel.")
        return

    if discord_channel.is_archived:
        await discord_interaction_sdk_adapter.respond_ephemeral(
            "This channel is archived. Posting opinions is not allowed."
        )
        return

    if not emoji.is_emoji(event.emoji):
        await discord_interaction_sdk_adapter.respond_ephemeral(f"Invalid emoji: {event.emoji}")
        return

    if not event.message:
        await discord_interaction_sdk_adapter.respond_ephemeral("Opinion message can't be empty.")
        return

    await discord_interaction_sdk_adapter.defer_ephemeral()

    previous_opinions = await get_user_valid_opinions_for_channel(
        user_id=event.user.user_id, channel_id=event.channel_id
    )
    if previous_opinions:
        confirmed = await _confirm_replacing_opinion(
            adapter=discord_interaction_sdk_adapter, opinion=previous_opinions[0]
        )
        logger.debug("Replacing opinion confirmed=%s for %s", confirmed, event)
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
            event=event, opinion_id=opinion.id, discord_interaction_sdk_adapter=discord_interaction_sdk_adapter
        )
        logger.debug("Opinion message posted %s", event)
        await mark_opinion_valid(opinion=opinion, message_id=message_id)
        await discord_interaction_sdk_adapter.delete_response()
    else:
        await discord_interaction_sdk_adapter.respond_ephemeral(
            "Thank you for your message - it will be available in the API and various clients can display it, "
            "but it will not be displayed publicly to prevent flooding the subnet channels with too many opinions.\n"
            "Thank you for your understanding."
        )


async def _confirm_replacing_opinion(*, adapter: DiscordInteractionSdkAPI, opinion: Opinion) -> bool:
    content = f"You have already posted the opinion in this channel.\n\n{opinion.emoji} {opinion.content}\n\nDo you want to replace it?"
    return await adapter.show_confirmation_dialog(content=content)


async def _publish_opinion(
    *, event: OpinionCommandEvent, opinion_id: int, discord_interaction_sdk_adapter: DiscordInteractionSdkAPI
) -> int:
    user_mention = create_user_mention(event.user.user_id)
    # TODO: consider keeping slug in DB
    opinion_ref = f"#{create_opinion_slug(opinion_id)}"
    message_header = f"{user_mention} posted opinion {opinion_ref}"
    message_content = f"{event.emoji} {event.message}"

    opinion_message = OpinionMessage(header=message_header, content=message_content)
    message_id = await discord_interaction_sdk_adapter.publish_opinion(opinion_message=opinion_message)
    return message_id
