# program/ide/service.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from program.mips.pipeline import tac_source_to_mips


@dataclass
class CompileResult:
    tac_source: str
    mips_source: str


class CompileService:
    def __init__(self) -> None:
        self._last_result: Optional[CompileResult] = None

    def compile(self, tac_source: str) -> CompileResult:
        mips = tac_source_to_mips(tac_source)
        result = CompileResult(tac_source=tac_source, mips_source=mips)
        self._last_result = result
        return result

    @property
    def last_result(self) -> Optional[CompileResult]:
        return self._last_result
