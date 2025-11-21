# program/tac/tac_printer.py
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


def _format_instruction(insn: TacInstruction) -> str:
    # x := valor
    if isinstance(insn, Assign):
        return f"{insn.dest} := {_format_value(insn.value)}"

    # x := array_new n
    if isinstance(insn, ArrayNew):
        return f"{insn.dest} := array_new {_format_value(insn.size)}"

    # array_store a, i, v
    if isinstance(insn, ArrayStore):
        return f"array_store {insn.array}, {_format_value(insn.index)}, {_format_value(insn.value)}"

    # branch cond, L1, L2
    if isinstance(insn, Branch):
        return f"branch {_format_value(insn.condition)}, {insn.true_label}, {insn.false_label}"

    # jump L
    if isinstance(insn, Jump):
        return f"jump {insn.target}"

    # print v
    if isinstance(insn, Print):
        return f"print {_format_value(insn.value)}"

    # return [v]
    if isinstance(insn, Return):
        if insn.value is None:
            return "return"
        return f"return {_format_value(insn.value)}"

    # Fallback (no debería aparecer en los tests)
    return f"# unsupported: {insn!r}"


def _format_function(fn: TacFunction) -> List[str]:
    lines: List[str] = []

    # Encabezado de la función
    header = f"function {fn.name}()"
    if fn.return_type:
        header += f" : {fn.return_type}"
    lines.append(header)

    # Bloques
    for i, block in enumerate(fn.blocks):
        lines.append(f"{block.label}:")
        for insn in block.instructions:
            lines.append("  " + _format_instruction(insn))
        # Línea en blanco entre bloques (opcional, pero amigable para el parser)
        if i != len(fn.blocks) - 1:
            lines.append("")

    return lines


def format_program(program: TacProgram) -> str:
    """
    Convierte un TacProgram en texto TAC.

    Este texto debe ser parseable de nuevo por parse_tac_text, para que
    el test de Día 3 (roundtrip) pase.
    """
    lines: List[str] = []

    # Recorremos las funciones en el orden de inserción
    for i, fn in enumerate(program.functions.values()):
        if i != 0:
            lines.append("")  # línea en blanco entre funciones
        lines.extend(_format_function(fn))

    # Agregamos un último newline por estética
    return "\n".join(lines) + "\n"
