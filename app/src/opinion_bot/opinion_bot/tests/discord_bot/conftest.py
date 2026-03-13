from unittest.mock import AsyncMock, patch

import pytest
from django.conf import settings

from opinion_bot.opinion_bot.discord_bot.discord_interaction_sdk_adapter import DiscordInteractionSdkAdapter


@pytest.fixture(autouse=True)
def opinions_url_settings_fixture():
    with patch.object(settings, "OPINIONS_URL", "http://test-opinions.com"):
        yield


@pytest.fixture
def mock_sdk_adapter_factory():
    def make_mock_sdk_adapter(
        *,
        new_opinion_message_id=1,
        confirmation_result=False,
    ) -> DiscordInteractionSdkAdapter:
        mock_sdk_adapter = AsyncMock(spec=DiscordInteractionSdkAdapter)
        mock_sdk_adapter.publish_opinion.return_value = new_opinion_message_id
        mock_sdk_adapter.show_confirmation_dialog.return_value = confirmation_result
        return mock_sdk_adapter

    return make_mock_sdk_adapter
