from __future__ import annotations
from dataclasses import dataclass
from typing import TypeVar, Generic, Callable, Union
T = TypeVar("T")
U = TypeVar("U")
E = TypeVar("E")

@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T
    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

@dataclass(frozen=True)
class Err(Generic[E]):
    error: E
    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True

Result = Union[Ok[T], Err[E]]

def map_result(result: Result[T, E], fn: Callable[[T], U]) -> Result[U, E]:
    match result:
        case Ok(value):
            return Ok(fn(value))
        case Err():
            return result

def bind_result(result: Result[T, E], fn: Callable[[T], Result[U, E]]) -> Result[U, E]:
    match result:
        case Ok(value):
            return fn(value)
        case Err():
            return result