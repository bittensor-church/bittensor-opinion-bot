from django.core.management.base import BaseCommand
from opinion_bot.opinion_bot.discord_bot.discord_bot_service import run_bot

class Command(BaseCommand):
    help = 'Runs the Discord bot service'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Discord bot...'))
        run_bot()