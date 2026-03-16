from channels.db import database_sync_to_async
from django.db import transaction

from opinion_bot.opinion_bot.discord_bot.domain import InteractionUser, OpinionCommandEvent, OpinionUpvoteEvent
from opinion_bot.opinion_bot.models import DiscordChannel, DiscordRole, DiscordUser, Opinion, Upvote, UserRole


@database_sync_to_async
def get_channel_by_netuid(netuid: int) -> DiscordChannel | None:
    return DiscordChannel.objects.filter(netuid=netuid).first()


@database_sync_to_async
def any_key_role(role_ids: list[int]) -> bool:
    return bool(role_ids) and DiscordRole.objects.filter(id__in=role_ids, is_key_role=True).exists()


# TODO [dtao] change into ..._for_subnet_instance
@database_sync_to_async
def get_user_valid_opinions_for_channel(*, user_id: int, channel_id: int) -> list[Opinion]:
    return list(
        Opinion.objects.filter(channel_id=channel_id, author_id=user_id, status=Opinion.Status.VALID).order_by(
            "-created_at"
        )
    )


# TODO [dtao] change into ..._for_subnet_instance
@database_sync_to_async
def get_user_valid_upvotes_for_channel(*, user_id: int, channel_id: int) -> list[Upvote]:
    return list(
        Upvote.objects.filter(channel_id=channel_id, author_id=user_id, status=Upvote.Status.VALID).order_by(
            "-created_at"
        )
    )


@database_sync_to_async
def save_opinion(
    *,
    event: OpinionCommandEvent,
    channel_id: int,  # TODO [dtao] change into subnet instance id
    is_featured: bool,
    previous_opinion_ids: list[int],
) -> Opinion:
    user = _create_or_update_user(event.user)

    with transaction.atomic():
        Opinion.objects.filter(id__in=previous_opinion_ids).update(status=Opinion.Status.REPLACED)

        opinion = Opinion.objects.create(
            channel_id=channel_id,
            author=user,
            emoji=event.emoji,
            content=event.message,
            status=Opinion.Status.PENDING if is_featured else Opinion.Status.VALID,
            visibility=Opinion.Visibility.FEATURED if is_featured else Opinion.Visibility.HIDDEN,
        )

        return opinion


@database_sync_to_async
def mark_opinion_valid(*, opinion: Opinion, message_id: int) -> None:
    opinion.status = Opinion.Status.VALID
    opinion.message_id = message_id
    opinion.save(update_fields=["status", "message_id"])


@database_sync_to_async
def get_opinion_by_id(opinion_id: int) -> Opinion | None:
    return Opinion.objects.filter(id=opinion_id).first()


@database_sync_to_async
def get_opinion_by_message_id(message_id: int) -> Opinion | None:
    return Opinion.objects.filter(message_id=message_id).first()


@database_sync_to_async
def save_upvote(
    *,
    event: OpinionUpvoteEvent,
    opinion: Opinion,
    is_featured: bool,
    previous_upvotes_ids: list[int],
) -> None:
    user = _create_or_update_user(event.user)

    with transaction.atomic():
        Upvote.objects.filter(id__in=previous_upvotes_ids).update(status=Upvote.Status.REPLACED)

        Upvote.objects.create(
            channel_id=opinion.channel_id,
            author=user,
            opinion=opinion,
            visibility=Upvote.Visibility.FEATURED if is_featured else Upvote.Visibility.HIDDEN,
            status=Upvote.Status.VALID,
        )


@transaction.atomic
def _create_or_update_user(interaction_user: InteractionUser) -> DiscordUser:
    user, _created = DiscordUser.objects.update_or_create(
        id=interaction_user.user_id,
        defaults={
            "username": interaction_user.username,
            "display_name": interaction_user.display_name,
        },
    )

    # Only keep roles that exist in DiscordRole table.
    existing_role_ids = set(DiscordRole.objects.filter(id__in=interaction_user.roles_ids).values_list("id", flat=True))

    # Remove roles no longer present.
    UserRole.objects.filter(user=user).exclude(role_id__in=existing_role_ids).delete()

    # Add missing roles.
    already_assigned_ids = set(
        UserRole.objects.filter(user=user, role_id__in=existing_role_ids).values_list("role_id", flat=True)
    )
    to_create = [UserRole(user=user, role_id=role_id) for role_id in (existing_role_ids - already_assigned_ids)]
    UserRole.objects.bulk_create(to_create, ignore_conflicts=True)

    return user
