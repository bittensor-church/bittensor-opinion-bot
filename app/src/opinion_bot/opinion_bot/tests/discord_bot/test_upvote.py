import asyncio
from dataclasses import dataclass
from unittest.mock import call

import pytest

from opinion_bot.opinion_bot.discord_bot.domain import InteractionUser, OpinionUpvoteEvent
from opinion_bot.opinion_bot.discord_bot.upvote import handle_opinion_upvote_event
from opinion_bot.opinion_bot.models import DiscordChannel, DiscordRole, DiscordUser, Opinion, Upvote, UserRole

_CHANNEL_ID = 100
_OTHER_CHANNEL_ID = 101

_USER_ID = 10
_USER_NAME = "testuser"
_USER_DISPLAY_NAME = "Test User"

_OTHER_USER_ID = 11

_KEY_ROLE_IDS = (50, 60)
_NON_KEY_ROLE_IDS = (70, 80)

_EMOJI = "👍"


@dataclass()
class DbSetup:
    other_user_opinion_id: int | None = None
    previous_upvote_id: int | None = None


@pytest.fixture()
def db_setup_factory(transactional_db):
    def make_db_setup(
        *,
        create_channel=False,
        is_channel_archived=False,
        create_user=False,
        user_roles_ids=(),
        create_other_user_opinion=False,
        other_user_opinion_message_id=None,
        create_user_upvote=False,
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
            id=_OTHER_USER_ID,
            username="otheruser",
            display_name="Other User",
        )

        DiscordChannel.objects.create(id=_OTHER_CHANNEL_ID, netuid=2, is_archived=False)

        if create_user:
            user = DiscordUser.objects.create(
                id=_USER_ID,
                username=_USER_NAME,
                display_name=_USER_DISPLAY_NAME,
            )
            for role_id in user_roles_ids:
                UserRole.objects.create(user=user, role_id=role_id)

        if create_channel:
            DiscordChannel.objects.create(id=_CHANNEL_ID, netuid=1, is_archived=is_channel_archived)

            if create_other_user_opinion:
                opinion = Opinion.objects.create(
                    channel_id=_CHANNEL_ID,
                    author_id=other_user.id,
                    emoji=_EMOJI,
                    content="other user's opinion",
                    status=Opinion.Status.VALID,
                    message_id=other_user_opinion_message_id,
                )
                db_setup.other_user_opinion_id = opinion.id

                if create_user_upvote:
                    db_setup.previous_upvote_id = Upvote.objects.create(
                        channel_id=_CHANNEL_ID,
                        author_id=_USER_ID,
                        opinion_id=opinion.id,
                        status=Upvote.Status.VALID,
                    ).id

        return db_setup

    return make_db_setup


def _get_upvote_count_in_channel():
    return Upvote.objects.filter(channel_id=_CHANNEL_ID).count()


def _get_last_upvote_by_channel_and_author(channel_id, author_id):
    return Upvote.objects.filter(channel_id=channel_id, author_id=author_id).order_by("-id").first()


def _get_upvote_status_by_id(upvote_id):
    return Upvote.objects.get(id=upvote_id).status


@pytest.fixture
def upvote_event_factory():
    def make_event(
        *,
        user_roles_ids=(),
        username=_USER_NAME,
        display_name=_USER_DISPLAY_NAME,
        opinion_id=None,
        message_id=None,
    ):
        user = InteractionUser(
            user_id=_USER_ID,
            username=username,
            display_name=display_name,
            roles_ids=user_roles_ids,
        )
        return OpinionUpvoteEvent(
            channel_id=_CHANNEL_ID,
            user=user,
            opinion_id=opinion_id,
            message_id=message_id,
        )

    return make_event


def test_defers_response_first(db_setup_factory, mock_sdk_adapter_factory, upvote_event_factory):
    # arrange
    db_setup_factory()
    mock_sdk_adapter = mock_sdk_adapter_factory()
    event = upvote_event_factory(opinion_id=1)

    # act
    asyncio.run(handle_opinion_upvote_event(event=event, discord_interaction_sdk_adapter=mock_sdk_adapter))

    # assert
    assert mock_sdk_adapter.mock_calls[0] == call.defer_ephemeral()
    mock_sdk_adapter.defer_ephemeral.assert_called_once()
    assert len(mock_sdk_adapter.mock_calls) > 1


