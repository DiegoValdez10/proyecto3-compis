# tests/test_ide_service.py
import textwrap

from program.ide.service import CompileService, CompileResult


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


def test_compile_service_basic_flow():
    svc = CompileService()
    source = _sample_tac_source()

    result = svc.compile(source)

    assert isinstance(result, CompileResult)
    assert result.tac_source.strip().startswith("function main")
    assert ".text" in result.mips_source
    assert "main:" in result.mips_source

    assert svc.last_result is result


def test_compile_service_overwrites_last_result():
    svc = CompileService()

    source1 = _sample_tac_source()
    result1 = svc.compile(source1)

    source2 = source1.replace("314", "200")
    result2 = svc.compile(source2)

    assert svc.last_result is result2
    assert result1 is not result2
    assert "200" in result2.tac_source
