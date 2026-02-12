import os
import sys

from django.apps import AppConfig


class Opinion_botConfig(AppConfig):
    name = "opinion_bot.opinion_bot"

    def ready(self) -> None:
        # Only start when running the dev server (not during migrate, shell, celery, etc).
        if len(sys.argv) < 2 or sys.argv[1] != "runserver":
            return

        # Django autoreloader imports apps twice; only start in the reloader's main process.
        if os.environ.get("RUN_MAIN") != "true":
            return

        # Local import keeps startup light and avoids importing discord.py when not needed.
        from .discord_bot.discord_bot_service import start_in_background

        start_in_background()