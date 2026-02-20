import structlog

from opinion_bot.opinion_bot.discord_bot.discord_interaction_sdk_api import DiscordInteractionSdkAPI
from opinion_bot.opinion_bot.discord_bot.domain import OpinionUpvoteEvent
from opinion_bot.opinion_bot.discord_bot.persistence import (get_channel, get_user_valid_upvotes_for_channel,
                                                             any_key_role, get_opinion_by_message_id, save_upvote,
                                                             get_opinion_by_id)
from opinion_bot.opinion_bot.discord_bot.utils import create_user_mention

logger = structlog.get_logger(__name__)

async def handle_opinion_upvote_event(
        *,
        event: OpinionUpvoteEvent,
        discord_interaction_sdk_adapter: DiscordInteractionSdkAPI,
) -> None:
    await discord_interaction_sdk_adapter.defer_ephemeral()

    discord_channel = await get_channel(channel_id=event.channel_id)
    if discord_channel is None:
        # FIXME: confirm text, move to const
        await discord_interaction_sdk_adapter.followup_ephemeral("Upvoting opinions is not allowed in this channel.")
        return

    if discord_channel.is_archived:
        # FIXME: confirm text, move to const
        await discord_interaction_sdk_adapter.followup_ephemeral("This channel is archived. Upvoting is not allowed.")
        return

    opinion = await get_opinion_by_message_id(event.message_id)
    if opinion is None:
        # FIXME: confirm text, move to const
        await discord_interaction_sdk_adapter.followup_ephemeral("Unknown opinion.")
        return

    if opinion.author_id == event.user.user_id:
        # FIXME: confirm text, move to const
        await discord_interaction_sdk_adapter.followup_ephemeral("You can't upvote your own opinion.")
        return

    # FIXME: confirm blocking upvote for replaced opinion

    previous_upvotes = await get_user_valid_upvotes_for_channel(user_id=event.user.user_id, channel_id=event.channel_id)

    if opinion.id in [upvote.opinion_id for upvote in previous_upvotes]:
        # FIXME: confirm text, move to const
        await discord_interaction_sdk_adapter.followup_ephemeral("You have already upvoted this opinion.")
        return

    is_featured = await any_key_role(event.user.roles_ids)

    await save_upvote(
        event=event,
        opinion=opinion,
        is_featured=is_featured,
        previous_upvotes_ids=[upvote.id for upvote in previous_upvotes]
    )

    # TODO: confirm text, move to const
    confirmation_message_parts = []
    opinion_author_mention = create_user_mention(opinion.author_id)
    if previous_upvotes:
        # FIXME: cannot use previous_upvotes[0].opinion directly due to sync/async issues
        previous_opinion = await get_opinion_by_id(previous_upvotes[0].opinion_id)
        if previous_opinion is None:
            raise Exception("Previous opinion not found")
        prev_opinion_author_mention = create_user_mention(previous_opinion.author_id)
        confirmation_message_parts.append(f"Your previous upvote for opinion by {prev_opinion_author_mention}")
        confirmation_message_parts.append(f"{previous_opinion.emoji} {previous_opinion.content}")
        confirmation_message_parts.append(f"moved to opinion by {opinion_author_mention}")
    else:
        confirmation_message_parts.append(f"Upvoted opinion by {opinion_author_mention}")

    confirmation_message_parts.append(f"{opinion.emoji} {opinion.content}")

    await discord_interaction_sdk_adapter.followup_ephemeral("\n".join(confirmation_message_parts))
