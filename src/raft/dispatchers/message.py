__all__ = (
    "RaftMessageDispatcher",
)

from abc import ABC, abstractmethod

from raft.protocol.messages import AppendEntriesMessage, RequestVoteMessage
from raft.protocol.responses import AppendEntriesResponse, RequestVoteResponse


class RaftMessageDispatcher(ABC):
    @abstractmethod
    async def dispatch_append_entries_message(self, message: AppendEntriesMessage) -> AppendEntriesResponse:
        ...

    @abstractmethod
    async def dispatch_request_vote_message(self, message: RequestVoteMessage) -> RequestVoteResponse:
        ...
