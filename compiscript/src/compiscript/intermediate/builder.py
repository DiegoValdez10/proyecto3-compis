from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Optional

from .ir import BasicBlock, IRFunction, IRModule, Instruction, Operand
from .temp_allocator import TemporaryAllocator, TempValue


@dataclass
class BuilderState:
    function: Optional[IRFunction] = None
    block: Optional[BasicBlock] = None


class IRBuilder:

    def __init__(
        self,
        module: Optional[IRModule] = None,
        temp_allocator: Optional[TemporaryAllocator] = None,
    ) -> None:
        self.module = module or IRModule()
        self.temps = temp_allocator or TemporaryAllocator()
        self.state = BuilderState()
    def literal(self, value: Any, type_hint: Optional[str] = None) -> Operand:
        return Operand(name=str(value), kind="immediate", type_hint=type_hint, value=value)

    def identifier(self, name: str, type_hint: Optional[str] = None) -> Operand:
        return Operand(name=name, kind="identifier", type_hint=type_hint)

    def temporary(self, *, type_hint: Optional[str] = None, lifespan: str = "block") -> Operand:
        temp = self.temps.acquire(type_hint=type_hint, lifespan=lifespan)
        return Operand(name=temp.name, kind="temp", type_hint=type_hint)

    def release_temp(self, operand: Operand | TempValue | str) -> None:
        if isinstance(operand, Operand):
            self.temps.release(operand.name)
        else:
            self.temps.release(operand)
    def start_function(
        self,
        name: str,
        *,
        params: Optional[List[str]] = None,
        return_type: Optional[str] = None,
        attributes: Optional[dict] = None,
    ) -> IRFunction:
        func = self.module.add_function(name, params=params or [], return_type=return_type, attributes=attributes)
        self.state.function = func
        self.state.block = func.append_block(f"{name}_entry")
        return func

    def end_function(self) -> Optional[IRFunction]:
        func = self.state.function
        self.state = BuilderState()
        return func

    def new_block(self, label: str) -> BasicBlock:
        if not self.state.function:
            raise RuntimeError("Cannot create a block without an active function")
        block = self.state.function.append_block(label)
        self.state.block = block
        return block

    def position_at_end(self, block: BasicBlock) -> None:
        self.state.block = block
    def emit(self, opcode: str, *, dest: Optional[Operand] = None, args: Optional[Iterable[Operand]] = None,
             comment: Optional[str] = None, metadata: Optional[dict] = None) -> Instruction:
        if not self.state.block:
            raise RuntimeError("No active basic block to append instructions to")
        instruction = Instruction(
            opcode=opcode,
            dest=dest,
            args=list(args) if args else [],
            comment=comment,
            metadata=metadata or {},
        )
        self.state.block.emit(instruction)
        return instruction

    def emit_assign(self, target: Operand, value: Operand, *, comment: Optional[str] = None) -> Instruction:
        return self.emit("assign", dest=target, args=[value], comment=comment)

    def emit_binary(
        self,
        opcode: str,
        left: Operand,
        right: Operand,
        *,
        dest: Optional[Operand] = None,
        type_hint: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> Operand:
        if dest is None:
            dest = self.temporary(type_hint=type_hint)
        self.emit(opcode, dest=dest, args=[left, right], comment=comment)
        return dest

    def emit_unary(
        self,
        opcode: str,
        operand: Operand,
        *,
        dest: Optional[Operand] = None,
        type_hint: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> Operand:
        if dest is None:
            dest = self.temporary(type_hint=type_hint)
        self.emit(opcode, dest=dest, args=[operand], comment=comment)
        return dest

    def emit_call(
        self,
        callee: Operand,
        arguments: Iterable[Operand],
        *,
        dest: Optional[Operand] = None,
        type_hint: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> Operand:
        if dest is None:
            dest = self.temporary(type_hint=type_hint, lifespan="call")
        self.emit("call", dest=dest, args=[callee, *arguments], comment=comment)
        return dest

    def emit_jump(self, target: str, *, comment: Optional[str] = None) -> Instruction:
        return self.emit("jump", args=[self.identifier(target, type_hint="label")], comment=comment)

    def emit_branch(
        self,
        condition: Operand,
        true_label: str,
        false_label: str,
        *,
        comment: Optional[str] = None,
    ) -> Instruction:
        return self.emit(
            "branch",
            args=[
                condition,
                self.identifier(true_label, type_hint="label"),
                self.identifier(false_label, type_hint="label"),
            ],
            comment=comment,
        )

    def emit_return(self, value: Optional[Operand] = None, *, comment: Optional[str] = None) -> Instruction:
        args: List[Operand] = [value] if value else []
        return self.emit("return", args=args, comment=comment)