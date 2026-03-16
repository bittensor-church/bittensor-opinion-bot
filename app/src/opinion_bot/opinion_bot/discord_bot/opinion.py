import logging

import emoji
from django.conf import settings

from opinion_bot.opinion_bot.models import (
    Opinion,
)

from .discord_interaction_sdk_api import DiscordInteractionSdkAPI
from .domain import DiscordEventOutcome, OpinionCommandEvent, OpinionMessage
from .persistence import (
    any_key_role,
    get_channel_by_netuid,
    get_user_valid_opinions_for_channel,
    mark_opinion_valid,
    save_opinion,
)
from .utils import create_masked_opinion_url, create_user_mention

logger = logging.getLogger(__name__)


async def handle_opinion_command_event(
    *,
    event: OpinionCommandEvent,
    discord_interaction_sdk_adapter: DiscordInteractionSdkAPI,
) -> DiscordEventOutcome:

    await discord_interaction_sdk_adapter.defer_ephemeral()

    # TODO [dtao] will it stand?
    if event.channel_id != settings.DISCORD_CHANNEL_ID:
        await discord_interaction_sdk_adapter.respond_ephemeral("Posting opinions is not allowed in this channel.")
        return "rejected"

    # TODO [dtao] change into subnet instance
    discord_channel = await get_channel_by_netuid(netuid=event.netuid)
    if discord_channel is None:
        await discord_interaction_sdk_adapter.respond_ephemeral("Unknown subnet.")
        return "rejected"

    if not emoji.is_emoji(event.emoji):
        await discord_interaction_sdk_adapter.respond_ephemeral(f"Invalid emoji: {event.emoji}")
        return "rejected"

    if not event.message:
        await discord_interaction_sdk_adapter.respond_ephemeral("Opinion message can't be empty.")
        return "rejected"

    previous_opinions = await get_user_valid_opinions_for_channel(
        user_id=event.user.user_id, channel_id=discord_channel.id
    )
    if previous_opinions:
        confirmed = await _confirm_replacing_opinion(
            adapter=discord_interaction_sdk_adapter, opinion=previous_opinions[0]
        )
        if confirmed:
            await discord_interaction_sdk_adapter.respond_ephemeral("Posting opinion...")
    else:
        confirmed = True

    if not confirmed:
        await discord_interaction_sdk_adapter.delete_response()
        return "user_cancelled"

    is_featured = await any_key_role(event.user.roles_ids)

    opinion = await save_opinion(
        event=event,
        channel_id=discord_channel.id,
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
            "but it will not be displayed publicly to prevent flooding the channel with too many opinions.\n"
            "Thank you for your understanding."
        )
    return "success"


async def _confirm_replacing_opinion(*, adapter: DiscordInteractionSdkAPI, opinion: Opinion) -> bool:
    # show only the prefix of a previous message if too long not to hit the following discord limitation:
    # 400 Bad Request (error code: 50035): Invalid Form Body, In content: Must be 2000 or fewer in length.
    previous_message = opinion.content if len(opinion.content) < 500 else opinion.content[:500] + "..."
    content = f"You have already posted the opinion on this subnet.\n\n{opinion.emoji} {previous_message}\n\nDo you want to replace it?"
    return await adapter.show_confirmation_dialog(content=content)


async def _publish_opinion(
    *, event: OpinionCommandEvent, opinion_id: int, discord_interaction_sdk_adapter: DiscordInteractionSdkAPI
) -> int:
    user_mention = create_user_mention(event.user.user_id)
    opinion_url = create_masked_opinion_url(opinion_id)
    message_header = f"{user_mention} posted opinion {opinion_url} about subnet {event.netuid}"
    message_content = f"{event.emoji} {event.message}"

    opinion_message = OpinionMessage(header=message_header, content=message_content)
    message_id = await discord_interaction_sdk_adapter.publish_opinion(opinion_message=opinion_message)
    return message_id
