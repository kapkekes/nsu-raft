__all__ = (
    "HttpResponder",
)

import uvicorn
from fastapi import FastAPI

from raft.dispatchers.message import RaftMessageDispatcher
from raft.exceptions import AlreadyWorkingResponderError
from raft.protocol.messages import AppendEntriesMessage, RequestVoteMessage
from raft.protocol.responses import AppendEntriesResponse, RequestVoteResponse
from raft.transport.responders.abc import Responder
from raft.transport.shared.http import APPEND_ENTRIES_ROUTE, REQUEST_VOTE_ROUTE


def build_app(dispatcher: RaftMessageDispatcher) -> FastAPI:
    app = FastAPI(title="HttpResponder", version="1.0.0")

    @app.post(APPEND_ENTRIES_ROUTE)
    async def append_entries(message: AppendEntriesMessage) -> AppendEntriesResponse:
        return await dispatcher.dispatch_append_entries_message(message)

    @app.post(REQUEST_VOTE_ROUTE)
    async def request_vote(message: RequestVoteMessage) -> RequestVoteResponse:
        return await dispatcher.dispatch_request_vote_message(message)

    return app


class HttpResponder(Responder):
    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._uvicorn_server: uvicorn.Server | None = None

    async def start(self, dispatcher: RaftMessageDispatcher) -> None:
        if self._uvicorn_server is not None:
            raise AlreadyWorkingResponderError()

        fastapi_app = build_app(dispatcher)
        uvicorn_config = uvicorn.Config(fastapi_app, self._host, self._port, log_level="critical")
        self._uvicorn_server = uvicorn.Server(uvicorn_config)
        return await self._uvicorn_server.serve()

    async def stop(self) -> None:
        if uvicorn_server := self._uvicorn_server:
            self._uvicorn_server = None
            await uvicorn_server.shutdown()
