from __future__ import annotations

import argparse
import sys

# Preferir los imports que ya tenías; si fallan (no hay paquete padre), usar absolutos.
try:
    from ..frontend.generated.program.CompiscriptLexer import CompiscriptLexer
    from ..frontend.generated.program.CompiscriptParser import CompiscriptParser
    from ..frontend import compat as _compat  # noqa: F401
    from ..intermediate.generator import IntermediateGenerator
except ImportError:
    from compiscript.frontend.generated.program.CompiscriptLexer import CompiscriptLexer
    from compiscript.frontend.generated.program.CompiscriptParser import CompiscriptParser
    from compiscript.frontend import compat as _compat  # noqa: F401
    from compiscript.intermediate.generator import IntermediateGenerator

from antlr4 import CommonTokenStream, FileStream, InputStream
from antlr4.error.ErrorListener import ErrorListener


class _ThrowingErrorListener(ErrorListener):
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        raise SyntaxError(f"Syntax error at {line}:{column}: {msg}")


def _parse_stream(stream):
    lexer = CompiscriptLexer(stream)
    tokens = CommonTokenStream(lexer)
    parser = CompiscriptParser(tokens)
    parser.removeErrorListeners()
    parser.addErrorListener(_ThrowingErrorListener())
    tree = parser.program()
    return tree


def _read_stream(path: str | None):
    if path and path != "-":
        return FileStream(path, encoding="utf-8")
    data = sys.stdin.read()
    return InputStream(data)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="compiscript", description="Compiscript CLI")
    ap.add_argument("file", nargs="?", help="Ruta al archivo .cps (o '-' para stdin)")
    ap.add_argument("--emit-ir", action="store_true", help="Emite código intermedio")
    args = ap.parse_args(argv)

    stream = _read_stream(args.file)
    tree = _parse_stream(stream)

    if not args.emit_ir:
        # Sólo parsea: si no explota, OK silencioso
        return 0

    gen = IntermediateGenerator()
    fn = gen.generate(tree)
    mod = gen.builder.module

    # Impresión legible del IR
    # Si tu IRModule o IRFunction tienen __str__, esto basta:
    try:
        print(str(mod))
        return 0
    except Exception:
        pass

    # Fallback a un volcado simple
    for fname, func in mod.functions.items():
        print(f"\nfunc {fname}():")
        for blk in func.blocks:
            print(f"  block {blk.label}:")
            for instr in blk.instructions:
                if instr.dest is not None:
                    print(f"    {instr.dest} = {instr.opcode} {', '.join(map(str, instr.args or []))}")
                else:
                    print(f"    {instr.opcode} {', '.join(map(str, instr.args or []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
