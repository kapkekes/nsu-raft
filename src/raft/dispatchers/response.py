__all__ = (
    "RaftResponseDispatcher",
)

from abc import ABC, abstractmethod

from raft.protocol.responses import AppendEntriesResponse, RequestVoteResponse
from raft.protocol.shared import ServerId


class RaftResponseDispatcher(ABC):
    @abstractmethod
    async def dispatch_append_entries_response(self, server_id: ServerId, response: AppendEntriesResponse) -> None:
        ...

    @abstractmethod
    async def dispatch_request_vote_response(self, server_id: ServerId, response: RequestVoteResponse) -> None:
        ...
