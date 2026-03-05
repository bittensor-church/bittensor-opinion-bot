from __future__ import annotations

import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from opinion_bot.opinion_bot.models import Opinion, Upvote


def _random_dt_between(start, end, *, rng: random.Random):
    if end <= start:
        return start
    span = (end - start).total_seconds()
    return start + timedelta(seconds=rng.random() * span)


class Command(BaseCommand):
    help = "Randomize created_at for opinions and upvotes authored by users in a given id range."

    def add_arguments(self, parser):
        parser.add_argument("--min-user-id", type=int, default=1)
        parser.add_argument("--max-user-id", type=int, default=1000)
        parser.add_argument("--days", type=int, default=30, help="Randomize within the last N days.")
        parser.add_argument("--seed", type=int, default=12345, help="Random seed for deterministic runs.")
        parser.add_argument("--batch-size", type=int, default=2000)
        parser.add_argument("--dry-run", action="store_true", help="Compute changes but do not write to DB.")

    @transaction.atomic
    def handle(self, *args, **options):
        min_user_id: int = options["min_user_id"]
        max_user_id: int = options["max_user_id"]
        days: int = options["days"]
        seed: int = options["seed"]
        batch_size: int = options["batch_size"]
        dry_run: bool = options["dry_run"]

        if min_user_id > max_user_id:
            raise ValueError("--min-user-id must be <= --max-user-id")
        if days <= 0:
            raise ValueError("--days must be > 0")
        if batch_size <= 0:
            raise ValueError("--batch-size must be > 0")

        rng = random.Random(seed)  # noqa: S311

        now = timezone.now()
        start = now - timedelta(days=days)

        self.stdout.write(
            f"Randomizing created_at for author_id in [{min_user_id}, {max_user_id}] "
            f"within [{start.isoformat()}, {now.isoformat()}]. Seed={seed}. Batch size={batch_size}. Dry-run={dry_run}."
        )

        # --- Opinions ---
        opinions_qs = (
            Opinion.objects.filter(author_id__gte=min_user_id, author_id__lte=max_user_id)
            .only("id", "created_at")
            .order_by("id")
        )
        opinions_total = opinions_qs.count()
        self.stdout.write(f"Matched opinions: {opinions_total}.")

        opinions_updated = 0
        opinions_buffer: list[Opinion] = []

        for opinion in opinions_qs.iterator(chunk_size=batch_size):
            opinion.created_at = _random_dt_between(start, now, rng=rng)
            opinions_buffer.append(opinion)

            if len(opinions_buffer) >= batch_size:
                if not dry_run:
                    Opinion.objects.bulk_update(opinions_buffer, ["created_at"], batch_size=batch_size)
                opinions_updated += len(opinions_buffer)
                opinions_buffer.clear()

        if opinions_buffer:
            if not dry_run:
                Opinion.objects.bulk_update(opinions_buffer, ["created_at"], batch_size=batch_size)
            opinions_updated += len(opinions_buffer)

        # --- Upvotes ---
        upvotes_qs = (
            Upvote.objects.filter(author_id__gte=min_user_id, author_id__lte=max_user_id)
            .only("id", "created_at")
            .order_by("id")
        )
        upvotes_total = upvotes_qs.count()
        self.stdout.write(f"Matched upvotes: {upvotes_total}.")

        upvotes_updated = 0
        upvotes_buffer: list[Upvote] = []

        for upvote in upvotes_qs.iterator(chunk_size=batch_size):
            upvote.created_at = _random_dt_between(start, now, rng=rng)
            upvotes_buffer.append(upvote)

            if len(upvotes_buffer) >= batch_size:
                if not dry_run:
                    Upvote.objects.bulk_update(upvotes_buffer, ["created_at"], batch_size=batch_size)
                upvotes_updated += len(upvotes_buffer)
                upvotes_buffer.clear()

        if upvotes_buffer:
            if not dry_run:
                Upvote.objects.bulk_update(upvotes_buffer, ["created_at"], batch_size=batch_size)
            upvotes_updated += len(upvotes_buffer)

        self.stdout.write(
            self.style.SUCCESS(
                f"Done.\n"
                f"- Updated opinions: {opinions_updated}/{opinions_total}\n"
                f"- Updated upvotes: {upvotes_updated}/{upvotes_total}"
            )
        )
