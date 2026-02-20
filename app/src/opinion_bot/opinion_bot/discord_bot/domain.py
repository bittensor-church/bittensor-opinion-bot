from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InteractionUser:
    user_id: int
    username: str
    display_name: str
    roles_ids: list[int]

@dataclass(frozen=True, slots=True)
class OpinionCommandEvent:
    channel_id: int
    user: InteractionUser
    emoji: str
    message: str

@dataclass(frozen=True, slots=True)
class OpinionUpvoteEvent:
    channel_id: int
    message_id: int
    user: InteractionUser

@dataclass(frozen=True, slots=True)
class OpinionMessage:
    header: str
    content: str
