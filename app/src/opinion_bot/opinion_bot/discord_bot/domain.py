from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OpinionCommandEvent:
    emoji: str
    message: str

@dataclass(frozen=True, slots=True)
class OpinionUpvoteEvent:
    channel_id: int
    message_id: int

@dataclass(frozen=True, slots=True)
class OpinionMessage:
    opinion_id: int
    channel_id: int
    user_id: int
    emoji: str
    message: str
