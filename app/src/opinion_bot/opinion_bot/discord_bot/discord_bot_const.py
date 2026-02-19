from enum import IntEnum

DISCORD_API_BASE_URL = "https://discord.com/api/v10"

UPVOTE_BUTTON_ID = "opinion:upvote"

class DiscordComponentType(IntEnum):
    ACTION_ROW = 1
    BUTTON = 2


class DiscordButtonStyle(IntEnum):
    PRIMARY = 1
