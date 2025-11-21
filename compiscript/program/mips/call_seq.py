# program/mips/call_seq.py
from __future__ import annotations

from typing import List


def emit_prologue(fn_name: str, frame_size: int) -> List[str]:
    lines: List[str] = []
    lines.append(f"{fn_name}:")
    lines.append(f"  addiu $sp, $sp, -{frame_size}")
    lines.append(f"  sw $ra, {frame_size - 4}($sp)")
    return lines


def emit_epilogue(frame_size: int) -> List[str]:
    lines: List[str] = []
    lines.append(f"  lw $ra, {frame_size - 4}($sp)")
    lines.append(f"  addiu $sp, $sp, {frame_size}")
    lines.append("  jr $ra")
    return lines


def emit_call(target: str) -> List[str]:
    return [f"  jal {target}"]
