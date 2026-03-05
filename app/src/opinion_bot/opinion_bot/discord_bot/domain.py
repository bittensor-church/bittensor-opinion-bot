from dataclasses import dataclass

from opinion_bot.opinion_bot.discord_bot.exceptions import BotRuntimeError


@dataclass(frozen=True, slots=True)
class InteractionUser:
    """Discord user data associated with an interaction (slash command, button click, etc.)"""

    user_id: int
    username: str
    display_name: str
    roles_ids: list[int]


@dataclass(frozen=True, slots=True)
class OpinionCommandEvent:
    """Discord opinion slash command interaction event"""

    channel_id: int
    user: InteractionUser
    emoji: str
    message: str


@dataclass(frozen=True, slots=True)
class OpinionUpvoteEvent:
    """Discord upvote button click or upvote slash command interaction event"""

    channel_id: int
    user: InteractionUser
    # exactly one of message_id and opinion_id must be set
    message_id: int | None = None
    opinion_id: int | None = None

    def __post_init__(self) -> None:
        if self.message_id is None and self.opinion_id is None:
            raise BotRuntimeError("OpinionUpvoteEvent requires either message_id or opinion_id to be set.")
        if self.message_id is not None and self.opinion_id is not None:
            raise BotRuntimeError("OpinionUpvoteEvent requires either message_id or opinion_id to be set, not both.")


@dataclass(frozen=True, slots=True)
class OpinionMessage:
    """Discord opinion message to be published"""

    header: str
    content: str
