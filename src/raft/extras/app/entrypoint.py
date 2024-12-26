import argparse
import asyncio
import collections.abc
import contextlib
import logging.config
from contextlib import asynccontextmanager
from importlib.resources import as_file, files
from typing import Any, NamedTuple, Self

import tomllib
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse

from raft.extras import app
from raft.nodes.naive import NaiveNode
from raft.protocol.shared import server_id
from raft.transport.messengers.http import HttpMessenger
from raft.transport.responders.http import HttpResponder


class Address(NamedTuple):
    host: str
    port: int

    def __str__(self) -> str:
        return f"{self.host}:{self.port}"

    @classmethod
    def load(cls, value: str) -> Self:
        host, _, port = value.partition(":")
        return cls(host, int(port))


class Arguments(NamedTuple):
    local: Address
    remote: list[Address]
    mono: bool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="raft-node",
        description="quite simple distributed key-value storage",
        epilog="note: responder will be launched at `<given-port> + 100`, so don't use ports from the end",
    )
    parser.add_argument(
        "-l", "--local",
        required=True, type=Address.load,
        help="address of this node"
    )
    parser.add_argument(
        "-r", "--remote", nargs="+",
        required=True, type=Address.load,
        help="addresses of other nodes"
    )
    parser.add_argument(
        "-m", "--mono",
        action="store_true", default=False,
        help="do not use colors for logging",
    )
    return parser


def build_app(lifespan: Any, node: NaiveNode) -> FastAPI:
    app = FastAPI(title="Key-value Storage Raft Node", version="1.0.0", lifespan=lifespan)

    @app.get("/{key}")
    async def get(key: bytes) -> Response:
        value = node._storage.get(key)
        if value is None:
            return Response(status_code=404)

        return PlainTextResponse(content=value, status_code=202)

    @app.post("/{key}")
    async def set(request: Request, key: bytes) -> Response:
        if redirect := node.add_entry({"type": "set", "key": key, "value": await request.body()}):
            return PlainTextResponse(content=redirect, status_code=405)

        return Response(status_code=202)

    @app.delete("/{key}")
    async def delete(key: bytes) -> Response:
        if redirect := node.add_entry({"type": "delete", "key": key}):
            return PlainTextResponse(content=redirect, status_code=405)

        return Response(status_code=202)

    return app


async def amain(args: Arguments) -> None:
    local: Address = args.local
    remote: list[Address] = args.remote

    node = NaiveNode(
        server_id=server_id(local),
        responsders=[HttpResponder(local.host, local.port + 100)],
        messengers=[HttpMessenger(server_id(address), address.host, address.port + 100) for address in remote]
    )
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> collections.abc.AsyncGenerator[None, Any]:
        await node.start()
        try:
            yield
        finally:
            await node.stop()

    app = build_app(lifespan, node)
    uvicorn_config = uvicorn.Config(app, host=local.host, port=local.port, log_level="critical")
    uvicorn_server = uvicorn.Server(uvicorn_config)
    await uvicorn_server.serve()


def main() -> None:
    args = Arguments(**vars(build_parser().parse_args()))
    with as_file(files(app)) as extras_path, open(extras_path / "logging.toml", "rb") as file:
        config = tomllib.load(file)
        config["formatters"]["default"].setdefault("defaults", {})["$switch"] = not args.mono
        logging.config.dictConfig(config)
    with contextlib.suppress(KeyboardInterrupt):
        return asyncio.run(amain(args))


if __name__ == "__main__":
    main()
