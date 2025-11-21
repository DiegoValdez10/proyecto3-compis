from dataclasses import dataclass

class Type:
    name: str = "type"

    def is_assignable_from(self, other: "Type") -> bool:
        return isinstance(other, type(self)) or isinstance(self, AnyType) or isinstance(other, AnyType)

    def __repr__(self):
        return self.name

class AnyType(Type):
    name = "any"

class ErrorType(Type):
    name = "error"

class IntType(Type):
    name = "integer"

class BoolType(Type):
    name = "boolean"

class StringType(Type):
    name = "string"

@dataclass(frozen=True)
class ArrayType(Type):
    elem: Type

    @property
    def name(self):
        return f"{self.elem.name}[]"

    def is_assignable_from(self, other: "Type") -> bool:
        if isinstance(self, AnyType) or isinstance(other, AnyType):
            return True
        if not isinstance(other, ArrayType):
            return False
        # permisivo con any: int[] <- any[] y any[] <- int[]
        if isinstance(self.elem, AnyType) or isinstance(other.elem, AnyType):
            return True
        return self.elem.is_assignable_from(other.elem)


ANY = AnyType()
ERR = ErrorType()
INT = IntType()
BOOL = BoolType()
STR = StringType()

def unify(a: Type, b: Type) -> Type:
    """Unifica tipos para literales y binarios (enfoque mínimo necesario hoy)."""
    if isinstance(a, ErrorType) or isinstance(b, ErrorType):
        return ERR
    if isinstance(a, AnyType):
        return b
    if isinstance(b, AnyType):
        return a
    # Arrays
    if isinstance(a, ArrayType) and isinstance(b, ArrayType):
        return ArrayType(unify(a.elem, b.elem))
    # Primitivos idénticos
    if type(a) is type(b):
        return a
    # Incompatibles
    return ERR
