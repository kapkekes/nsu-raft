__all__ = (
    "Responder",
)

from abc import ABC, abstractmethod

from raft.dispatchers.message import RaftMessageDispatcher


class Responder(ABC):
    @abstractmethod
    async def start(self, dispatcher: RaftMessageDispatcher) -> None:
        ...

    @abstractmethod
    async def stop(self) -> None:
        ...
