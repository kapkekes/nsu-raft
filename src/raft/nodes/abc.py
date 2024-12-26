__all__ = (
    "Node",
)

from abc import abstractmethod

from raft.dispatchers.message import RaftMessageDispatcher
from raft.dispatchers.response import RaftResponseDispatcher


class Node(RaftMessageDispatcher, RaftResponseDispatcher):
    @abstractmethod
    async def start(self) -> None:
        ...

    @abstractmethod
    async def stop(self) -> None:
        ...
