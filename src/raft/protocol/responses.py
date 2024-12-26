__all__ = (
    "AppendEntriesResponse",
    "RequestVoteResponse",
)

from pydantic import BaseModel


class AppendEntriesResponse(BaseModel):
    term: int
    success: bool


class RequestVoteResponse(BaseModel):
    term: int
    vote_granted: bool
