from .ir import (
    Operand,
    Instruction,
    BasicBlock,
    IRFunction,
    IRModule,
)
from .builder import IRBuilder
from .temp_allocator import TemporaryAllocator, TempValue

__all__ = [
    "Operand",
    "Instruction",
    "BasicBlock",
    "IRFunction",
    "IRModule",
    "IRBuilder",
    "IntermediateGenerator",
    "TemporaryAllocator",
    "TempValue",
]


def __getattr__(name: str):
    if name == "IntermediateGenerator":
        from .generator import IntermediateGenerator

        return IntermediateGenerator
    raise AttributeError(name)