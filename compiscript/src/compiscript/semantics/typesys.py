from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
@dataclass(frozen=True)
class Type:

    name: str

    def __repr__(self) -> str:
        return self.name


class ArrayType(Type):
    def __init__(self, elem: Type):
        object.__setattr__(self, "elem", elem)
        base = repr(elem)
        if not base.endswith("]") and " " not in base and base.isidentifier() is False:
            pass
        name = f"{base}[]"
        super().__init__(name)

    def __repr__(self) -> str:
        return f"{repr(self.elem)}[]"
Integer = Type("integer")
String = Type("string")
Boolean = Type("boolean")
Null = Type("null")

def is_array(t: Optional[Type]) -> bool:
    return isinstance(t, ArrayType)


def elem_type(t: Optional[Type]) -> Optional[Type]:
    return t.elem if isinstance(t, ArrayType) else None


def is_numeric(t: Optional[Type]) -> bool:
    return t is Integer


def same(a: Optional[Type], b: Optional[Type]) -> bool:
    if a is b:
        return True
    if a is None or b is None:
        return a is b
    if isinstance(a, ArrayType) and isinstance(b, ArrayType):
        return same(a.elem, b.elem)
    return a.name == b.name


def from_type_name(name: str) -> Optional[Type]:

    lname = name.lower()
    if lname == "integer":
        return Integer
    if lname == "string":
        return String
    if lname == "boolean":
        return Boolean
    if lname == "null":
        return Null
    return Type(name)


def from_type_rule(type_ctx) -> Optional[Type]:
    if type_ctx is None:
        return None

    text = type_ctx.getText()
    dims = 0
    while text.endswith("[]"):
        dims += 1
        text = text[:-2]

    base = from_type_name(text)
    t = base
    for _ in range(dims):
        t = ArrayType(t)
    return t