def test_saves_hidden_upvote_by_opinion_id(db_setup_factory, mock_sdk_adapter_factory, upvote_event_factory):
    # arrange
    db_setup = db_setup_factory(create_channel=True, create_other_user_opinion=True, create_user=True)
    opinion_in_other_channel = Opinion.objects.create(
        channel_id=_OTHER_CHANNEL_ID,
        author_id=_OTHER_USER_ID,
        emoji=_EMOJI,
        content="other user's opinion in other channel",
        status=Opinion.Status.VALID,
    )
    Upvote.objects.create(
        channel_id=_OTHER_CHANNEL_ID,
        author_id=_USER_ID,
        opinion_id=opinion_in_other_channel.id,
        status=Upvote.Status.VALID,
    )
    mock_sdk_adapter = mock_sdk_adapter_factory()
    event = upvote_event_factory(opinion_id=db_setup.other_user_opinion_id)

    # act
    result = asyncio.run(handle_opinion_upvote_event(event=event, discord_interaction_sdk_adapter=mock_sdk_adapter))

    # assert
    assert result == "success"
    upvote = _get_last_upvote_by_channel_and_author(_CHANNEL_ID, _USER_ID)
    assert upvote.opinion_id == db_setup.other_user_opinion_id
    assert upvote.status == Upvote.Status.VALID
    assert upvote.visibility == Upvote.Visibility.HIDDEN

    mock_sdk_adapter.followup_ephemeral.assert_called_once_with(
        f"Opinion [#{db_setup.other_user_opinion_id:05d}](<http://test-opinions.com/?id={db_setup.other_user_opinion_id}>) upvoted"
    )


def test_saves_featured_upvote_by_opinion_id(db_setup_factory, mock_sdk_adapter_factory, upvote_event_factory):
    # arrange
    db_setup = db_setup_factory(
        create_channel=True,
        create_other_user_opinion=True,
    )
    mock_sdk_adapter = mock_sdk_adapter_factory()
    event = upvote_event_factory(
        opinion_id=db_setup.other_user_opinion_id, user_roles_ids=(_KEY_ROLE_IDS[0], _NON_KEY_ROLE_IDS[0])
    )

    # act
    result = asyncio.run(handle_opinion_upvote_event(event=event, discord_interaction_sdk_adapter=mock_sdk_adapter))

    # assert
    assert result == "success"
    upvote = _get_last_upvote_by_channel_and_author(_CHANNEL_ID, _USER_ID)
    assert upvote.opinion_id == db_setup.other_user_opinion_id
    assert upvote.status == Upvote.Status.VALID
    assert upvote.visibility == Upvote.Visibility.FEATURED

    mock_sdk_adapter.followup_ephemeral.assert_called_once_with(
        f"Opinion [#{db_setup.other_user_opinion_id:05d}](<http://test-opinions.com/?id={db_setup.other_user_opinion_id}>) upvoted"
    )


def test_saves_upvote_by_message_id(db_setup_factory, mock_sdk_adapter_factory, upvote_event_factory):
    # arrange
    db_setup = db_setup_factory(create_channel=True, create_other_user_opinion=True, other_user_opinion_message_id=999)
    mock_sdk_adapter = mock_sdk_adapter_factory()
    event = upvote_event_factory(message_id=999)

    # act
    result = asyncio.run(handle_opinion_upvote_event(event=event, discord_interaction_sdk_adapter=mock_sdk_adapter))

    # assert
    assert result == "success"
    upvote = _get_last_upvote_by_channel_and_author(_CHANNEL_ID, _USER_ID)
    assert upvote.opinion_id == db_setup.other_user_opinion_id

    mock_sdk_adapter.followup_ephemeral.assert_called_once_with(
        f"Opinion [#{db_setup.other_user_opinion_id:05d}](<http://test-opinions.com/?id={db_setup.other_user_opinion_id}>) upvoted"
    )


def test_replaces_previous_upvote(db_setup_factory, mock_sdk_adapter_factory, upvote_event_factory):
    # arrange
    db_setup = db_setup_factory(
        create_channel=True,
        create_other_user_opinion=True,
        create_user=True,
        create_user_upvote=True,
    )
    other_user_opinion_in_other_channel = Opinion.objects.create(
        channel_id=_OTHER_CHANNEL_ID,
        author_id=_OTHER_USER_ID,
        emoji=_EMOJI,
        content="other user's opinion in other channel",
        status=Opinion.Status.VALID,
    )
    user_upvote_in_other_channel = Upvote.objects.create(
        channel_id=_OTHER_CHANNEL_ID,
        author_id=_USER_ID,
        opinion_id=other_user_opinion_in_other_channel.id,
        status=Upvote.Status.VALID,
    )
    another_user = DiscordUser.objects.create(
        id=_OTHER_USER_ID + 1,
        username="another_user",
        display_name="Another User",
    )
    another_user_opinion = Opinion.objects.create(
        channel_id=_CHANNEL_ID,
        author_id=another_user.id,
        emoji=_EMOJI,
        content="another user's opinion in the same channel",
        status=Opinion.Status.VALID,
    )
    another_user_upvote = Upvote.objects.create(
        channel_id=_CHANNEL_ID,
        author_id=another_user.id,
        opinion_id=db_setup.other_user_opinion_id,
        status=Upvote.Status.VALID,
    )

    mock_sdk_adapter = mock_sdk_adapter_factory()
    event = upvote_event_factory(opinion_id=another_user_opinion.id)

    # act
    result = asyncio.run(handle_opinion_upvote_event(event=event, discord_interaction_sdk_adapter=mock_sdk_adapter))

    # assert
    assert result == "success"
    assert _get_upvote_status_by_id(db_setup.previous_upvote_id) == Upvote.Status.REPLACED
    assert _get_upvote_status_by_id(user_upvote_in_other_channel.id) == Upvote.Status.VALID
    assert _get_upvote_status_by_id(another_user_upvote.id) == Upvote.Status.VALID

    mock_sdk_adapter.followup_ephemeral.assert_called_once_with(
        f"Upvote moved from [#{db_setup.other_user_opinion_id:05d}](<http://test-opinions.com/?id={db_setup.other_user_opinion_id}>)"
        f" to [#{another_user_opinion.id:05d}](<http://test-opinions.com/?id={another_user_opinion.id}>)"
    )


