# tests/test_mips_backend_full.py

from program.backend.mips_backend_full import (
    CS_MipsBackend,
    IRFunction,
    BasicBlock,
    Instruction,
    Operand,
)


def _simple_activation(slots):
    """
    Helper para crear un activation con el formato que usa el backend:
    metadata['activation']['slots'][name] = { 'offset': int, 'size': 1, ... }
    """
    act_slots = {}
    for name, offset in slots.items():
        act_slots[name] = {
            "name": name,
            "role": "local",
            "offset": offset,
            "size": 1,
            "type": ":integer",
            "attributes": {},
            "const": False,
        }
    return {"name": "main", "level": 1, "metadata": {}, "slots": act_slots, "temporaries": {}}


def test_simple_assign_and_print_int():
    """
    Verifica que:
    - No explote al generar MIPS.
    - Aparece 'main:'.
    - Se emite un syscall de print_int.
    """

    # x := 42
    instr1 = Instruction(
        opcode="assign",
        dest=Operand(name="x", kind="identifier", type_hint=":integer"),
        args=[Operand(name="42", kind="immediate", type_hint="integer", value=42)],
        comment=None,
        metadata={},
    )

    # print x
    instr2 = Instruction(
        opcode="print",
        dest=None,
        args=[Operand(name="x", kind="identifier", type_hint=":integer")],
        comment=None,
        metadata={},
    )

    block = BasicBlock(label="main_entry", instructions=[instr1, instr2])

    activation = _simple_activation({"x": 0})

    func = IRFunction(
        name="main",
        params=[],
        return_type="void",
        blocks=[block],
        attributes={},
        locals={"x": {"slot": activation["slots"]["x"], "const": False, "type": None}},
        metadata={"activation": activation},
    )

    backend = CS_MipsBackend()
    mips = backend.generate_program([func])

    assert "main:" in mips
    assert "print_int" not in mips  # usamos li $v0, 1, no etiqueta
    assert "li   $v0, 1" in mips    # syscall print_int
    assert "syscall" in mips


def test_print_string_literal():
    """
    Verifica que un print con string literal:
    - Genere una etiqueta en .data
    - Use syscall 4
    """

    instr = Instruction(
        opcode="print",
        dest=None,
        args=[Operand(name="msg", kind="immediate", type_hint="string", value="Hello!")],
        comment=None,
        metadata={},
    )

    block = BasicBlock(label="main_entry", instructions=[instr])
    activation = _simple_activation({})
    func = IRFunction(
        name="main",
        params=[],
        return_type="void",
        blocks=[block],
        attributes={},
        locals={},
        metadata={"activation": activation},
    )

    backend = CS_MipsBackend()
    mips = backend.generate_program([func])

    # Debe aparecer una etiqueta str_0 en .data y syscall 4
    assert ".data" in mips
    assert 'str_0: .asciiz "Hello!' in mips or 'str_0: .asciiz "Hello!' in mips
    assert "li   $v0, 4" in mips
    assert "syscall" in mips


def test_branch_and_jump():
    """
    Pequeña prueba de control de flujo: branch + jump.
    """

    # t0 := 1
    instr1 = Instruction(
        opcode="assign",
        dest=Operand(name="t0", kind="identifier", type_hint=":integer"),
        args=[Operand(name="1", kind="immediate", type_hint="integer", value=1)],
        comment=None,
        metadata={},
    )

    # branch t0, L_true, L_false
    instr2 = Instruction(
        opcode="branch",
        dest=None,
        args=[
            Operand(name="t0", kind="identifier", type_hint=":integer"),
            Operand(name="L_true", kind="label", type_hint="label"),
            Operand(name="L_false", kind="label", type_hint="label"),
        ],
        comment=None,
        metadata={},
    )

    block_main = BasicBlock(label="main_entry", instructions=[instr1, instr2])

    # Bloques true/false vacíos para el test
    block_true = BasicBlock(label="L_true", instructions=[])
    block_false = BasicBlock(label="L_false", instructions=[])

    activation = _simple_activation({"t0": 0})
    func = IRFunction(
        name="main",
        params=[],
        return_type="void",
        blocks=[block_main, block_true, block_false],
        attributes={},
        locals={"t0": {"slot": activation["slots"]["t0"], "const": False, "type": None}},
        metadata={"activation": activation},
    )

    backend = CS_MipsBackend()
    mips = backend.generate_program([func])

    # Deberíamos ver "bnez" y saltos a L_true / L_false
    assert "bnez $t0, L_true" in mips
    assert "j    L_false" in mips


def test_array_new_and_store():
    """
    Verifica que se emite llamada a __cs_array_new y que el runtime está presente.
    """

    instr_new = Instruction(
        opcode="array_new",
        dest=Operand(name="arr", kind="identifier", type_hint=":integer[]"),
        args=[Operand(name="5", kind="immediate", type_hint="integer", value=5)],
        comment=None,
        metadata={},
    )

    instr_store = Instruction(
        opcode="array_store",
        dest=None,
        args=[
            Operand(name="arr", kind="identifier", type_hint=":integer[]"),
            Operand(name="0", kind="immediate", type_hint="integer", value=0),
            Operand(name="1", kind="immediate", type_hint="integer", value=1),
        ],
        comment=None,
        metadata={},
    )

    block = BasicBlock(label="main_entry", instructions=[instr_new, instr_store])
    activation = _simple_activation({"arr": 0})

    func = IRFunction(
        name="main",
        params=[],
        return_type="void",
        blocks=[block],
        attributes={},
        locals={"arr": {"slot": activation["slots"]["arr"], "const": False, "type": None}},
        metadata={"activation": activation},
    )

    backend = CS_MipsBackend()
    mips = backend.generate_program([func])

    # Debe llamar a __cs_array_new
    assert "jal  __cs_array_new" in mips
    # Y el runtime debe estar presente
    assert "__cs_array_new:" in mips
