__all__ = (
    "Messenger",
)

from abc import ABC, abstractmethod

from raft.dispatchers.response import RaftResponseDispatcher
from raft.protocol.messages import AppendEntriesMessage, RequestVoteMessage
from raft.protocol.shared import ServerId


class Messenger(ABC):
    def __init__(self, server_id: ServerId, host: str, port: int) -> None:
        self._server_id = server_id
        self._host = host
        self._port = port
        self._dispatcher: RaftResponseDispatcher | None = None

    @abstractmethod
    async def start(self, dispatcher: RaftResponseDispatcher) -> None:
        ...

    @abstractmethod
    async def stop(self) -> None:
        ...

    @abstractmethod
    async def send_append_entries(self, message: AppendEntriesMessage) -> None:
        ...

    @abstractmethod
    async def send_request_vote(self, message: RequestVoteMessage) -> None:
        ...
