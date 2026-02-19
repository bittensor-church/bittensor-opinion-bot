import httpx
import structlog

from .discord_bot_settings import DiscordBotSettings
from .discord_bot_const import DISCORD_API_BASE_URL
from .discord_interaction_rest_api import DiscordInteractionRestAsyncAPI

logger = structlog.get_logger(__name__)


class DiscordInteractionRestAsyncClient:
    def __init__(self, discord_bot_settings: DiscordBotSettings ,client: httpx.AsyncClient):
        self._discord_bot_settings = discord_bot_settings
        self._client = client

    async def delete_original_response(self, *, interaction_token: str) -> None:
        url = f"{DISCORD_API_BASE_URL}/webhooks/{self._discord_bot_settings.application_id}/{interaction_token}/messages/@original"
        resp = await self._client.delete(url)

        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            logger.exception(
                "discord_interaction.delete_previous_response_failed",
                status_code=resp.status_code,
                response_text=resp.text,
            )
            raise

def create_discord_interaction_rest_async_client(
        *,
        discord_bot_settings: DiscordBotSettings,
        client: httpx.AsyncClient,
) -> DiscordInteractionRestAsyncAPI:
    return DiscordInteractionRestAsyncClient(discord_bot_settings, client) # FIXME: do we cast in such case?
