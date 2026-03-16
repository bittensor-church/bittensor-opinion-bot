import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
from unittest.mock import call

import pytest

from opinion_bot.opinion_bot.discord_bot.domain import InteractionUser, OpinionCommandEvent, OpinionMessage
from opinion_bot.opinion_bot.discord_bot.opinion import handle_opinion_command_event
from opinion_bot.opinion_bot.models import DiscordChannel, DiscordRole, DiscordUser, Opinion, UserRole

_CHANNEL_ID = 100

_USER_ID = 10
_USER_NAME = "testuser"
_USER_DISPLAY_NAME = "Test User"

_KEY_ROLE_IDS = (50, 60)
_NON_KEY_ROLE_IDS = (70, 80)

_OPINION_MESSAGE = "This is a test opinion"
_EMOJI = "👍"

# TODO [dtao] adjust test to new model (channel --> subnet instance)


@dataclass()
class DbSetup:
    other_user_opinion_id: int | None = None
    user_opinion_in_other_channel_id: int | None = None
    previous_opinions_ids: list[int] = field(default_factory=list)

    def existing_opinions_in_channel_count(self):
        return len(self.previous_opinions_ids) + (1 if self.other_user_opinion_id is not None else 0)


@pytest.fixture()
def db_setup_factory(transactional_db):
    def make_db_setup(
        *,
        create_channel=False,
        is_channel_archived=False,
        create_user=False,
        user_roles_ids=(),
        create_previous_opinions=False,
    ):
        db_setup = DbSetup()

        for role_id in (*_KEY_ROLE_IDS, *_NON_KEY_ROLE_IDS):
            DiscordRole.objects.create(
                id=role_id,
                is_key_role=role_id in _KEY_ROLE_IDS,
                name=f"Test Role {role_id}",
                slug=f"test-role-{role_id}",
            )

        other_user = DiscordUser.objects.create(
            id=_USER_ID + 1,
            username="otheruser",
            display_name="Other User",
        )

        other_channel = DiscordChannel.objects.create(id=_CHANNEL_ID + 1, netuid=2, is_archived=False)

        if create_channel:
            DiscordChannel.objects.create(id=_CHANNEL_ID, netuid=1, is_archived=is_channel_archived)
            db_setup.other_user_opinion_id = Opinion.objects.create(
                channel_id=_CHANNEL_ID,
                author_id=other_user.id,
                emoji=_EMOJI,
                content="other user's opinion in the same channel",
                status=Opinion.Status.VALID,
            ).id

        if create_user or create_previous_opinions:
            user = DiscordUser.objects.create(
                id=_USER_ID,
                username=_USER_NAME,
                display_name=_USER_DISPLAY_NAME,
            )
            for role_id in user_roles_ids:
                UserRole.objects.create(user=user, role_id=role_id)

            db_setup.user_opinion_in_other_channel_id = Opinion.objects.create(
                channel_id=other_channel.id,
                author_id=_USER_ID,
                emoji=_EMOJI,
                content="opinion in other channel",
                status=Opinion.Status.VALID,
            ).id

            if create_previous_opinions:
                previous_opinions = [
                    Opinion.objects.create(
                        channel_id=_CHANNEL_ID,
                        author_id=_USER_ID,
                        emoji=_EMOJI,
                        content=content,
                        status=status,
                    )
                    for (content, status) in [
                        ("opinion 1", Opinion.Status.REPLACED),
                        ("opinion 2", Opinion.Status.VALID),
                        ("most recent VALID opinion", Opinion.Status.VALID),
                    ]
                ]
                # make last opinion the most recent VALID
                previous_opinions[1].created_at = previous_opinions[1].created_at - timedelta(days=1)
                previous_opinions[1].save(update_fields=["created_at"])
                db_setup.previous_opinions_ids = [opinion.id for opinion in previous_opinions]

        return db_setup

    return make_db_setup


def _get_opinion_in_channel_count():
    return Opinion.objects.filter(channel_id=_CHANNEL_ID).count()


def _get_last_opinion_by_channel_and_author(channel_id, author_id):
    return Opinion.objects.filter(channel_id=channel_id, author_id=author_id).order_by("-id").first()


def _get_opinion_statuses_by_ids(opinion_ids):
    return [Opinion.objects.get(id=opinion_id).status for opinion_id in opinion_ids]


@pytest.fixture
def opinion_event_factory():
    def make_event(
        *,
        user_roles_ids=(),
        username=_USER_NAME,
        display_name=_USER_DISPLAY_NAME,
        emoji=_EMOJI,
        message=_OPINION_MESSAGE,
    ):
        user = InteractionUser(
            user_id=_USER_ID,
            username=username,
            display_name=display_name,
            roles_ids=user_roles_ids,
        )
        return OpinionCommandEvent(
            channel_id=_CHANNEL_ID,
            netuid=1,  # TODO [dtao] use const variable
            user=user,
            emoji=emoji,
            message=message,
        )

    return make_event


