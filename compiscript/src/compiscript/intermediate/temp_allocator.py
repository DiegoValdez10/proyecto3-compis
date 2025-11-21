from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class TempValue:
    """Descriptor for a temporary value produced during code generation."""

    name: str
    index: int
    type_hint: Optional[str] = None
    lifespan: str = "block"

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "index": self.index,
            "type": self.type_hint,
            "lifespan": self.lifespan,
        }


class TemporaryAllocator:
    """Simple allocator that recycles temporary variable names."""

    def __init__(self, prefix: str = "t") -> None:
        self.prefix = prefix
        self._counter = 0
        self._free: List[int] = []
        self._active: Dict[str, TempValue] = {}

    def acquire(self, *, type_hint: Optional[str] = None, lifespan: str = "block") -> TempValue:
        if self._free:
            index = self._free.pop()
        else:
            index = self._counter
            self._counter += 1
        name = f"{self.prefix}{index}"
        temp = TempValue(name=name, index=index, type_hint=type_hint, lifespan=lifespan)
        self._active[temp.name] = temp
        return temp

    def release(self, temp: TempValue | str) -> None:
        name = temp if isinstance(temp, str) else temp.name
        entry = self._active.pop(name, None)
        if entry is not None:
            self._free.append(entry.index)

    def reset(self) -> None:
        self._counter = 0
        self._free.clear()
        self._active.clear()

    def snapshot(self) -> Dict[str, object]:
        return {
            "prefix": self.prefix,
            "counter": self._counter,
            "free": list(self._free),
            "active": {name: value.to_dict() for name, value in self._active.items()},
        }