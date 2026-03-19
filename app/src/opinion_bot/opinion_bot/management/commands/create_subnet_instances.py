from django.core.management.base import BaseCommand
from django.db import transaction

from opinion_bot.opinion_bot.models import SubnetInstance

instances = {
    64: "ش Chutes",
    3: "γ τemplar",
    4: "δ Targon",
    120: "ⴷ Affine",
    51: "ת lium.io",
    8: "θ Vanta",
    62: "ز Ridges",
    75: "م Hippius",
    44: "ף Score",
    9: "ι iota",
    56: "ج Gradients",
    39: "מ basilica",
    81: "ᚠ grail",
    68: "ظ NOVA",
    19: "t blockmachine",
    5: "ε Hone",
    29: "ה Coldint",
    93: "ᚃ Bitcast",
    34: "י BitMind",
    11: "λ TrajectoryRL",
    1: "α Apex",
    24: "ω Quasar",
    17: "ρ 404—GEN",
    14: "テ TAOHash",
    13: "ν Data Universe",
    50: "ש Synth",
    71: "ㄴ Leadpoet",
    28: "ד oracle",
    63: "س Quantum Innovate",
    85: "ᚱ Vidaio",
    95: "ᚅ nion",
    33: "ט ReadyAI",
    12: "μ Compute Horde",
    2: "β DSperse",
    66: "ض AlphaCore",
    52: "ا Dojo",
    6: "ζ Numinous",
    35: "ך Cartha",
    18: "σ Zeus",
    43: "ע Graphite",
    53: "ب EfficientFrontier",
    10: "κ Swap",
    41: "נ Almanac",
    23: "ψ Trishool",
    58: "خ Handshake",
    54: "ت Yanez MIID",
    21: "φ OMEGA.inc: The Aw...",
    74: "ل Gittensor",
    22: "χ Desearch",
    16: "π BitAds",
    61: "ر RedTeam",
    26: "ඞ Kinitro",
    48: "ק Quantum Compute",
    46: "ץ RESI",
    25: "א Mainframe",
    59: "د Babelbit",
    60: "ذ Bitsec.ai",
    124: "˙ Swarm",
    65: "ص TAO Private Network",
    73: "ك MetaHash",
    37: "ל Aurelius",
    121: "Ⲅ sundae_bar",
    100: "დ Plaτform",
    45: "פ Talisman AI",
    7: "η",
    30: "ו Pending",
    27: "ג Nodexo",
    77: "ه Liquidity",
    127: "𑀅 Astrid",
    20: "υ GroundLayer",
    32: "ח ItsAI",
    40: "ן Chunking",
    103: "Ա Djinn",
    115: "Ѕ HashiChain",
    106: "Դ VoidAI",
    125: ": 8 Ball",
    98: "ბ ForeverMoney",
    69: "ع ain",
    57: "ح Sparket.AI",
    42: "ס Gopher",
    72: "ق StreetVision by N...",
    88: "ᛉ Investing",
    111: "Ё oneoneone",
    112: "Ђ minotaur",
    104: "Բ for sale (burn to...",
    36: "כ Web Agents - Auto...",
    89: "ᛒ InfiniteHash",
    79: "ي MVTRX",
    82: "ᚢ Hermes",
    122: "ⲅ Bitrecs",
    84: "モ ChipForge (Tatsu)",
    55: "ث NIOME",
    123: "˙ MANTIS",
    78: "و Loosh",
    119: "Ⲃ Satori",
    70: "غ Vericore",
    105: "Գ Beam",
    128: "න ByteLeap",
    83: "ᚦ CliqueAI",
    116: "ⴵ TaoLend",
    101: "ე eni",
    49: "ר Nepher Robotics",
    102: "ვ Vocence",
    110: "Ѐ Rich Kids of TAO",
    117: "Ⲁ BrainPlay",
    118: "ⲁ HODL ETF",
    114: "Є SOMA",
    15: "ο deval",
    86: "ᚳ ⚒",
    38: "ם colosseum",
    90: "ogham",
    107: "ミ Minos",
    113: "Ѓ TensorUSD",
    94: "ᚄ Bitsota",
    108: "Զ TalkHead",
    92: "ᚂ LUCID",
    80: "ى dogelayer",
    31: "ז Halftime",
    87: "Ы Luminar Network",
    109: "՞ Reserved",
    99: "გ Leoma",
    47: "צ EvolAI",
    76: "ن nun",
    126: "𑀃 Poker44",
    91: "ᚁ Bitstarter #1",
    97: "ა Constantinople",
    67: "ط ta",
    96: "᚛ X",
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