def test_defers_response_first(db_setup_factory, mock_sdk_adapter_factory, opinion_event_factory):
    # arrange
    db_setup_factory()
    mock_sdk_adapter = mock_sdk_adapter_factory()
    event = opinion_event_factory()

    # act
    asyncio.run(handle_opinion_command_event(event=event, discord_interaction_sdk_adapter=mock_sdk_adapter))

    # assert
    assert mock_sdk_adapter.mock_calls[0] == call.defer_ephemeral()
    mock_sdk_adapter.defer_ephemeral.assert_called_once()
    assert len(mock_sdk_adapter.mock_calls) > 1


def test_saves_and_posts_featured_opinion(db_setup_factory, mock_sdk_adapter_factory, opinion_event_factory):
    # arrange
    db_setup_factory(
        create_channel=True,
    )
    mock_sdk_adapter = mock_sdk_adapter_factory(new_opinion_message_id=333)
    event = opinion_event_factory(user_roles_ids=(_KEY_ROLE_IDS[0], _NON_KEY_ROLE_IDS[0]))

    # act
    result = asyncio.run(handle_opinion_command_event(event=event, discord_interaction_sdk_adapter=mock_sdk_adapter))

    # assert
    assert result == "success"

    mock_sdk_adapter.show_confirmation_dialog.assert_not_called()

    opinion = _get_last_opinion_by_channel_and_author(channel_id=event.channel_id, author_id=event.user.user_id)
    assert opinion.content == event.message
    assert opinion.emoji == event.emoji
    assert opinion.visibility == Opinion.Visibility.FEATURED
    assert opinion.status == Opinion.Status.VALID
    assert opinion.message_id == 333

    mock_sdk_adapter.publish_opinion.assert_called_once_with(
        opinion_message=OpinionMessage(
            header=f"<@{_USER_ID}> posted opinion [#{opinion.id:05d}](<http://test-opinions.com/?id={opinion.id}>) about subnet 1",
            content="👍 This is a test opinion",
        )
    )


def test_saves_hidden_opinion(db_setup_factory, mock_sdk_adapter_factory, opinion_event_factory):
    # arrange
    db_setup_factory(create_channel=True)

    mock_sdk_adapter = mock_sdk_adapter_factory()
    event = opinion_event_factory()

    # act
    result = asyncio.run(handle_opinion_command_event(event=event, discord_interaction_sdk_adapter=mock_sdk_adapter))

    # assert
    assert result == "success"

    opinion = _get_last_opinion_by_channel_and_author(channel_id=event.channel_id, author_id=event.user.user_id)
    assert opinion.content == event.message
    assert opinion.emoji == event.emoji
    assert opinion.visibility == Opinion.Visibility.HIDDEN
    assert opinion.status == Opinion.Status.VALID

    mock_sdk_adapter.publish_opinion.assert_not_called()

    mock_sdk_adapter.respond_ephemeral.assert_called_once_with(
        "Thank you for your message - it will be available in the API and various clients can display it, "
        "but it will not be displayed publicly to prevent flooding the channel with too many opinions.\n"
        "Thank you for your understanding."
    )


def test_does_not_replace_previous_opinion_when_user_cancels(
    db_setup_factory, mock_sdk_adapter_factory, opinion_event_factory
):
    # arrange
    db_setup = db_setup_factory(
        create_channel=True,
        create_previous_opinions=True,
    )
    mock_sdk_adapter = mock_sdk_adapter_factory()
    event = opinion_event_factory(user_roles_ids=_KEY_ROLE_IDS)

    # act
    result = asyncio.run(handle_opinion_command_event(event=event, discord_interaction_sdk_adapter=mock_sdk_adapter))

    # assert
    assert result == "user_cancelled"

    mock_sdk_adapter.show_confirmation_dialog.assert_called_once()
    assert "most recent VALID opinion" in mock_sdk_adapter.show_confirmation_dialog.call_args.kwargs["content"]

    assert _get_opinion_in_channel_count() == db_setup.existing_opinions_in_channel_count()
    statuses = _get_opinion_statuses_by_ids(
        [
            *db_setup.previous_opinions_ids,
            db_setup.other_user_opinion_id,
            db_setup.user_opinion_in_other_channel_id,
        ]
    )
    assert statuses == [Opinion.Status.REPLACED] + [Opinion.Status.VALID] * 4

    mock_sdk_adapter.publish_opinion.assert_not_called()


def test_replaces_previous_opinion_when_user_confirms(
    db_setup_factory, mock_sdk_adapter_factory, opinion_event_factory
):
    # arrange
    db_setup = db_setup_factory(
        create_channel=True,
        create_previous_opinions=True,
    )
    mock_sdk_adapter = mock_sdk_adapter_factory(confirmation_result=True)
    event = opinion_event_factory()

    # act
    result = asyncio.run(handle_opinion_command_event(event=event, discord_interaction_sdk_adapter=mock_sdk_adapter))

    # assert
    assert result == "success"

    mock_sdk_adapter.show_confirmation_dialog.assert_called_once()

    assert _get_opinion_in_channel_count() == db_setup.existing_opinions_in_channel_count() + 1
    statuses = _get_opinion_statuses_by_ids(
        [
            *db_setup.previous_opinions_ids,
            db_setup.other_user_opinion_id,
            db_setup.user_opinion_in_other_channel_id,
        ]
    )
    assert statuses == [Opinion.Status.REPLACED] * 3 + [Opinion.Status.VALID] * 2