def test_creates_user_with_known_roles_when_not_exists(
    db_setup_factory, mock_sdk_adapter_factory, upvote_event_factory
):
    # arrange
    db_setup = db_setup_factory(create_channel=True, create_other_user_opinion=True)
    mock_sdk_adapter = mock_sdk_adapter_factory()
    event = upvote_event_factory(
        opinion_id=db_setup.other_user_opinion_id,
        user_roles_ids=(_KEY_ROLE_IDS[0], _NON_KEY_ROLE_IDS[0], 999),
    )

    # act
    asyncio.run(handle_opinion_upvote_event(event=event, discord_interaction_sdk_adapter=mock_sdk_adapter))

    # assert
    user = DiscordUser.objects.get(id=_USER_ID)
    assert user.username == _USER_NAME
    assert user.display_name == _USER_DISPLAY_NAME
    assert {role.role_id for role in user.user_roles.all()} == {_KEY_ROLE_IDS[0], _NON_KEY_ROLE_IDS[0]}


def test_update_user_when_exists(db_setup_factory, mock_sdk_adapter_factory, upvote_event_factory):
    # arrange
    db_setup = db_setup_factory(create_channel=True, create_other_user_opinion=True, create_user=True)
    mock_sdk_adapter = mock_sdk_adapter_factory()
    event = upvote_event_factory(
        opinion_id=db_setup.other_user_opinion_id,
        username="updated_user",
        display_name="Updated Name",
    )

    # act
    asyncio.run(handle_opinion_upvote_event(event=event, discord_interaction_sdk_adapter=mock_sdk_adapter))

    # assert
    user = DiscordUser.objects.get(id=_USER_ID)
    assert user.username == "updated_user"
    assert user.display_name == "Updated Name"


def test_updates_user_roles(db_setup_factory, mock_sdk_adapter_factory, upvote_event_factory):
    # arrange
    db_setup = db_setup_factory(
        create_channel=True,
        create_other_user_opinion=True,
        create_user=True,
        user_roles_ids=(_KEY_ROLE_IDS[0], _NON_KEY_ROLE_IDS[0], _NON_KEY_ROLE_IDS[1]),
    )
    mock_sdk_adapter = mock_sdk_adapter_factory()
    event = upvote_event_factory(
        opinion_id=db_setup.other_user_opinion_id,
        user_roles_ids=(_KEY_ROLE_IDS[1], _NON_KEY_ROLE_IDS[0]),
    )

    # act
    asyncio.run(handle_opinion_upvote_event(event=event, discord_interaction_sdk_adapter=mock_sdk_adapter))

    # assert
    user = DiscordUser.objects.get(id=_USER_ID)
    assert {role.role_id for role in user.user_roles.all()} == {_KEY_ROLE_IDS[1], _NON_KEY_ROLE_IDS[0]}


def test_rejects_upvote_when_channel_is_missing(db_setup_factory, mock_sdk_adapter_factory, upvote_event_factory):
    # arrange
    db_setup_factory()
    mock_sdk_adapter = mock_sdk_adapter_factory()
    event = upvote_event_factory(opinion_id=999)

    # act
    result = asyncio.run(handle_opinion_upvote_event(event=event, discord_interaction_sdk_adapter=mock_sdk_adapter))

    # assert
    assert result == "rejected"
    mock_sdk_adapter.followup_ephemeral.assert_called_once_with("Upvoting opinions is not allowed in this channel.")
    assert _get_upvote_count_in_channel() == 0


