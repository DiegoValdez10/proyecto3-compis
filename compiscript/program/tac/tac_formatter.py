# program/tac/tac_formatter.py
from __future__ import annotations

from typing import List

from .tac_model import (
    TacProgram,
    TacFunction,
    TacBlock,
    TacInstruction,
    TacValue,
    Assign,
    ArrayNew,
    ArrayStore,
    Branch,
    Jump,
    Print,
    Return,
)


def _format_value(v: TacValue) -> str:
    return v.text


def _format_instruction(ins: TacInstruction) -> str:
    # x := v
    if isinstance(ins, Assign):
        return f"{ins.dest} := {_format_value(ins.value)}"

    # x := array_new n
    if isinstance(ins, ArrayNew):
        return f"{ins.dest} := array_new {_format_value(ins.size)}"

    # array_store a, i, v
    if isinstance(ins, ArrayStore):
        return (
            f"array_store {ins.array}, "
            f"{_format_value(ins.index)}, "
            f"{_format_value(ins.value)}"
        )

    # branch cond, L1, L2
    if isinstance(ins, Branch):
        return (
            f"branch {_format_value(ins.condition)}, "
            f"{ins.true_label}, {ins.false_label}"
        )

    # jump L
    if isinstance(ins, Jump):
        return f"jump {ins.target}"

    # print v
    if isinstance(ins, Print):
        return f"print {_format_value(ins.value)}"

    # return [v]
    if isinstance(ins, Return):
        if ins.value is None:
            return "return"
        return f"return {_format_value(ins.value)}"


    return ""


def format_program(program: TacProgram) -> str:

    lines: List[str] = []

    for name in sorted(program.functions.keys()):
        fn: TacFunction = program.functions[name]

        ret_part = f" : {fn.return_type}" if fn.return_type else ""
        lines.append(f"function {fn.name}(){ret_part}")

        for block in fn.blocks:
            if block.label:
                lines.append(f"{block.label}:")
            for ins in block.instructions:
                line = _format_instruction(ins)
                if line:
                    lines.append("  " + line)
        lines.append("")


    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines) + "\n"
