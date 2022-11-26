from typing import Optional, TypeVar

T = TypeVar("T")


def none_throws(val: Optional[T]) -> T:
    assert val is not None, "Unexpected null"
    return val
