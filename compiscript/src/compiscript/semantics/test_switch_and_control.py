from tests._utils import run, has

def test_switch_expr_must_be_boolean():
    code = "switch (1) { default: }"
    diags = run(code, "_tmp_switch_bool.comp")
    assert not diags.ok()
    assert has(diags, "CF05")

def test_if_while_for_do_require_boolean():
    code = """
    if (1) {}
    while (1) {}
    do {} while (1);
    for (; 1; ) {}
    """
    diags = run(code, "_tmp_cf_bool.comp")
    assert not diags.ok()
    assert has(diags, "CF01")
    assert has(diags, "CF02")
    assert has(diags, "CF03")
    assert has(diags, "CF04")

def test_break_continue_outside_loop():
    code = "break; continue;"
    diags = run(code, "_tmp_break_continue.comp")
    assert not diags.ok()
    assert has(diags, "CF10")
    assert has(diags, "CF11")
