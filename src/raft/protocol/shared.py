__all__ = (
    "ServerId",
    "server_id",
    "State",
)

import enum
from typing import Any

ServerId = str


def server_id(value: Any) -> ServerId:
    return str(value)


class State(enum.IntEnum):
    FOLLOWER = 0
    CANDIDATE = 1
    LEADER = 2
