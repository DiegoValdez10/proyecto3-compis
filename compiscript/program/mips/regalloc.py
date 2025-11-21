# program/mips/regalloc.py
from __future__ import annotations


class RegisterAllocator:
    """
    Asignador de registros súper sencillo.

    - Usa $t0..$t9 para valores temporales.
    - Si se quedan sin registros, reutiliza $t0 (naive).
    """

    def __init__(self) -> None:
        self._pool = [f"$t{i}" for i in range(10)]
        self._in_use = set()

    def get(self) -> str:
        if self._pool:
            reg = self._pool.pop(0)
            self._in_use.add(reg)
            return reg
        # Sin registros libres: reutilizamos $t0 como fallback.
        return "$t0"

    def release(self, reg: str) -> None:
        if reg in self._in_use:
            self._in_use.remove(reg)
            # Lo volvemos a poner al frente para ser reutilizado
            if reg not in self._pool:
                self._pool.insert(0, reg)
