# program/mips/reg_alloc.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Set, List

T_REGS: List[str] = [f"$t{i}" for i in range(10)]
S_REGS: List[str] = [f"$s{i}" for i in range(8)]


@dataclass
class RegAllocator:
    temp_to_reg: Dict[str, str] = field(default_factory=dict)
    free_t: Set[str] = field(default_factory=lambda: set(T_REGS))
    free_s: Set[str] = field(default_factory=lambda: set(S_REGS))

    def get_reg(self, name: str, long_lived: bool = False) -> str:
        if name in self.temp_to_reg:
            return self.temp_to_reg[name]

        pool = self.free_s if long_lived else self.free_t
        if pool:
            reg = sorted(pool)[0]
            pool.remove(reg)
        else:
            reg = "$t9"

        self.temp_to_reg[name] = reg
        return reg

    def release(self, name: str) -> None:
        reg = self.temp_to_reg.pop(name, None)
        if reg is None:
            return
        if reg in T_REGS:
            self.free_t.add(reg)
        elif reg in S_REGS:
            self.free_s.add(reg)

    def clear(self) -> None:
        self.temp_to_reg.clear()
        self.free_t = set(T_REGS)
        self.free_s = set(S_REGS)
