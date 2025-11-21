# tests/test_mips_calls.py
from program.mips.call_seq import emit_prologue, emit_epilogue, emit_call


def test_prologue_and_epilogue_shape():
    frame_size = 16

    prologue = emit_prologue("foo", frame_size)
    epilogue = emit_epilogue(frame_size)

    text = "\n".join(prologue + epilogue)

    assert "foo:" in text
    assert f"addiu $sp, $sp, -{frame_size}" in text
    assert f"sw $ra, {frame_size - 4}($sp)" in text
    assert f"lw $ra, {frame_size - 4}($sp)" in text
    assert f"addiu $sp, $sp, {frame_size}" in text
    assert "jr $ra" in text


def test_call_emits_jal():
    lines = emit_call("bar")
    assert any("jal bar" in line for line in lines)
