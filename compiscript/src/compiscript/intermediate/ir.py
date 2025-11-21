from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class Operand:
    name: str
    kind: str = "value"
    type_hint: Optional[str] = None
    value: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "name": self.name,
            "kind": self.kind,
        }
        if self.type_hint is not None:
            data["type"] = self.type_hint
        if self.value is not None:
            data["value"] = self.value
        return data


@dataclass
class Instruction:
    opcode: str
    dest: Optional[Operand] = None
    args: List[Operand] = field(default_factory=list)
    comment: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "opcode": self.opcode,
            "args": [arg.to_dict() for arg in self.args],
        }
        if self.dest is not None:
            data["dest"] = self.dest.to_dict()
        if self.comment:
            data["comment"] = self.comment
        if self.metadata:
            data["meta"] = dict(self.metadata)
        return data


@dataclass
class BasicBlock:

    label: str
    instructions: List[Instruction] = field(default_factory=list)

    def emit(self, instruction: Instruction) -> Instruction:
        self.instructions.append(instruction)
        return instruction

    def extend(self, instructions: Iterable[Instruction]) -> None:
        for instr in instructions:
            self.emit(instr)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "instructions": [instr.to_dict() for instr in self.instructions],
        }


@dataclass
class IRFunction:

    name: str
    params: List[str]
    return_type: Optional[str]
    blocks: List[BasicBlock] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    locals: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def append_block(self, label: str) -> BasicBlock:
        block = BasicBlock(label=label)
        self.blocks.append(block)
        return block

    def current_block(self) -> Optional[BasicBlock]:
        return self.blocks[-1] if self.blocks else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "params": list(self.params),
            "return": self.return_type,
            "blocks": [block.to_dict() for block in self.blocks],
            "locals": {name: dict(info) for name, info in self.locals.items()},
            "attributes": dict(self.attributes),
            "meta": dict(self.metadata),
        }


@dataclass
class IRModule:

    functions: Dict[str, IRFunction] = field(default_factory=dict)
    globals: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    string_pool: Dict[str, str] = field(default_factory=dict)
    entrypoint: Optional[str] = None

    def add_function(
        self,
        name: str,
        params: Optional[List[str]] = None,
        return_type: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> IRFunction:
        func = IRFunction(
            name=name,
            params=params or [],
            return_type=return_type,
            attributes=attributes or {},
        )
        self.functions[name] = func
        if self.entrypoint is None:
            self.entrypoint = name
        return func

    def get_function(self, name: str) -> Optional[IRFunction]:
        return self.functions.get(name)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "functions": {name: func.to_dict() for name, func in self.functions.items()},
            "globals": {name: dict(info) for name, info in self.globals.items()},
            "string_pool": dict(self.string_pool),
            "entrypoint": self.entrypoint,
        }