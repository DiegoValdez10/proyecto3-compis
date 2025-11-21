from antlr4 import FileStream, InputStream, CommonTokenStream
from ..frontend.generated.program.CompiscriptLexer import CompiscriptLexer
from ..frontend.generated.program.CompiscriptParser import CompiscriptParser
from ..frontend import compat  # noqa: F401


def _build_parser_from_text(text: str) -> CompiscriptParser:
    input_stream = InputStream(text)
    lexer = CompiscriptLexer(input_stream)
    token_stream = CommonTokenStream(lexer)
    parser = CompiscriptParser(token_stream)
    return parser


def parse_text(text: str):
    parser = _build_parser_from_text(text)
    tree = parser.program()
    return tree, parser


def parse_file(path: str):
    fs = FileStream(path, encoding="utf-8")
    lexer = CompiscriptLexer(fs)
    token_stream = CommonTokenStream(lexer)
    parser = CompiscriptParser(token_stream)
    tree = parser.program()
    return tree, parser

def parse(path: str):
    tree, _ = parse_file(path)
    return tree
