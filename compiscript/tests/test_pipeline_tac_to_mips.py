# tests/test_pipeline_tac_to_mips.py
import textwrap

from program.mips.pipeline import tac_source_to_mips


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

          t1 := PI < 400
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


def test_pipeline_tac_to_mips_basic():
    source = _sample_tac_source()
    mips = tac_source_to_mips(source)

    assert isinstance(mips, str)
    assert ".text" in mips
    assert "main:" in mips
    assert "main_entry:" in mips
    assert "if_true_1:" in mips
    assert "if_false_2:" in mips
    assert "end_3:" in mips

    assert "addiu $sp" in mips
    assert "sw $ra" in mips
    assert "lw $ra" in mips
    assert "jr $ra" in mips
