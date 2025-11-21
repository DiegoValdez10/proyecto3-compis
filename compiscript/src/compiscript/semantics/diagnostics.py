from dataclasses import dataclass

@dataclass
class Diagnostic:
    code: str
    message: str
    line: int
    column: int
    level: str = "error"

class DiagBag:
    def __init__(self):
        self.items = []

    def err(self, code: str, message: str, token):
        line = getattr(token, "line", -1)
        col = getattr(token, "column", -1)
        self.items.append(Diagnostic(code, message, line, col, "error"))

    def warn(self, code: str, message: str, token):
        line = getattr(token, "line", -1)
        col = getattr(token, "column", -1)
        self.items.append(Diagnostic(code, message, line, col, "warning"))

    def ok(self):
        return all(d.level != "error" for d in self.items)

    def __iter__(self):
        return iter(self.items)
