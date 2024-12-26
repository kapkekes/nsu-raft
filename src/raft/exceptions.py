__all__ = (
    "RaftException",
    "UninitializedMessengerError",
    "AlreadyWorkingResponderError",
)

class RaftException(Exception):
    """Base exception class for `simple-raft` library."""


class UninitializedMessengerError(RaftException):
    """This `Messenger` hasn't been started yet."""

    def __init__(self) -> None:
        super().__init__("messenger hasn't been started")


class AlreadyWorkingResponderError(RaftException):
    """This `Responder` is already working."""

    def __init__(self) -> None:
        super().__init__("cannot start responder twice in a row")
