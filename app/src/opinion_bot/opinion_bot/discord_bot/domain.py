from dataclasses import dataclass


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
    """Discord upvote button click interaction event"""

    channel_id: int
    user: InteractionUser
    message_id: int


@dataclass(frozen=True, slots=True)
class OpinionMessage:
    """Discord opinion message to be published"""

    header: str
    content: str
