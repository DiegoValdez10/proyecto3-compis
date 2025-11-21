from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Value:
    kind: str
    text: str


@dataclass
class TacInstruction:
    pass


@dataclass
class Assign(TacInstruction):
    dest: str
    value: Value


@dataclass
class BinaryOp(TacInstruction):
    dest: str
    left: Value
    op: str
    right: Value


@dataclass
class UnaryOp(TacInstruction):
    dest: str
    op: str
    operand: Value


@dataclass
class ArrayNew(TacInstruction):
    dest: str
    size: Value


@dataclass
class ArrayStore(TacInstruction):
    array: str
    index: Value
    value: Value


@dataclass
class ArrayIndex(TacInstruction):
    dest: str
    array: str
    index: Value


@dataclass
class ArrayLength(TacInstruction):
    dest: str
    array: str


@dataclass
class FieldLoad(TacInstruction):
    dest: str
    object: str
    field: Value


@dataclass
class FieldStore(TacInstruction):
    object: str
    field: Value
    value: Value


@dataclass
class Call(TacInstruction):
    dest: Optional[str]
    function: str
    args: List[Value]


@dataclass
class Branch(TacInstruction):
    condition: Value
    true_label: str
    false_label: str


@dataclass
class Jump(TacInstruction):
    target: str


@dataclass
class Print(TacInstruction):
    value: Value


@dataclass
class Return(TacInstruction):
    value: Optional[Value] = None


@dataclass
class BeginTry(TacInstruction):
    handler_label: str


@dataclass
class EndTry(TacInstruction):
    pass


@dataclass
class BeginCatch(TacInstruction):
    dest: Optional[str] = None


@dataclass
class EndCatch(TacInstruction):
    pass


@dataclass
class TacBlock:
    label: str
    instructions: List[TacInstruction] = field(default_factory=list)


@dataclass
class TacFunction:
    name: str
    params: List[str]
    return_type: Optional[str]
    blocks: List[TacBlock] = field(default_factory=list)


@dataclass
class TacProgram:
    functions: Dict[str, TacFunction] = field(default_factory=dict)