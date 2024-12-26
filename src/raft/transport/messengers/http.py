__all__ = (
    "HttpMessenger",
)

import httpx

from raft.dispatchers.response import RaftResponseDispatcher
from raft.exceptions import UninitializedMessengerError
from raft.protocol.messages import AppendEntriesMessage, RequestVoteMessage
from raft.protocol.responses import AppendEntriesResponse, RequestVoteResponse
from raft.protocol.shared import ServerId
from raft.transport.messengers.abc import Messenger
from raft.transport.shared.http import APPEND_ENTRIES_ROUTE, REQUEST_VOTE_ROUTE


class HttpMessenger(Messenger):
    def __init__(self, server_id: ServerId, host: str, port: int) -> None:
        super().__init__(server_id, host, port)
        self._client = httpx.AsyncClient(base_url=f"http://{host}:{port}")
        self._dispatcher: RaftResponseDispatcher | None  = None

    @property
    def dispatcher(self) -> RaftResponseDispatcher:
        if (dispatcher := self._dispatcher) is None:
            raise UninitializedMessengerError()

        return dispatcher

    async def start(self, dispatcher: RaftResponseDispatcher) -> None:
        self._dispatcher = dispatcher
        _ = await self._client.__aenter__()

    async def stop(self) -> None:
        return await self._client.__aexit__()

    async def send_append_entries(self, message: AppendEntriesMessage) -> None:
        response = await self._client.post(APPEND_ENTRIES_ROUTE, content=message.model_dump_json())
        _ = response.raise_for_status()
        return await self.dispatcher.dispatch_append_entries_response(
            self._server_id,
            AppendEntriesResponse.model_validate_json(response.content),
        )

    async def send_request_vote(self, message: RequestVoteMessage) -> None:
        response = await self._client.post(REQUEST_VOTE_ROUTE, content=message.model_dump_json())
        _ = response.raise_for_status()
        return await self.dispatcher.dispatch_request_vote_response(
            self._server_id,
            RequestVoteResponse.model_validate_json(response.content),
        )
