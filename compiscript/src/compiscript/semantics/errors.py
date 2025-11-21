from dataclasses import dataclass

@dataclass
class Diagnostic:
    kind: str
    message: str
    line: int = 0
    col: int = 0

    def __repr__(self):
        pos = f"{self.line}:{self.col}" if self.line or self.col else "-"
        return f"[{self.kind}] ({pos}) {self.message}"
