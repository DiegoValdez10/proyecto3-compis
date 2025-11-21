# tests/test_mips_stack_layout.py
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



def test_stack_layout_and_frame_size():
    """
    Día 5: revisamos que el frame de stack sea consistente y que
    los locales se mapeen a offsets concretos en la pila.
    """
    source = _sample_tac_source()
    tree = parse_tac_text(source)
    tac_program = build_tac_program(tree)
    asm = generate_mips(tac_program)

    lines = [l.rstrip() for l in asm.splitlines()]

    # Líneas con mapeo de locales
    local_lines = [l.strip() for l in lines if l.strip().startswith("# local ")]
    assert any("PI" in l for l in local_lines)
    assert any("greeting" in l for l in local_lines)
    assert any("flag" in l for l in local_lines)

    # Prologue: addi $sp, $sp, -N
    prologue = next(
        l.strip() for l in lines if l.strip().startswith("addi $sp, $sp, -")
    )
    # Epilogue: addi $sp, $sp, N
    epilogue = next(
        l.strip()
        for l in lines
        if l.strip().startswith("addi $sp, $sp, ")
        and not l.strip().startswith("addi $sp, $sp, -")
    )

    pro_size = int(prologue.split(",")[-1])
    epi_size = int(epilogue.split(",")[-1])

    # Deben ser inversos
    assert pro_size == -epi_size

    # Se guarda y restaura $ra
    assert any("sw $ra" in l for l in lines)
    assert any("lw $ra" in l for l in lines)

    # Debemos estar usando registros temporales ($t0, $t1, etc.)
    assert any("$t0" in l or "$t1" in l or "$t2" in l for l in lines)
