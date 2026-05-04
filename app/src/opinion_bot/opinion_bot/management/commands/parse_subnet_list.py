import json
import sys

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "A dev only tool for parsing the subnet list obtained by `btcli subnet list --json.out` "
        "and producing a dict that can be used in create_subnet_instances.py"
    )

    def handle(self, *args, **options):
        data = json.load(sys.stdin)
        for netuid in data["subnets"]:
            if netuid != "0":
                name = data["subnets"][netuid]["subnet_name"]
                print(f'{netuid}: "{name}",')
