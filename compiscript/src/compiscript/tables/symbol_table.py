from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from ..intermediate.temp_allocator import TemporaryAllocator, TempValue


@dataclass
class SymEntry:
    name: str
    value: Any
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemorySlot:
    """Represents the runtime location of a symbol inside an activation record."""

    name: str
    role: str
    offset: int
    size: int = 1
    type_hint: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "offset": self.offset,
            "size": self.size,
            "type": self.type_hint,
            "attributes": dict(self.attributes),
        }


@dataclass
class ActivationRecord:
    """Metadata describing a runtime activation (stack frame)."""

    name: str
    level: int
    parent: Optional["ActivationRecord"] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    slots: Dict[str, MemorySlot] = field(default_factory=dict)
    temporaries: Dict[str, MemorySlot] = field(default_factory=dict)
    order: List[str] = field(default_factory=list)
    temp_allocator: TemporaryAllocator = field(default_factory=TemporaryAllocator)
    _next_offset: int = 0

    def reserve_slot(
        self,
        name: str,
        *,
        role: str,
        size: int = 1,
        type_hint: Optional[str] = None,
        **attributes: Any,
    ) -> MemorySlot:
        slot = MemorySlot(
            name=name,
            role=role,
            offset=self._next_offset,
            size=size,
            type_hint=type_hint,
            attributes=attributes,
        )
        self.slots[name] = slot
        self.order.append(name)
        self._next_offset += size
        return slot

    def allocate_temp(self, *, type_hint: Optional[str] = None, lifespan: str = "block") -> tuple[MemorySlot, TempValue]:
        temp = self.temp_allocator.acquire(type_hint=type_hint, lifespan=lifespan)
        slot = MemorySlot(
            name=temp.name,
            role="temp",
            offset=self._next_offset,
            size=1,
            type_hint=type_hint,
            attributes={"lifespan": lifespan, "temp_index": temp.index},
        )
        self.temporaries[temp.name] = slot
        self._next_offset += 1
        return slot, temp

    def release_temp(self, name: str | TempValue) -> Optional[MemorySlot]:
        key = name if isinstance(name, str) else name.name
        slot = self.temporaries.pop(key, None)
        if slot:
            self.temp_allocator.release(key)
        return slot

    def get_slot(self, name: str) -> Optional[MemorySlot]:
        if name in self.slots:
            return self.slots[name]
        if name in self.temporaries:
            return self.temporaries[name]
        return self.parent.get_slot(name) if self.parent else None

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "level": self.level,
            "metadata": dict(self.metadata),
            "slots": {name: slot.to_dict() for name, slot in self.slots.items()},
            "temporaries": {name: slot.to_dict() for name, slot in self.temporaries.items()},
        }


