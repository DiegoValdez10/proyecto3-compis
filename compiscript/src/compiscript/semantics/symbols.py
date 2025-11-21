from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Union, Dict, List, Tuple

try:
    from .typesys import Type
except Exception:
    Type = object


@dataclass
class Symbol:
    name: str


@dataclass
class VarSymbol(Symbol):
    type: Optional["Type"] = None
    is_const: bool = False


@dataclass
class FuncSymbol(Symbol):
    params: List[Tuple[str, Optional["Type"]]] = field(default_factory=list)
    return_type: Optional["Type"] = None


class ClassSymbol(Symbol):
    def __init__(self, name: str):
        super().__init__(name)
        self._members: Dict[str, Union[VarSymbol, FuncSymbol]] = {}

    def define_member(self, sym: Union[VarSymbol, FuncSymbol]) -> bool:
        if sym.name in self._members:
            return False
        self._members[sym.name] = sym
        return True

    def get_member(self, name: str) -> Optional[Union[VarSymbol, FuncSymbol]]:
        return self._members.get(name)

    @property
    def members(self) -> Dict[str, Union[VarSymbol, FuncSymbol]]:
        return self._members.copy()
