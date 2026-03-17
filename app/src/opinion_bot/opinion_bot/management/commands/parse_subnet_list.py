import sys

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "A dev only tool for parsing the subnet list obtained by "
        "`btcli subnet list --subtensor.network finney` "
        "and producing a dict that can be used in create_subnet_instances.py"
    )

    def handle(self, *args, **options):
        res = dict()
        for line in sys.stdin:
            parts = line.rstrip("\n").split("│")
            if len(parts) >= 2:
                netuid = int(parts[0].strip())
                name = parts[1].strip()
                if 1 <= netuid <= 128:
                    res[netuid] = name

        print(res)
