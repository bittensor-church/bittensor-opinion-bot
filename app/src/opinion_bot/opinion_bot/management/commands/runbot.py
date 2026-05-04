from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from opinion_bot.opinion_bot.discord_bot.discord_bot_service import run_bot


class Command(BaseCommand):
    help = "Runs the Discord bot service"

    def handle(self, *args, **options):
        if not settings.CONNECT_TO_DISCORD:
            self.stdout.write(self.style.WARNING("Discord bot disabled (check .env CONNECT_TO_DISCORD)"))
            return

        self.stdout.write(self.style.SUCCESS("Starting Discord bot..."))
        try:
            run_bot()
        except Exception as exc:
            raise CommandError("Discord bot failed to start") from exc
