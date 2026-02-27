from opinion_bot.opinion_bot.discord_bot.discord_interaction_sdk_api import DiscordInteractionSdkAPI
from opinion_bot.opinion_bot.discord_bot.domain import OpinionUpvoteEvent
from opinion_bot.opinion_bot.discord_bot.persistence import (
    any_key_role,
    get_channel,
    get_opinion_by_message_id,
    get_user_valid_upvotes_for_channel,
    save_upvote,
)
from opinion_bot.opinion_bot.discord_bot.utils import create_masked_opinion_url


async def handle_opinion_upvote_event(
    *,
    event: OpinionUpvoteEvent,
    discord_interaction_sdk_adapter: DiscordInteractionSdkAPI,
) -> None:
    await discord_interaction_sdk_adapter.defer_ephemeral()

    discord_channel = await get_channel(channel_id=event.channel_id)
    if discord_channel is None:
        await discord_interaction_sdk_adapter.followup_ephemeral("Upvoting opinions is not allowed in this channel.")
        return

    if discord_channel.is_archived:
        await discord_interaction_sdk_adapter.followup_ephemeral("This channel is archived. Upvoting is not allowed.")
        return

    opinion = await get_opinion_by_message_id(event.message_id)
    if opinion is None:
        await discord_interaction_sdk_adapter.followup_ephemeral("Unknown opinion.")
        return

    if opinion.author_id == event.user.user_id:
        await discord_interaction_sdk_adapter.followup_ephemeral("You can't upvote your own opinion.")
        return

    previous_upvotes = await get_user_valid_upvotes_for_channel(user_id=event.user.user_id, channel_id=event.channel_id)

    if opinion.id in [upvote.opinion_id for upvote in previous_upvotes]:
        await discord_interaction_sdk_adapter.followup_ephemeral("You have already upvoted this opinion.")
        return

    is_featured = await any_key_role(event.user.roles_ids)

    await save_upvote(
        event=event,
        opinion=opinion,
        is_featured=is_featured,
        previous_upvotes_ids=[upvote.id for upvote in previous_upvotes],
    )

    opinion_url = create_masked_opinion_url(opinion.id)
    if previous_upvotes:
        previous_opinion_url = create_masked_opinion_url(previous_upvotes[0].opinion_id)
        confirmation_message = f"Upvote moved from {previous_opinion_url} to {opinion_url}"
    else:
        confirmation_message = f"Opinion {opinion_url} upvoted"

    await discord_interaction_sdk_adapter.followup_ephemeral(confirmation_message)