class SymbolTable:
    def __init__(self, logger=None):
        self.scopes: List[Dict[str, SymEntry]] = [dict()]
        self.logger = logger
        self.activation_stack: List[ActivationRecord] = []
        self.scope_activation: List[Optional[ActivationRecord]] = [None]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _log(self, tag: str, msg: str):
        if self.logger and hasattr(self.logger, "log"):
            try:
                self.logger.log(tag, msg)
            except Exception:
                pass

    def _new_activation(self, name: str, metadata: Optional[Dict[str, Any]] = None) -> ActivationRecord:
        parent = self.activation_stack[-1] if self.activation_stack else None
        record = ActivationRecord(
            name=name,
            level=len(self.activation_stack) + 1,
            parent=parent,
            metadata=metadata or {},
        )
        return record

    # ------------------------------------------------------------------
    # Scope management
    # ------------------------------------------------------------------
    def push(self, activation_name: Optional[str] = None, **activation_meta: Any):
        self.scopes.append({})
        record: Optional[ActivationRecord] = None
        if activation_name:
            record = self._new_activation(activation_name, activation_meta)
            self.activation_stack.append(record)
            self._log("step", f"Ámbito: push + activación '{activation_name}' (niveles = {len(self.scopes)})")
        else:
            self._log("step", f"Ámbito: push (niveles = {len(self.scopes)})")
        self.scope_activation.append(record)

    def pop(self):
        if len(self.scopes) > 1:
            self.scopes.pop()
            record = self.scope_activation.pop()
            if record is not None and self.activation_stack:
                self.activation_stack.pop()
                self._log("step", f"Ámbito: pop + activación '{record.name}' (niveles = {len(self.scopes)})")
            else:
                self._log("step", f"Ámbito: pop (niveles = {len(self.scopes)})")

    # ------------------------------------------------------------------
    # Symbol management
    # ------------------------------------------------------------------
    def define(self, symbol) -> bool:
        scope = self.scopes[-1]
        if symbol.name in scope:
            self._log("err", f"TS.define: redeclaración '{symbol.name}' en el mismo ámbito")
            return False
        scope[symbol.name] = SymEntry(name=symbol.name, value=symbol, meta={})
        self._log("ok", f"TS.define: insertado '{symbol.name}'")
        return True

    def resolve(self, name: str) -> Optional[Any]:
        for i in range(len(self.scopes) - 1, -1, -1):
            scope = self.scopes[i]
            if name in scope:
                self._log("info", f"TS.resolve: '{name}' encontrado (nivel {i + 1}/{len(self.scopes)})")
                return scope[name].value
        self._log("err", f"TS.resolve: '{name}' no encontrado")
        return None

    def update(self, name: str, **meta):
        for i in range(len(self.scopes) - 1, -1, -1):
            scope = self.scopes[i]
            if name in scope:
                scope[name].meta.update(meta)
                self._log("ok", f"TS.update: '{name}' meta={meta}")
                return True
        self._log("err", f"TS.update: '{name}' no encontrado")
        return False

    def snapshot(self) -> List[Dict[str, SymEntry]]:
        snap: List[Dict[str, SymEntry]] = []
        for scope in self.scopes:
            snap.append({k: SymEntry(v.name, v.value, dict(v.meta)) for k, v in scope.items()})
        return snap

    # ------------------------------------------------------------------
    # Runtime metadata helpers
    # ------------------------------------------------------------------
    def current_activation(self) -> Optional[ActivationRecord]:
        return self.activation_stack[-1] if self.activation_stack else None

    def bind_slot(self, name: str, slot: MemorySlot) -> bool:
        for scope in reversed(self.scopes):
            if name in scope:
                scope[name].meta.setdefault("runtime", {})["slot"] = slot.to_dict()
                return True
        return False

    def get_slot(self, name: str) -> Optional[MemorySlot]:
        for record in reversed(self.activation_stack):
            slot = record.get_slot(name)
            if slot:
                return slot
        return None

    def reserve_slot(
        self,
        name: str,
        *,
        role: str,
        size: int = 1,
        type_hint: Optional[str] = None,
        **attributes: Any,
    ) -> MemorySlot:
        activation = self.current_activation()
        if activation is None:
            raise RuntimeError("No hay activación actual para reservar slots")
        slot = activation.reserve_slot(name, role=role, size=size, type_hint=type_hint, **attributes)
        self.bind_slot(name, slot)
        return slot

    def allocate_temp(self, *, type_hint: Optional[str] = None, lifespan: str = "block") -> tuple[MemorySlot, TempValue]:
        activation = self.current_activation()
        if activation is None:
            raise RuntimeError("No hay activación actual para temporales")
        return activation.allocate_temp(type_hint=type_hint, lifespan=lifespan)

    def release_temp(self, name: str | TempValue) -> Optional[MemorySlot]:
        activation = self.current_activation()
        if activation is None:
            return None
        return activation.release_temp(name)

    def describe_activations(self) -> List[Dict[str, Any]]:
        return [record.describe() for record in self.activation_stack]

    def iter_symbols(self) -> Iterable[SymEntry]:
        for scope in self.scopes:
            for entry in scope.values():
                yield entry