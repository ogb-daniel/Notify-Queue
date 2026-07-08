from __future__ import annotations
from dataclasses import dataclass
from typing import TypeVar, Generic, Union
T = TypeVar("T")
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