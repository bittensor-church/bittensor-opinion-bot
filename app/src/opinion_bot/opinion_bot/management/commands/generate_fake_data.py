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


def _weighted_sample_without_replacement(items, *, k: int, weights, rng: random.Random):
    """
    Sample up to k distinct items without replacement using weights.
    Simple O(k*n) approach (fine for our sizes: <= 128 channels).
    """
    if k <= 0 or not items:
        return []
    if len(items) != len(weights):
        raise ValueError("items and weights must have the same length")

    chosen = []
    pool_items = list(items)
    pool_weights = list(weights)

    for _ in range(min(k, len(pool_items))):
        total = sum(w for w in pool_weights if w > 0)
        if total <= 0:
            # all remaining weights are 0 => fall back to uniform among remaining
            idx = rng.randrange(len(pool_items))
        else:
            idx = rng.choices(range(len(pool_items)), weights=pool_weights, k=1)[0]
        chosen.append(pool_items.pop(idx))
        pool_weights.pop(idx)

    return chosen


@dataclass(frozen=True)
class _Config:
    users_count: int = 1000
    picked_opinions_count: int = 100
    alpha: float = 1.35  # bigger => more skew (more "50+ upvotes" style concentration)
    seed: int | None = None

    user_id_from: int = 1
    user_id_to: int = 1000

    netuid_from: int = 1
    netuid_to: int = 128


