from __future__ import annotations

import httpx
import structlog

from .discord_bot_rest_api import DiscordBotRestAsyncAPI
from .discord_bot_settings import DiscordBotSettings
from .discord_bot_const import DiscordComponentType, DiscordButtonStyle, DISCORD_API_BASE_URL, UPVOTE_BUTTON_ID
from .domain import OpinionMessage, OpinionUpvoteEvent

logger = structlog.get_logger(__name__)

_FEATURE_COLOR = 0xFFA000
_POSTED_OPINION_HEADER_TEXT = "posted opinion"
_UPVOTE_LABEL = "Upvote"

class DiscordBotRestAsyncClient:
    def __init__(self, discord_bot_settings: DiscordBotSettings, client: httpx.AsyncClient) -> None:
        self._discord_bot_settings = discord_bot_settings
        self._client = client

    async def post_opinion_message(self, *, opinion_message: OpinionMessage) -> None:
        # TODO: move creating payload to mapper function
        user_mention = f"<@{opinion_message.user_id}>"
        message_text = f"{opinion_message.emoji} {opinion_message.message}" if opinion_message.message else opinion_message.emoji
        opinion_ref = f"#{format(opinion_message.opinion_id, 'x')}" # TODO: create hash ???

        payload: dict[str, object] = {
            "components": _create_upvote_button_components(opinion_message.upvote_count),
        }

        if opinion_message.featured:
            # TODO: consider adding image banner
            payload["content"] = f"{user_mention} {_POSTED_OPINION_HEADER_TEXT} {opinion_ref}"
            payload["embeds"] = [
                {
                    "title": message_text, # cannot use user_mention here
                    "color": _FEATURE_COLOR,
                    #"footer": { "text": "footer text"}
                }
            ]
        else:
            payload["content"] = f"{user_mention} {_POSTED_OPINION_HEADER_TEXT} {opinion_ref}\n{message_text}"

        logger.info("discord_bot.post_opinion_message", payload=payload)

        url = f"{DISCORD_API_BASE_URL}/channels/{opinion_message.channel_id}/messages"

        resp = await self._client.post(url, headers=self._create_headers(), json=payload)
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            logger.exception(
                "discord_bot.post_opinion_message_failed",
                status_code=resp.status_code,
                response_text=resp.text,
                channel_id=opinion_message.channel_id,
                featured=opinion_message.featured,
            )
            raise

    # TODO: return success status bool
    async def update_upvote_count(self, *, upvote_event: OpinionUpvoteEvent, upvote_count: int) -> None:
        payload: dict[str, object] = {
            "components": _create_upvote_button_components(upvote_count),
        }

        url = f"{DISCORD_API_BASE_URL}/channels/{upvote_event.channel_id}/messages/{upvote_event.message_id}"

        resp = await self._client.patch(url, headers=self._create_headers(), json=payload)
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            logger.exception(
                "discord_bot.update_upvote_count_failed",
                status_code=resp.status_code,
                response_text=resp.text,
                message_id=upvote_event.message_id,
                upvote_count=upvote_count,
            )
            raise

    def _create_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bot {self._discord_bot_settings.token}",
            "Content-Type": "application/json",
        }

def create_discord_bot_rest_async_client(
    *,
    settings: DiscordBotSettings,
    client: httpx.AsyncClient
) -> DiscordBotRestAsyncAPI:
    return DiscordBotRestAsyncClient(settings, client) # FIXME: do we cast in such case?


def _create_upvote_button_components(upvote_count: int) -> list[dict[str, object]]:
    upvote_label = (
        f"{_UPVOTE_LABEL} ({upvote_count})"
        if upvote_count > 0
        else _UPVOTE_LABEL
    )
    return [
        {
            "type": DiscordComponentType.ACTION_ROW,
            "components": [
                {
                    "type": DiscordComponentType.BUTTON,
                    "style": DiscordButtonStyle.PRIMARY,
                    "custom_id": UPVOTE_BUTTON_ID,
                    "label": upvote_label,
                }
            ],
        }
    ]
