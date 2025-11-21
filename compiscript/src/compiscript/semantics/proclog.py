
from __future__ import annotations
from typing import Callable, Optional

Sink = Callable[[str, str], None]

class ProcLog:
    def __init__(self, sink: Optional[Sink] = None):
        self.sink: Sink = sink or (lambda msg, tag="info": print(f"[{tag.upper()}] {msg}"))
    def step(self, msg: str): self.sink(msg, "step")
    def info(self, msg: str): self.sink(msg, "info")
    def ok(self, msg: str):   self.sink(msg, "ok")
    def err(self, msg: str):  self.sink(msg, "err")