def test_creates_user_with_known_roles_when_not_exists(
    db_setup_factory, mock_sdk_adapter_factory, opinion_event_factory
):
    # arrange
    db_setup_factory(
        create_channel=True,
    )
    mock_sdk_adapter = mock_sdk_adapter_factory()
    event = opinion_event_factory(user_roles_ids=(_KEY_ROLE_IDS[0], _NON_KEY_ROLE_IDS[0], 888, 999))

    # act
    result = asyncio.run(handle_opinion_command_event(event=event, discord_interaction_sdk_adapter=mock_sdk_adapter))

    # assert
    assert result == "success"

    user = DiscordUser.objects.get(id=_USER_ID)
    assert user.username == _USER_NAME
    assert user.display_name == _USER_DISPLAY_NAME
    assert {role.role_id for role in user.user_roles.all()} == {_KEY_ROLE_IDS[0], _NON_KEY_ROLE_IDS[0]}


def test_update_user_when_exists(db_setup_factory, mock_sdk_adapter_factory, opinion_event_factory):
    # arrange
    db_setup_factory(
        create_channel=True,
        create_user=True,
    )
    mock_sdk_adapter = mock_sdk_adapter_factory()
    event = opinion_event_factory(
        username="updated_username",
        display_name="Updated Display Name",
    )

    # act
    result = asyncio.run(handle_opinion_command_event(event=event, discord_interaction_sdk_adapter=mock_sdk_adapter))

    # assert
    assert result == "success"

    user = DiscordUser.objects.get(id=_USER_ID)
    assert user.username == "updated_username"
    assert user.display_name == "Updated Display Name"


def test_updates_user_roles(db_setup_factory, mock_sdk_adapter_factory, opinion_event_factory):
    # arrange
    db_setup_factory(
        create_channel=True,
        create_user=True,
        user_roles_ids=(_KEY_ROLE_IDS[0], _NON_KEY_ROLE_IDS[0], _NON_KEY_ROLE_IDS[1]),
    )
    mock_sdk_adapter = mock_sdk_adapter_factory()
    event = opinion_event_factory(user_roles_ids=(_KEY_ROLE_IDS[1], _NON_KEY_ROLE_IDS[0]))

    # act
    result = asyncio.run(handle_opinion_command_event(event=event, discord_interaction_sdk_adapter=mock_sdk_adapter))

    # assert
    assert result == "success"

    user = DiscordUser.objects.get(id=_USER_ID)
    assert {role.role_id for role in user.user_roles.all()} == {_KEY_ROLE_IDS[1], _NON_KEY_ROLE_IDS[0]}


# TODO [dtao] consider updating the test
def test_rejects_opinion_when_channel_is_missing(db_setup_factory, mock_sdk_adapter_factory, opinion_event_factory):
    # arrange
    db_setup = db_setup_factory(
        create_channel=False,
    )
    mock_sdk_adapter = mock_sdk_adapter_factory()
    event = opinion_event_factory()

    # act
    result = asyncio.run(handle_opinion_command_event(event=event, discord_interaction_sdk_adapter=mock_sdk_adapter))

    # assert
    assert result == "rejected"

    assert _get_opinion_in_channel_count() == db_setup.existing_opinions_in_channel_count()
    mock_sdk_adapter.publish_opinion.assert_not_called()
    mock_sdk_adapter.respond_ephemeral.assert_called_once_with("Unknown subnet.")


def test_rejects_opinion_when_emoji_is_invalid(db_setup_factory, mock_sdk_adapter_factory, opinion_event_factory):
    # arrange
    db_setup = db_setup_factory(
        create_channel=True,
    )
    mock_sdk_adapter = mock_sdk_adapter_factory()
    event = opinion_event_factory(emoji=":heart:")

    # act
    result = asyncio.run(handle_opinion_command_event(event=event, discord_interaction_sdk_adapter=mock_sdk_adapter))

    # assert
    assert result == "rejected"

    assert _get_opinion_in_channel_count() == db_setup.existing_opinions_in_channel_count()
    mock_sdk_adapter.publish_opinion.assert_not_called()
    mock_sdk_adapter.respond_ephemeral.assert_called_once_with("Invalid emoji: :heart:")


def test_rejects_opinion_when_message_text_is_missing(
    db_setup_factory, mock_sdk_adapter_factory, opinion_event_factory
):
    # arrange
    db_setup = db_setup_factory(
        create_channel=True,
    )
    mock_sdk_adapter = mock_sdk_adapter_factory()
    event = opinion_event_factory(message="")

    # act
    result = asyncio.run(handle_opinion_command_event(event=event, discord_interaction_sdk_adapter=mock_sdk_adapter))

    # assert
    assert result == "rejected"

    assert _get_opinion_in_channel_count() == db_setup.existing_opinions_in_channel_count()
    mock_sdk_adapter.publish_opinion.assert_not_called()
    mock_sdk_adapter.respond_ephemeral.assert_called_once_with("Opinion message can't be empty.")
