# program/tac/tac_driver.py
import sys
from antlr4 import FileStream, CommonTokenStream
from TacLexer import TacLexer
from TacParser import TacParser
from antlr4.tree.Tree import TerminalNode

def main(path: str):
    input_stream = FileStream(path, encoding="utf-8")
    lexer = TacLexer(input_stream)
    tokens = CommonTokenStream(lexer)
    parser = TacParser(tokens)
    tree = parser.program()

    # recorrido rápido: imprimir líneas “normalizadas” de instrucciones
    for f in tree.children or []:
        if f.getChild(0).getText() == "function":
            fname = f.Identifier(0).getText()
            print(f"[function] {fname}")
            for i in range(f.getChildCount()):
                node = f.getChild(i)
                if hasattr(node, "label") and node.label():
                    print(f"[label] {node.label().getText()}")
                if hasattr(node, "instruction"):
                    # block can have many instruction() nodes
                    for ins in node.instruction():
                        line = " ".join(tok.getText() for tok in ins.children if not isinstance(tok, TerminalNode) or tok.getText().strip())
                        print(f"  {line}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python tac_driver.py path/to/file.tac")
        sys.exit(1)
    main(sys.argv[1])
