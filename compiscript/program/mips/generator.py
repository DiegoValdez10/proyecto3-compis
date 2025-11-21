# program/mips/generator.py
from __future__ import annotations

from typing import Dict, List, Set

from program.tac.tac_model import (
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
from .regalloc import RegisterAllocator


def _format_value(v: TacValue) -> str:
    return v.text


class MipsGenerator:
    """
    Toma un TacProgram y produce código MIPS como string.

    Simplificaciones:
      - Todo se guarda en stack, direccionado desde $sp.
      - Se guarda $ra en la pila.
      - No usamos $fp por ahora (puedes extenderlo después).
    """

    def __init__(self, program: TacProgram) -> None:
        self.program = program
        self.lines: List[str] = []
        self.regs = RegisterAllocator()
        self.var_offsets: Dict[str, int] = {}
        self.frame_size: int = 0

    # --------- Entrada principal ---------

    def generate(self) -> str:
        self.lines.append(".text")

        # Funciones en orden determinista
        for name in sorted(self.program.functions.keys()):
            fn = self.program.functions[name]
            self._generate_function(fn)

        return "\n".join(self.lines) + "\n"

    # --------- Por función ---------

    def _collect_locals(self, fn: TacFunction) -> Set[str]:
        """
        Colecta nombres de variables que aparecen como destinos de instrucciones.
        Por ahora ignoramos arrays como estructuras reales; solo nos interesa
        tener algún mapeo de 'dest'.
        """
        names: Set[str] = set()
        for block in fn.blocks:
            for ins in block.instructions:
                if isinstance(ins, Assign):
                    names.add(ins.dest)
                elif isinstance(ins, ArrayNew):
                    names.add(ins.dest)
                # Podrías extender aquí para otros tipos de instrucciones.
        return names

    def _allocate_frame(self, locals_: Set[str]) -> None:
        """
        Asigna offsets de pila para cada variable local.
        Layout súper simple:

           [0($sp)]     -> local 1
           [4($sp)]     -> local 2
           ...
           [N-4($sp)]   -> local k
           [N($sp)]     -> slot para $ra

        Donde N = 4 * len(locals).
        """
        self.var_offsets.clear()
        offset = 0
        for name in sorted(locals_):
            self.var_offsets[name] = offset
            offset += 4

        # Reservamos además 4 bytes para guardar $ra
        self.frame_size = offset + 4

    def _generate_function(self, fn: TacFunction) -> None:
        locals_ = self._collect_locals(fn)
        self._allocate_frame(locals_)

        self.lines.append("")
        self.lines.append(f"{fn.name}:")

        # ---- Prólogo ----
        self.lines.append("  # prologue")
        self.lines.append(f"  addi $sp, $sp, -{self.frame_size}")
        self.lines.append(f"  sw $ra, {self.frame_size - 4}($sp)")

        for name, off in self.var_offsets.items():
            self.lines.append(f"  # local {name} -> {off}($sp)")

        # ---- Cuerpo (bloques) ----
        for block in fn.blocks:
            if block.label:
                self.lines.append(f"{block.label}:")
            for ins in block.instructions:
                self._generate_instruction(ins)

    # --------- Helpers de valores ---------

    def _load_value(self, v: TacValue) -> str:
        """
        Carga un TacValue en un registro y retorna ese registro.
        """
        reg = self.regs.get()

        if v.kind == "int":
            self.lines.append(f"  li {reg}, {v.text}")
        elif v.kind == "var":
            if v.text not in self.var_offsets:
                # Variable no declarada como local; le damos un offset nuevo
                new_off = len(self.var_offsets) * 4
                self.var_offsets[v.text] = new_off
                self.lines.append(f"  # local {v.text} -> {new_off}($sp)")
            off = self.var_offsets[v.text]
            self.lines.append(f"  lw {reg}, {off}($sp)")
        elif v.kind == "bool":
            val = "1" if v.text == "true" else "0"
            self.lines.append(f"  li {reg}, {val}")
        elif v.kind == "null":
            self.lines.append(f"  li {reg}, 0")
        else:
            # string u otro tipo: por ahora lo tratamos como 0 (placeholder)
            self.lines.append(f"  li {reg}, 0")

        return reg

    def _store_var(self, name: str, reg: str) -> None:
        """
        Guarda el valor de 'reg' en la variable 'name' en stack.
        """
        if name not in self.var_offsets:
            new_off = len(self.var_offsets) * 4
            self.var_offsets[name] = new_off
            self.lines.append(f"  # local {name} -> {new_off}($sp)")
        off = self.var_offsets[name]
        self.lines.append(f"  sw {reg}, {off}($sp)")

    # --------- Instrucciones TAC -> MIPS ---------

    def _generate_instruction(self, ins: TacInstruction) -> None:
        # x := v
        if isinstance(ins, Assign):
            reg = self._load_value(ins.value)
            self._store_var(ins.dest, reg)
            self.regs.release(reg)
            return

        # x := array_new n  /  array_store ...
        if isinstance(ins, ArrayNew):
            self.lines.append(
                f"  # array_new {ins.dest}, size={_format_value(ins.size)}"
            )
            return

        if isinstance(ins, ArrayStore):
            self.lines.append(
                "  # array_store "
                f"{ins.array}, idx={_format_value(ins.index)}, "
                f"value={_format_value(ins.value)}"
            )
            return

        # branch cond, Ltrue, Lfalse
        if isinstance(ins, Branch):
            r = self._load_value(ins.condition)
            self.lines.append(f"  beq {r}, $zero, {ins.false_label}")
            self.lines.append(f"  j {ins.true_label}")
            self.regs.release(r)
            return

        # jump L
        if isinstance(ins, Jump):
            self.lines.append(f"  j {ins.target}")
            return

        # print v  -> lo dejamos como comentario
        if isinstance(ins, Print):
            self.lines.append(f"  # print {_format_value(ins.value)}")
            return

        # return [v]
        if isinstance(ins, Return):
            if ins.value is not None:
                r = self._load_value(ins.value)
                self.lines.append(f"  move $v0, {r}")
                self.regs.release(r)

            self.lines.append("  # epilogue")
            self.lines.append(f"  lw $ra, {self.frame_size - 4}($sp)")
            self.lines.append(f"  addi $sp, $sp, {self.frame_size}")
            self.lines.append("  jr $ra")
            return

        # Fallback
        self.lines.append(f"  # unsupported TAC: {ins}")

# API sencilla para usar en tests
def generate_mips(program: TacProgram) -> str:
    gen = MipsGenerator(program)
    return gen.generate()