def test_rejects_upvote_when_channel_is_archived(db_setup_factory, mock_sdk_adapter_factory, upvote_event_factory):
    # arrange
    db_setup_factory(create_channel=True, is_channel_archived=True)
    mock_sdk_adapter = mock_sdk_adapter_factory()
    event = upvote_event_factory(opinion_id=999)

    # act
    result = asyncio.run(handle_opinion_upvote_event(event=event, discord_interaction_sdk_adapter=mock_sdk_adapter))

    # assert
    assert result == "rejected"
    mock_sdk_adapter.followup_ephemeral.assert_called_once_with("This channel is archived. Upvoting is not allowed.")
    assert _get_upvote_count_in_channel() == 0


def test_rejects_upvote_when_opinion_is_unknown_by_id(db_setup_factory, mock_sdk_adapter_factory, upvote_event_factory):
    # arrange
    db_setup = db_setup_factory(create_channel=True, create_other_user_opinion=True)
    mock_sdk_adapter = mock_sdk_adapter_factory()
    event = upvote_event_factory(opinion_id=db_setup.other_user_opinion_id + 1)

    # act
    result = asyncio.run(handle_opinion_upvote_event(event=event, discord_interaction_sdk_adapter=mock_sdk_adapter))

    # assert
    assert result == "rejected"
    mock_sdk_adapter.followup_ephemeral.assert_called_once_with("Unknown opinion.")
    assert _get_upvote_count_in_channel() == 0


def test_rejects_upvote_when_opinion_is_unknown_by_message_id(
    db_setup_factory, mock_sdk_adapter_factory, upvote_event_factory
):
    # arrange
    db_setup_factory(create_channel=True, create_other_user_opinion=True, other_user_opinion_message_id=999)
    mock_sdk_adapter = mock_sdk_adapter_factory()
    event = upvote_event_factory(message_id=998)

    # act
    result = asyncio.run(handle_opinion_upvote_event(event=event, discord_interaction_sdk_adapter=mock_sdk_adapter))

    # assert
    assert result == "rejected"
    mock_sdk_adapter.followup_ephemeral.assert_called_once_with("Unknown opinion.")
    assert _get_upvote_count_in_channel() == 0


def test_rejects_upvote_when_opinion_is_in_different_channel(
    db_setup_factory, mock_sdk_adapter_factory, upvote_event_factory
):
    # arrange
    db_setup_factory(create_channel=True)
    opinion = Opinion.objects.create(
        channel_id=_OTHER_CHANNEL_ID,
        author_id=_OTHER_USER_ID,
        emoji=_EMOJI,
        content="other channel opinion",
        status=Opinion.Status.VALID,
    )
    mock_sdk_adapter = mock_sdk_adapter_factory()
    event = upvote_event_factory(opinion_id=opinion.id)

    # act
    result = asyncio.run(handle_opinion_upvote_event(event=event, discord_interaction_sdk_adapter=mock_sdk_adapter))

    # assert
    assert result == "rejected"
    mock_sdk_adapter.followup_ephemeral.assert_called_once_with("Opinion is not in this channel.")
    assert _get_upvote_count_in_channel() == 0


def test_rejects_upvote_when_upvoting_own_opinion(db_setup_factory, mock_sdk_adapter_factory, upvote_event_factory):
    # arrange
    db_setup_factory(create_channel=True, create_user=True)
    opinion = Opinion.objects.create(
        channel_id=_CHANNEL_ID,
        author_id=_USER_ID,
        emoji=_EMOJI,
        content="user's own opinion",
        status=Opinion.Status.VALID,
    )
    mock_sdk_adapter = mock_sdk_adapter_factory()
    event = upvote_event_factory(opinion_id=opinion.id)

    # act
    result = asyncio.run(handle_opinion_upvote_event(event=event, discord_interaction_sdk_adapter=mock_sdk_adapter))

    # assert
    assert result == "rejected"
    mock_sdk_adapter.followup_ephemeral.assert_called_once_with("You can't upvote your own opinion.")
    assert _get_upvote_count_in_channel() == 0


def test_rejects_upvote_when_already_upvoted(db_setup_factory, mock_sdk_adapter_factory, upvote_event_factory):
    # arrange
    db_setup = db_setup_factory(
        create_channel=True, create_other_user_opinion=True, create_user=True, create_user_upvote=True
    )

    mock_sdk_adapter = mock_sdk_adapter_factory()
    event = upvote_event_factory(opinion_id=db_setup.other_user_opinion_id)

    # act
    result = asyncio.run(handle_opinion_upvote_event(event=event, discord_interaction_sdk_adapter=mock_sdk_adapter))

    # assert
    assert result == "rejected"
    mock_sdk_adapter.followup_ephemeral.assert_called_once_with("You have already upvoted this opinion.")
    assert _get_upvote_count_in_channel() == 1
