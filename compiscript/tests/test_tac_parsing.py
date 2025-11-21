# tests/test_tac_parsing.py
from __future__ import annotations

import textwrap

from program.tac.tac_parser import parse_tac_text


def test_parse_simple_tac_program():
    """
    Día 1: validar que podemos parsear un TAC básico sin errores de sintaxis.

    Este programa cubre:
      - functionDecl
      - label
      - assignInstr
      - binaryInstr (lt, add)
      - arrayInstr (array_new, array_store)
      - branchInstr
      - jumpInstr
      - printInstr
      - returnInstr
    """
    source = textwrap.dedent(
        """
        function main() : void
        main_entry:
          PI := 314
          greeting := "Hello, Compiscript!"
          flag := true

          t0 := array_new 5
          array_store t0, 0, 1
          array_store t0, 1, 2

          t1 := lt PI, 400
          branch t1, if_true_1, if_false_2

        if_true_1:
          print "Less than 400"
          jump end_3

        if_false_2:
          print "Too big"
          jump end_3

        end_3:
          return
        """
    ).lstrip()

    tree = parse_tac_text(source)

    # Verificación mínima de estructura: hay al menos una función main
    funcs = tree.functionDecl()
    assert len(funcs) == 1

    main_fn = funcs[0]
    assert main_fn.Identifier().getText() == "main"

    # Tiene al menos un bloque (main_entry + if_true_1 + if_false_2 + end_3)
    blocks = main_fn.block()
    assert len(blocks) >= 1
    