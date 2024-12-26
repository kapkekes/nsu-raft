__all__ = (
    "AppendEntriesMessage",
    "RequestVoteMessage",
)

from collections.abc import Sequence

from pydantic import BaseModel

from raft.protocol.log import LogEntry
from raft.protocol.shared import ServerId


class AppendEntriesMessage(BaseModel):
    term: int
    leader_id: ServerId
    prev_log_index: int
    prev_log_term: int
    entries: Sequence[LogEntry]
    leader_commit_index: int


class RequestVoteMessage(BaseModel):
    term: int
    candidate_id: ServerId
    last_log_index: int
    last_log_term: int
