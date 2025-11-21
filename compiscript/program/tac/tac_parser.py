from __future__ import annotations

from importlib import import_module
from typing import Tuple

from antlr4 import InputStream, FileStream, CommonTokenStream


def _load_lexer_parser() -> Tuple[type, type]:
    base_pkg = f"{__package__}.generated" if __package__ else "generated"
    lexer_mod = import_module(base_pkg + ".TacLexer")
    parser_mod = import_module(base_pkg + ".TacParser")
    return lexer_mod.TacLexer, parser_mod.TacParser


def parse_tac_text(source: str):
    TacLexer, TacParser = _load_lexer_parser()

    input_stream = InputStream(source)
    lexer = TacLexer(input_stream)
    token_stream = CommonTokenStream(lexer)
    parser = TacParser(token_stream)

    tree = parser.program()
    errors = parser.getNumberOfSyntaxErrors()
    assert errors == 0, f"Se encontraron {errors} errores de sintaxis al parsear TAC."
    return tree


def parse_tac_file(path: str):
    TacLexer, TacParser = _load_lexer_parser()

    input_stream = FileStream(path, encoding="utf-8")
    lexer = TacLexer(input_stream)
    token_stream = CommonTokenStream(lexer)
    parser = TacParser(token_stream)

    tree = parser.program()
    errors = parser.getNumberOfSyntaxErrors()
    assert errors == 0, f"Se encontraron {errors} errores de sintaxis al parsear TAC."
    return tree
