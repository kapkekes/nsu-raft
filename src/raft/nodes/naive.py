__all__ = (
    "NaiveNode",
    "NaiveConfig",
)

import asyncio
import logging
import random
from collections.abc import Awaitable, Iterable, Sequence
from typing import Any, TypedDict, TypeVar

from raft.extras.app.logging import TRACE_INT
from raft.nodes.abc import Node
from raft.protocol.log import Log, LogEntry, Storage
from raft.protocol.messages import AppendEntriesMessage, RequestVoteMessage
from raft.protocol.responses import AppendEntriesResponse, RequestVoteResponse
from raft.protocol.shared import ServerId, State
from raft.schedule import schedule
from raft.transport.messengers.abc import Messenger
from raft.transport.responders.abc import Responder

T = TypeVar("T")
logger = logging.getLogger(__name__)


class NaiveConfig(TypedDict, total=False):
    heartbeat_period: float
    election_period_const: float
    election_period_rnd: float
    request_timeout: float


class NaiveNode(Node):
    __slots__ = (
        "_responders",
        "_messengers",
        "_state",
        "_server_id",
        "_storage",
        "_current_term",
        "_voted_for",
        "_log",
        "_current_votes",
        "_commit_index",
        "_last_applied",
        "_next_index",
        "_match_index",
        "_current_leader",
        "_schedule_heartbeat",
        "_schedule_election",
        "_request_timeout",
    )

    def __init__(
        self, 
        server_id: ServerId,
        responsders: Iterable[Responder],
        messengers: Iterable[Messenger],
        *,
        config: NaiveConfig | None = None,
    ) -> None:
        if config is None:
            config = NaiveConfig()

        self._responders = list(responsders)
        self._messengers = list(messengers)
        self._state = State.FOLLOWER
        self._server_id = server_id
        self._storage: Storage = {}

        # raft, persistent state
        self._current_term: int = 0
        self._voted_for: ServerId | None = None
        self._log = Log([LogEntry.stub()])
        self._current_votes: int = 0  # bonus

        # raft, volatile state
        self._commit_index: int = 0
        self._last_applied: int = 0

        # raft, leader only volatile state
        self._next_index: dict[ServerId, int] = {}
        self._match_index: dict[ServerId, int] = {}

        # quality of life
        self._current_leader: ServerId | None = None

        # scheduling and timeout shenanigans
        self._schedule_heartbeat = schedule(
            self._heartbeat_callback,
            lambda: config.get("heartbeat_period", 0.5),
        )
        self._schedule_election = schedule(
            self._election_callback,
            lambda: config.get("election_period_const", 2) + random.uniform(0, config.get("election_period_rnd", 0.5)),
        )
        self._request_timeout = config.get("request_timeout", 0.2)

    @property
    def state(self) -> State:
        return self._state

    @state.setter
    def state(self, new: State) -> None:
        if self._state == new:
            return

        old = self._state
        self._state = new
        logger.info("migrated from '%s' to '%s'", old.name, new.name)

    async def _with_timeout(self, aw: Awaitable[T]) -> T:
        async with asyncio.timeout(self._request_timeout):
            return await aw

    async def _update_term(self, term: int, force: bool = False) -> None:
        if term > self._current_term or force:
            logger.info("current term was '%s'; moving to '%s'", self._current_term, term)
            self._current_term = term
            self.state = State.FOLLOWER
            await self._schedule_heartbeat.cancel()
            self._voted_for = None
            self._current_votes = 0
            await self._schedule_election.plan()

    def _update_commit_index(self) -> None:
        for n in range(self._commit_index + 1, len(self._log)):
            count = sum(1 for match in self._match_index.values() if match >= n)
            if (len(self._messengers) + 1) / 2 < count + 1:
                if self._log[n].got_at_term == self._current_term:
                    self._commit_index = n
            else:
                break
        for index in range(self._last_applied + 1, self._commit_index + 1):
            self._log[index].command.apply(self._storage)
            self._last_applied += 1

    def _append_entries_message(self, prev_log_index: int, entires: Sequence[LogEntry]) -> AppendEntriesMessage:
        return AppendEntriesMessage(
            term=self._current_term,
            leader_id=self._server_id,
            prev_log_index=prev_log_index,
            prev_log_term=self._log[prev_log_index].got_at_term,
            entries=entires,
            leader_commit_index=self._commit_index
        )

    def _request_vote_message(self) -> RequestVoteMessage:
        return RequestVoteMessage(
            term=self._current_term,
            candidate_id=self._server_id,
            last_log_index=self._log.last_index(),
            last_log_term=self._log[-1].got_at_term,
        )

    async def start(self) -> None:
        logger.info("starting naive node '%s'", self._server_id)
        for responder in self._responders:
            _ = asyncio.ensure_future(responder.start(self))
        for messenger in self._messengers:
            _ = asyncio.ensure_future(messenger.start(self))
        await self._schedule_election.plan()

    async def stop(self) -> None:
        logger.info("stopping naive node '%s'", self._server_id)
        await asyncio.gather(
            self._schedule_election.cancel(),
            self._schedule_heartbeat.cancel(),
            *(responder.stop() for responder in self._responders),
            *(messenger.stop() for messenger in self._messengers),
            return_exceptions=True
        )

    async def dispatch_append_entries_message(self, message: AppendEntriesMessage) -> AppendEntriesResponse:
        logger.log(TRACE_INT, "received AppendEntires from '%s'", message.leader_id)
        if message.term < self._current_term:
            logger.debug("discarded AppendEntires from '%s', as their term is less than mine", message.leader_id)
            return AppendEntriesResponse(term=self._current_term, success=False)

        is_candidate = self._state == State.CANDIDATE
        await self._update_term(message.term, is_candidate)
        self._current_leader = message.leader_id

        if (
            self._log.last_index() < message.prev_log_index
            or self._log[message.prev_log_index].got_at_term != message.prev_log_term
        ):
            logger.info("removing log entries until '%s'", message.prev_log_index)
            self._log = self._log[:message.prev_log_index]
            await self._schedule_election.plan()
            return AppendEntriesResponse(term=self._current_term, success=False)

        if message.entries:
            logger.info("appending new entries: %s", message.entries)
            self._log.extend(message.entries)

        if message.leader_commit_index > self._commit_index:
            self._commit_index = min(message.leader_commit_index, self._log.last_index())
            for entry in self._log[self._last_applied + 1: self._commit_index + 1]:
                logger.debug("applying entry '%s'", entry)
                entry.command.apply(self._storage)

        await self._schedule_election.plan()
        return AppendEntriesResponse(term=self._current_term, success=True)

    async def dispatch_append_entries_response(self, server_id: ServerId, response: AppendEntriesResponse) -> None:
        logger.log(TRACE_INT, "received AppendEntries repsonse from '%s'", server_id)
        await self._update_term(response.term)
        if self.state != State.LEADER:
            return logger.debug(
                "discarded AppendEntries repsonse from '%s', as current state is '%s'", server_id, self.state.name,
            )

        if response.success:
            self._match_index[server_id] = min(self._next_index[server_id], self._log.last_index())
            self._next_index[server_id] = min(self._next_index[server_id] + 1, len(self._log))
            if self._commit_index != self._log.last_index():
                self._update_commit_index()
        else:
            self._next_index[server_id] -= 1
            self._match_index[server_id] = 0

    async def dispatch_request_vote_message(self, message: RequestVoteMessage) -> RequestVoteResponse:
        logger.log(TRACE_INT, "received RequestVote from '%s'", message.candidate_id)
        if message.term < self._current_term:
            logger.debug("discarded RequestVote from '%s', as their term is less than mine", message.candidate_id)
            return RequestVoteResponse(term=self._current_term, vote_granted=False)

        await self._update_term(message.term)
        if (
            (self._voted_for is None)
            and (message.last_log_term >= self._log[-1].got_at_term)
            and (
                message.last_log_term != self._log[-1].got_at_term
                or message.last_log_index >= self._log.last_index()
            )
        ):
            logger.info("voted for '%s'", message.candidate_id)
            self._voted_for = message.candidate_id
            await self._schedule_election.plan()

        return RequestVoteResponse(term=self._current_term, vote_granted=True)

    async def dispatch_request_vote_response(self, server_id: ServerId, response: RequestVoteResponse) -> None:
        logger.log(TRACE_INT, "received RequestVote repsonse from '%s'", server_id)
        await self._update_term(response.term)
        if self.state != State.CANDIDATE:
            return logger.debug(
                "discarded RequestVote repsonse from '%s', as current state is '%s'", server_id, self.state.name,
            )

        if response.vote_granted:
            self._current_votes += 1
            if (len(self._messengers) + 1) / 2 < self._current_votes:
                logger.info("there are enough votes to become a leader")
                self.state = State.LEADER
                await self._schedule_election.cancel()
                self._current_leader = self._server_id
                for messenger in self._messengers:
                    self._next_index[messenger._server_id] = len(self._log)
                    self._match_index[messenger._server_id] = 0
                await self._heartbeat_callback()

    async def _heartbeat_callback(self) -> None:
        logger.debug("entered heartbeat callback")
        tasks = []
        for messenger in self._messengers:
            server_id = messenger._server_id
            prev_log_index = self._next_index[messenger._server_id] - 1
            entries = [self._log[self._next_index[server_id]]] if len(self._log) > self._next_index[server_id] else []
            message = self._append_entries_message(prev_log_index, entries)
            logger.log(TRACE_INT, "sending heartbeat to '%s'", server_id)
            tasks.append(asyncio.ensure_future(self._with_timeout(messenger.send_append_entries(message))))
        _ = asyncio.gather(*tasks, return_exceptions=True)
        await self._schedule_heartbeat.plan()

    async def _election_callback(self) -> None:
        logger.debug("entered election callback")
        self.state = State.CANDIDATE
        logger.info("current term was '%s'; moving to '%s'", self._current_term, self._current_term + 1)
        self._current_term += 1
        self._current_votes = 1
        self._voted_for = self._server_id
        self._current_leader = None
        tasks = []
        message = self._request_vote_message()
        for messenger in self._messengers:
            logger.log(TRACE_INT, "sending vote request to '%s'", messenger._server_id)
            tasks.append(asyncio.ensure_future(self._with_timeout(messenger.send_request_vote(message))))
        _ = asyncio.gather(*tasks, return_exceptions=True)
        await self._schedule_election.plan()

    def add_entry(self, command: Any) -> ServerId | None:
        if self.state != State.LEADER:
            logger.warning("rejected a command as current state is '%s'", self.state.name)
            return self._current_leader

        self._log.append(LogEntry.model_validate({"command": command, "got_at_term": self._current_term}))
        return None
