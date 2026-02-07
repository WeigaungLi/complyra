from __future__ import annotations

from contextvars import ContextVar, Token

REQUEST_ID_CONTEXT: ContextVar[str] = ContextVar("request_id", default="-")


def set_request_id(request_id: str) -> Token:
    return REQUEST_ID_CONTEXT.set(request_id)


def get_request_id() -> str:
    return REQUEST_ID_CONTEXT.get()


def reset_request_id(token: Token) -> None:
    REQUEST_ID_CONTEXT.reset(token)
