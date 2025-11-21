# tests/test_mips_basic.py
import textwrap

from program.tac.tac_parser import parse_tac_text
from program.tac.tac_builder import build_tac_program
from program.mips.generator import generate_mips


def _sample_tac_source() -> str:
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



def test_generate_basic_mips_from_tac():
    """
    Día 4: validar que podemos generar un MIPS básico desde TAC.

    Verificamos:
      - Sección .text
      - Función main
      - Labels de bloques
      - Prologue/epilogue con stack y $ra
      - Branch + jump
      - Comentarios de print / arrays
    """
    source = _sample_tac_source()

    tree = parse_tac_text(source)
    tac_program = build_tac_program(tree)
    asm = generate_mips(tac_program)

    # Estructura general
    assert ".text" in asm
    assert "main:" in asm

    # Labels de bloques
    assert "main_entry:" in asm
    assert "if_true_1:" in asm
    assert "if_false_2:" in asm
    assert "end_3:" in asm

    # Prologue / epilogue
    assert "addi $sp, $sp, -" in asm
    assert "sw $ra" in asm
    assert "lw $ra" in asm
    assert "jr $ra" in asm

    # Branch + saltos
    assert "beq" in asm
    assert "j if_true_1" in asm or "j  if_true_1" in asm

    # Comentarios de print y arrays
    assert "# print" in asm
    assert "# array_new" in asm
    assert "# array_store" in asm
