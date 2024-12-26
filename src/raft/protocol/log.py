__all__ = (
    "Storage",
    "StubCommand",
    "SetCommand",
    "DeleteCommand",
    "LogEntry",
    "Log",
)

from collections import UserList
from collections.abc import MutableMapping
from typing import Annotated, Literal, Optional, Self

from pydantic import BaseModel, Field

Storage = MutableMapping[bytes, bytes]


class StubCommand(BaseModel):
    type: Annotated[Literal["stub"], Field("stub")]

    def apply(self, storage: Storage) -> None:
        pass


class SetCommand(BaseModel):
    type: Annotated[Literal["set"], Field("set")]
    key: bytes
    value: bytes

    def apply(self, storage: Storage) -> None:
        storage[self.key] = self.value


class DeleteCommand(BaseModel):
    type: Annotated[Literal["delete"], Field("delete")]
    key: bytes

    def apply(self, storage: Storage) -> None:
        _ = storage.pop(self.key, None)


class LogEntry(BaseModel):
    command: Annotated[StubCommand | SetCommand | DeleteCommand, Field(discriminator="type")]
    got_at_term: int

    @classmethod
    def stub(cls, term: int = 0) -> Self:
        return cls(command=StubCommand(type="stub"), got_at_term=term)


class Log(UserList[LogEntry]):
    def get(self, index: int) -> Optional[LogEntry]:
        try:
            return self.data[index]
        except IndexError:
            return None

    def last_index(self) -> int:
        return len(self.data) - 1
