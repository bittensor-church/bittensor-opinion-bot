# app/src/opinion_bot/opinion_bot/management/commands/generate_fake_data.py
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from opinion_bot.opinion_bot.models import DiscordChannel, DiscordRole, DiscordUser, Opinion, Upvote, UserRole

_EMOJIS = ["👍", "👎", "❤️", "🤮", "🚀", "🪙", "😭"]

# A tiny lorem ipsum word bank (no extra deps).
_LOREM_WORDS = (
    "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore et dolore magna "
    "aliqua ut enim ad minim veniam quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat "
    "duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur excepteur "
    "sint occaecat cupidatat non proident sunt in culpa qui officia deserunt mollit anim id est laborum"
).split()


def _random_dt_between(start, end, *, rng: random.Random):
    if end <= start:
        return start
    span = (end - start).total_seconds()
    return start + timedelta(seconds=rng.random() * span)


def _make_lorem_text(*, target_len: int, rng: random.Random) -> str:
    # Build a string that is >= target_len, then trim.
    # This allows repetition naturally.
    words = []
    while True:
        words.append(rng.choice(_LOREM_WORDS))
        text = " ".join(words)
        if len(text) >= target_len:
            return text[:target_len]


@dataclass(frozen=True)
class _Config:
    users_count: int = 1000
    picked_opinions_count: int = 100
    alpha: float = 1.35  # bigger => more skew (more "50+ upvotes" style concentration)
    seed: int | None = None


class Command(BaseCommand):
    help = "Generate dummy Discord users, opinions, and upvotes for local/dev testing."

    def add_arguments(self, parser):
        parser.add_argument("--seed", type=int, default=12345, help="Random seed for deterministic generation.")

    @transaction.atomic
    def handle(self, *args, **options):
        cfg = _Config(seed=options.get("seed"))
        rng = random.Random(cfg.seed)  # noqa: S311

        channel = DiscordChannel.objects.order_by("id").first()
        if channel is None:
            raise CommandError("No DiscordChannel found. Create at least one channel first.")

        roles = list(DiscordRole.objects.all())
        if not roles:
            raise CommandError("No DiscordRole found. Create at least one role first (needed for even-id users).")

        now = timezone.now()
        month_ago = now - timedelta(days=30)

        # 1) Create users (id=1..1000)
        users_to_create: list[DiscordUser] = []
        for user_id in range(1, cfg.users_count + 1):
            name = f"dummy{user_id}"
            users_to_create.append(DiscordUser(id=user_id, username=name, display_name=name))
        DiscordUser.objects.bulk_create(users_to_create, ignore_conflicts=True, batch_size=1000)

        # Re-fetch users to ensure we have actual DB objects (and any pre-existing ones).
        users = list(DiscordUser.objects.filter(id__gte=1, id__lte=cfg.users_count).order_by("id"))
        if len(users) != cfg.users_count:
            raise CommandError(
                f"Expected {cfg.users_count} users with ids 1..{cfg.users_count}, found {len(users)}. "
                "If your DB already has conflicting IDs, clear them or pick a different range."
            )

        # 2) Assign a random role to even-id users
        user_roles_to_create: list[UserRole] = []
        even_user_ids = set()
        for u in users:
            if u.id % 2 == 0:
                even_user_ids.add(u.id)
                user_roles_to_create.append(UserRole(user=u, role=rng.choice(roles)))
        UserRole.objects.bulk_create(user_roles_to_create, ignore_conflicts=True, batch_size=1000)

        # 3) Create one opinion per user in the first channel
        opinions_to_create: list[Opinion] = []
        opinion_created_at: list[tuple[Opinion, timezone.datetime]] = []

        for u in users:
            has_role = u.id in even_user_ids
            visibility = Opinion.Visibility.FEATURED if has_role else Opinion.Visibility.HIDDEN

            emoji = rng.choice(_EMOJIS)

            # 50% short (10..100), 50% long (100..2000)
            if rng.random() < 0.5:
                target_len = rng.randint(10, 100)
            else:
                target_len = rng.randint(100, 2000)

            content = _make_lorem_text(target_len=target_len, rng=rng)
            created_at = _random_dt_between(month_ago, now, rng=rng)

            opinion = Opinion(
                channel=channel,
                author=u,
                emoji=emoji,
                content=content,
                visibility=visibility,
                status=Opinion.Status.VALID,
            )
            opinions_to_create.append(opinion)
            opinion_created_at.append((opinion, created_at))

        Opinion.objects.bulk_create(opinions_to_create, batch_size=1000)

        for opinion, created_at in opinion_created_at:
            opinion.created_at = created_at
        Opinion.objects.bulk_update(opinions_to_create, ["created_at"], batch_size=1000)

        # Re-fetch opinions for these users in this channel (in case DB had previous data, or bulk_create didn't populate ids).
        created_opinions = list(
            Opinion.objects.filter(channel=channel, author_id__gte=1, author_id__lte=cfg.users_count)
            .order_by("id")
            .only("id", "author_id", "channel_id")
        )
        if len(created_opinions) < cfg.users_count:
            raise CommandError(
                f"Expected at least {cfg.users_count} opinions for users 1..{cfg.users_count} in channel {channel.id}, "
                f"found {len(created_opinions)}."
            )

        # 4) Pick 100 opinions randomly
        if len(created_opinions) < cfg.picked_opinions_count:
            raise CommandError(
                f"Not enough opinions to sample {cfg.picked_opinions_count}. Found {len(created_opinions)}."
            )
        picked_opinions = rng.sample(created_opinions, cfg.picked_opinions_count)

        # 5) Create one upvote per user, picking from the 100 with a skewed distribution
        #    Weights ~ 1/(rank^alpha) to produce a “some opinions get 50+ upvotes” effect.
        ranked = list(picked_opinions)
        rng.shuffle(ranked)  # randomize which opinions become the “popular” ones
        weights = [1.0 / ((i + 1) ** cfg.alpha) for i in range(len(ranked))]

        upvotes_to_create: list[Upvote] = []
        for u in users:
            has_role = u.id in even_user_ids
            visibility = Upvote.Visibility.FEATURED if has_role else Upvote.Visibility.HIDDEN

            opinion = rng.choices(ranked, weights=weights, k=1)[0]
            upvotes_to_create.append(
                Upvote(
                    channel=channel,
                    author=u,
                    opinion=opinion,
                    visibility=visibility,
                    status=Upvote.Status.VALID,
                    created_at=_random_dt_between(month_ago, now, rng=rng),
                )
            )

        Upvote.objects.bulk_create(upvotes_to_create, batch_size=1000)

        self.stdout.write(
            self.style.SUCCESS(
                f"Done.\n"
                f"- Channel: {channel.id}\n"
                f"- Users: {len(users)} (ids 1..{cfg.users_count})\n"
                f"- UserRoles created (even ids): {len(user_roles_to_create)}\n"
                f"- Opinions created: {cfg.users_count}\n"
                f"- Opinions sampled for upvotes: {cfg.picked_opinions_count}\n"
                f"- Upvotes created: {len(upvotes_to_create)}\n"
                f"- Seed: {cfg.seed}\n"
            )
        )
