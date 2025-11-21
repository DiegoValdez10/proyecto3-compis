from __future__ import annotations

from program.tac.tac_builder import parse_tac_text, build_tac_program
from program.mips.backend import MipsBackend


def tac_source_to_mips(source: str) -> str:
    tree = parse_tac_text(source)
    tac_program = build_tac_program(tree)
    backend = MipsBackend()
    return backend.emit_program(tac_program)
