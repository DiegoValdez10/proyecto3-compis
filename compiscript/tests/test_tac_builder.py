# tests/test_tac_builder.py
import textwrap

from program.tac.tac_parser import parse_tac_text
from program.tac.tac_builder import build_tac_program
from program.tac.tac_model import TacProgram, TacFunction, TacBlock


def _sample_tac_source() -> str:
    """
    Programa TAC básico para probar el builder.

    Nota: usamos la misma sintaxis que en el Día 1:
      t1 := lt PI, 400
    en lugar de 't1 := PI < 400', porque la gramática actual
    reconoce 'lt' como operador binario.
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


def test_build_tac_model_from_simple_program():
    """
    Día 2: validar que podemos construir un modelo en memoria (TacProgram)
    a partir del parse tree del TAC.

    Este test NO entra a detalles de generación de MIPS todavía; solo
    comprueba que:

      - Se crea un TacProgram.
      - Contiene una función 'main'.
      - La función 'main' tiene bloques con labels esperados.
      - Dentro de los bloques hay instrucciones de tipos clave:
        asignaciones, array_new, array_store, branch, jump, print, return.
    """

    source = _sample_tac_source()

    # 1) Parseamos el texto TAC a un parse tree de ANTLR
    tree = parse_tac_text(source)

    # 2) Construimos el modelo de alto nivel (TacProgram)
    program = build_tac_program(tree)

    # --- Validaciones de estructura general ---
    assert isinstance(program, TacProgram)

    # Debe existir la función 'main'
    assert "main" in program.functions

    main_fn = program.functions["main"]
    assert isinstance(main_fn, TacFunction)
    assert main_fn.name == "main"

    # La función debe tener al menos un bloque
    assert len(main_fn.blocks) > 0
    assert all(isinstance(b, TacBlock) for b in main_fn.blocks)

    # Labels esperados
    labels = {b.label for b in main_fn.blocks}
    assert "main_entry" in labels
    assert "if_true_1" in labels
    assert "if_false_2" in labels
    assert "end_3" in labels

    # --- Revisión liviana de instrucciones ---
    all_insns = [ins for b in main_fn.blocks for ins in b.instructions]

    # Por tipo de instrucción (usamos el nombre de la clase para no acoplarnos de más)
    insn_types = {type(i).__name__ for i in all_insns}

    # Debe haber al menos una asignación
    assert any("Assign" in t for t in insn_types)

    # Debe haber operaciones con arreglos
    assert any("ArrayNew" in t for t in insn_types)
    assert any("ArrayStore" in t for t in insn_types)

    # Debe haber un branch
    assert any("Branch" in t for t in insn_types)

    # Debe haber saltos incondicionales
    assert any("Jump" in t for t in insn_types)

    # Debe haber impresiones
    assert any("Print" in t for t in insn_types)

    # Y un return al final de la función
    last_block = main_fn.blocks[-1]
    assert len(last_block.instructions) > 0
    last_insn = last_block.instructions[-1]
    assert "Return" in type(last_insn).__name__
