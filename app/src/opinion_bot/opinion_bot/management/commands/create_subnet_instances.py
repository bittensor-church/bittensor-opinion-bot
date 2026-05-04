from django.core.management.base import BaseCommand
from django.db import transaction

from opinion_bot.opinion_bot.models import SubnetInstance

instances = {
    64: "Chutes",
    51: "lium.io",
    4: "Targon",
    120: "Affine",
    44: "Score",
    8: "Vanta",
    3: "deprecated",
    9: "iota",
    56: "Gradients",
    75: "Hippius",
    95: "nion",
    62: "Ridges",
    68: "NOVA",
    5: "Hone",
    17: "404—GEN",
    19: "blockmachine",
    24: "Quasar",
    66: "ninja",
    34: "BitMind",
    28: "gm",
    93: "Bitcast",
    11: "TrajectoryRL",
    85: "Vidaio",
    1: "Apex",
    14: "TAOHash",
    79: "MVTRX",
    50: "Synth",
    63: "Enigma",
    46: "RESI",
    15: "ORO",
    13: "Data Universe",
    81: "deprecated",
    12: "Compute Horde",
    52: "Dojo",
    54: "Yanez MIID",
    39: "deprecated",
    43: "Graphite",
    2: "DSperse",
    74: "Gittensor",
    29: "Coldint",
    53: "EfficientFrontier",
    10: "Swap",
    33: "ReadyAI",
    18: "Zeus",
    124: "Swarm",
    71: "Leadpoet",
    107: "Minos",
    35: "OxMarkets",
    21: "AdTAO",
    48: "Quantum Compute",
    41: "Almanac",
    61: "RedTeam",
    27: "Nodexo",
    22: "Desearch",
    30: "Pending",
    58: "Handshake",
    55: "NIOME",
    25: "Mainframe",
    6: "Numinous",
    16: "BitAds",
    97: "distil",
    121: "sundae_bar",
    37: "Aurelius",
    20: "GroundLayer",
    23: "Trishool",
    7: "Allways",  # codespell:ignore
    105: "Beam",
    32: "ItsAI",
    59: "Babelbit",
    103: "Djinn",
    65: "TAO Private Network",
    60: "Bitsec.ai",
    45: "Talisman AI",
    73: "Parked",
    125: "8 Ball",
    77: "Liquidity",
    69: "ain",
    40: "Chunking",
    42: "Unknown",
    100: "Plaτform",
    26: "beqar",
    83: "CliqueAI",
    98: "ForeverMoney",
    123: "MANTIS",
    106: "VoidAI",
    115: "HashiChain",
    72: "StreetVision by N...",
    88: "Investing",
    122: "Bitrecs",
    89: "InfiniteHash",
    111: "oneoneone",
    112: "minotaur",
    127: "Astrid",
    104: "for sale (burn to...",
    118: "Ditto",
    110: "Green Compute",
    119: "Satori",
    116: "TaoLend",
    128: "ByteLeap",
    38: "colosseum",
    114: "SOMA",
    101: "eni",
    91: "Bitstarter #1",
    113: "TensorUSD",
    49: "Nepher Robotics",
    117: "Unknown",
    86: "⚒",
    102: "ConnitoAI",
    99: "Leoma",
    92: "TensorClaw",
    108: "TalkHead",
    94: "Bitsota",
    109: "Academia",
    90: "ogham",
    31: "Halftime",
    87: "Luminar Network",
    126: "Poker44",
    47: "EvolAI",
    76: "Byzantium",
    80: "dogelayer",
    84: "ansuz",
    67: "Harnyx",
    57: "gaia",
    70: "NexisGen",
    36: "automata",
    78: "Vocence",
    96: "Verathos",
    82: "uruz",
}


class Command(BaseCommand):
    help = "Create missing SubnetInstance rows from the predefined instances map."

    def handle(self, *args, **options):
        created_count = 0
        skipped_count = 0

        with transaction.atomic():
            for netuid, name in instances.items():
                if SubnetInstance.objects.filter(netuid=netuid).exists():
                    skipped_count += 1
                    self.stdout.write(self.style.WARNING(f"Skipped existing subnet {netuid}: {name}"))
                    continue

                SubnetInstance.objects.create(netuid=netuid, name=name)
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Created subnet {netuid}: {name}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created {created_count} subnet instance(s), skipped {skipped_count} existing instance(s)."
            )
        )
