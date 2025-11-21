# tests/test_tac_roundtrip.py
import textwrap

from program.tac.tac_parser import parse_tac_text
from program.tac.tac_builder import build_tac_program
from program.tac.tac_printer import format_program
from program.tac.tac_model import TacProgram


def _sample_tac_source() -> str:
    """
    Mismo programa que en el Día 2 / Día 1, pero lo usamos para
    probar el roundtrip completo.
    """
    return textwrap.dedent(
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


def test_tac_roundtrip_parse_build_print():
    """
    Día 3: validamos que podemos hacer roundtrip:

      texto TAC -> parse_tac_text -> TacProgram (TacBuilder)
      -> format_program -> texto TAC normalizado -> parse_tac_text

    El segundo parse no debe dar errores de sintaxis (parse_tac_text
    ya hace un assert interno de que errors == 0).
    """

    original_source = _sample_tac_source()

    # 1) Parseamos el original a parse tree
    tree = parse_tac_text(original_source)

    # 2) Construimos el modelo TacProgram
    program = build_tac_program(tree)
    assert isinstance(program, TacProgram)

    # 3) Lo convertimos de vuelta a texto TAC "bonito" / normalizado
    pretty_source = format_program(program)
    assert isinstance(pretty_source, str)
    assert "function main" in pretty_source

    # 4) Volvemos a parsear el texto generado
    #    Si hay errores de sintaxis, parse_tac_text lanzará AssertionError.
    tree2 = parse_tac_text(pretty_source)
    assert tree2 is not None