class Command(BaseCommand):
    help = "Generate dummy Discord channels, users, opinions, and upvotes for local/dev testing."

    def add_arguments(self, parser):
        parser.add_argument("--seed", type=int, default=12345, help="Random seed for deterministic generation.")
        parser.add_argument("--user-id-from", type=int, default=1, help="First DiscordUser.id (inclusive).")
        parser.add_argument("--user-id-to", type=int, default=1000, help="Last DiscordUser.id (inclusive).")
        parser.add_argument(
            "--netuid-from",
            type=int,
            default=1,
            help="First subnet netuid to ensure DiscordChannel exists for (inclusive).",
        )
        parser.add_argument(
            "--netuid-to",
            type=int,
            default=128,
            help="Last subnet netuid to ensure DiscordChannel exists for (inclusive).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        cfg = _Config(
            seed=options.get("seed"),
            user_id_from=options.get("user_id_from"),
            user_id_to=options.get("user_id_to"),
            netuid_from=options.get("netuid_from"),
            netuid_to=options.get("netuid_to"),
        )
        rng = random.Random(cfg.seed)  # noqa: S311

        if cfg.user_id_from <= 0 or cfg.user_id_to < cfg.user_id_from:
            raise CommandError("--user-id-from must be > 0 and --user-id-to must be >= --user-id-from")
        if cfg.netuid_from <= 0 or cfg.netuid_to < cfg.netuid_from:
            raise CommandError("--netuid-from must be > 0 and --netuid-to must be >= --netuid-from")

        roles = list(DiscordRole.objects.all())
        if not roles:
            raise CommandError("No DiscordRole found. Create at least one role first (needed for even-id users).")

        now = timezone.now()
        month_ago = now - timedelta(days=30)

        # 0) Ensure channels for netuid range exist (create ONLY for netuids that are not present yet)
        netuids_in_range = list(range(cfg.netuid_from, cfg.netuid_to + 1))
        existing_netuids = set(
            DiscordChannel.objects.filter(netuid__in=netuids_in_range).values_list("netuid", flat=True)
        )

        channels_to_create: list[DiscordChannel] = []
        for netuid in netuids_in_range:
            if netuid in existing_netuids:
                continue
            channels_to_create.append(DiscordChannel(id=netuid, netuid=netuid, name=f"Subnet {netuid}"))

        if channels_to_create:
            DiscordChannel.objects.bulk_create(channels_to_create, batch_size=1000)

        channels = list(
            DiscordChannel.objects.filter(netuid__gte=cfg.netuid_from, netuid__lte=cfg.netuid_to)
            .order_by("netuid")
            .only("id", "netuid", "name")
        )
        if not channels:
            raise CommandError("No DiscordChannel found after creation attempt. Check DB constraints/migrations.")

        # 1) Create users in the given id range if missing (do not error if some already exist)
        users_to_create: list[DiscordUser] = []
        for user_id in range(cfg.user_id_from, cfg.user_id_to + 1):
            name = f"dummy{user_id}"
            users_to_create.append(DiscordUser(id=user_id, username=name, display_name=name))
        DiscordUser.objects.bulk_create(users_to_create, ignore_conflicts=True, batch_size=1000)

        users = list(
            DiscordUser.objects.filter(id__gte=cfg.user_id_from, id__lte=cfg.user_id_to)
            .order_by("id")
            .only("id", "username", "display_name")
        )
        if not users:
            raise CommandError("No users found in the requested id range after creation attempt.")

        # 2) Assign a random role to even-id users (create missing links; keep existing)
        user_roles_to_create: list[UserRole] = []
        even_user_ids = set()
        for u in users_to_create:
            if u.id % 2 == 0:
                even_user_ids.add(u.id)
                user_roles_to_create.append(UserRole(user_id=u.id, role=rng.choice(roles)))
        UserRole.objects.bulk_create(user_roles_to_create, ignore_conflicts=True, batch_size=1000)

        # 3) Remove ONLY opinions and upvotes authored by users in given id range (do not touch other users)
        upvotes_deleted, _ = Upvote.objects.filter(
            author_id__gte=cfg.user_id_from, author_id__lte=cfg.user_id_to
        ).delete()
        opinions_deleted, _ = Opinion.objects.filter(
            author_id__gte=cfg.user_id_from, author_id__lte=cfg.user_id_to
        ).delete()

        # 4) Create random number of opinions per user:
        #    - 1..number_of_channels
        #    - max 1 per channel
        #    - pick channels with non-uniform distribution (global channel popularity weights)
        num_channels = len(channels)

        # Zipf-ish popularity for channels (lower netuid tends to get more opinions, but still randomized)
        # Shuffle channel "ranks" once so it's not always the same netuids that are popular.
        channel_ranked = list(channels)
        rng.shuffle(channel_ranked)
        channel_weights_ranked = [1.0 / ((i + 1) ** 1.15) for i in range(num_channels)]
        channel_weight_by_id = {ch.id: w for ch, w in zip(channel_ranked, channel_weights_ranked, strict=True)}

        opinions_to_create: list[Opinion] = []
        opinion_created_at: list[tuple[Opinion, timezone.datetime]] = []

        # also keep counts per channel for later upvote channel weighting
        opinions_count_by_channel_id = {ch.id: 0 for ch in channels}

        channel_ids = [ch.id for ch in channels]
        channel_weights = [channel_weight_by_id[ch_id] for ch_id in channel_ids]

        for u in users:
            has_role = u.id in even_user_ids
            visibility = Opinion.Visibility.FEATURED if has_role else Opinion.Visibility.HIDDEN

            k = rng.randint(1, num_channels)
            picked_channel_ids = _weighted_sample_without_replacement(
                channel_ids, k=k, weights=channel_weights, rng=rng
            )

            for ch_id in picked_channel_ids:
                emoji = rng.choice(_EMOJIS)

                # 50% short (10..100), 50% long (100..2000)
                target_len = rng.randint(10, 100) if rng.random() < 0.5 else rng.randint(100, 2000)
                content = _make_lorem_text(target_len=target_len, rng=rng)
                created_at = _random_dt_between(month_ago, now, rng=rng)

                opinion = Opinion(
                    channel_id=ch_id,
                    author_id=u.id,
                    emoji=emoji,
                    content=content,
                    visibility=visibility,
                    status=Opinion.Status.VALID,
                )
                opinions_to_create.append(opinion)
                opinion_created_at.append((opinion, created_at))
                opinions_count_by_channel_id[ch_id] += 1

        Opinion.objects.bulk_create(opinions_to_create, batch_size=2000)

        for opinion, created_at in opinion_created_at:
            opinion.created_at = created_at
        if opinions_to_create:
            Opinion.objects.bulk_update(opinions_to_create, ["created_at"], batch_size=2000)

        # 5) Create random number of upvotes per user:
        #    - 1..number_of_channels
        #    - 1 per channel
        #    - pick channels weighted by number of opinions in each channel (per current generation)
        #    - within each channel, keep “skewed popularity” like before (Zipf on a randomized ranking),
        #      but computed separately per channel.
        # Re-fetch opinions we just created for those users to get ids (and to build per-channel pools).
        created_opinions = list(
            Opinion.objects.filter(author_id__gte=cfg.user_id_from, author_id__lte=cfg.user_id_to).only(
                "id", "author_id", "channel_id"
            )
        )

        opinions_by_channel_id: dict[int, list[Opinion]] = {ch.id: [] for ch in channels}
        for op in created_opinions:
            if op.channel_id in opinions_by_channel_id:
                opinions_by_channel_id[op.channel_id].append(op)

        upvote_channel_weights = [float(opinions_count_by_channel_id[ch_id]) for ch_id in channel_ids]

        upvotes_to_create: list[Upvote] = []
        upvote_created_at: list[tuple[Upvote, timezone.datetime]] = []

        for u in users:
            has_role = u.id in even_user_ids
            visibility = Upvote.Visibility.FEATURED if has_role else Upvote.Visibility.HIDDEN

            k = rng.randint(1, num_channels)
            picked_channels_for_upvotes = _weighted_sample_without_replacement(
                channel_ids, k=k, weights=upvote_channel_weights, rng=rng
            )

            for ch_id in picked_channels_for_upvotes:
                pool = opinions_by_channel_id.get(ch_id) or []
                if not pool:
                    continue

                # Avoid self-upvoting if possible.
                pool_non_self = [op for op in pool if op.author_id != u.id]
                if pool_non_self:
                    pool = pool_non_self

                # Skew within channel: randomize who becomes "popular" in THIS channel, then Zipf weights by rank.
                ranked = list(pool)
                rng.shuffle(ranked)
                weights = [1.0 / ((i + 1) ** cfg.alpha) for i in range(len(ranked))]

                opinion = rng.choices(ranked, weights=weights, k=1)[0]
                created_at = _random_dt_between(month_ago, now, rng=rng)

                upvote = Upvote(
                    channel_id=ch_id,
                    author_id=u.id,
                    opinion_id=opinion.id,
                    visibility=visibility,
                    status=Upvote.Status.VALID,
                )
                upvotes_to_create.append(upvote)
                upvote_created_at.append((upvote, created_at))

        Upvote.objects.bulk_create(upvotes_to_create, batch_size=2000)

        for upvote, created_at in upvote_created_at:
            upvote.created_at = created_at
        if upvotes_to_create:
            Upvote.objects.bulk_update(upvotes_to_create, ["created_at"], batch_size=2000)

        self.stdout.write(
            self.style.SUCCESS(
                "Done.\n"
                f"- Channels ensured: netuid {cfg.netuid_from}..{cfg.netuid_to} (count {len(channels)})\n"
                f"- Users ensured: ids {cfg.user_id_from}..{cfg.user_id_to} (count {len(users)})\n"
                f"- UserRoles created (even ids, ignore_conflicts): {len(user_roles_to_create)}\n"
                f"- Deleted (scoped to user id range): upvotes={upvotes_deleted}, opinions={opinions_deleted}\n"
                f"- Opinions created: {len(opinions_to_create)}\n"
                f"- Upvotes created: {len(upvotes_to_create)}\n"
                f"- Seed: {cfg.seed}\n"
            )
        )
