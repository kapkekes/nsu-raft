__all__ = (
    "schedule",
)

import asyncio
from collections.abc import Awaitable, Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class schedule(Generic[T]):
    def __init__(
        self,
        callback: Callable[[], Awaitable[T]],
        delay: Callable[[], float],
    ) -> None:
        self._delay = delay
        self._callback = callback
        self._task: asyncio.Task[T] | None = None
        self._lock = asyncio.Lock()

    def _cancel(self) -> None:
        if self._task is not None:
            _ = self._task.cancel()
            self._task = None

    async def _worker(self) -> T:
        await asyncio.sleep(self._delay())
        return await self._callback()

    async def cancel(self) -> None:
        async with self._lock:
            self._cancel()

    async def plan(self) -> None:
        async with self._lock:
            self._cancel()
            self._task = asyncio.ensure_future(self._worker())
