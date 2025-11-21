from tests._utils import run, has, count

def test_dead_after_return_warning_inside_function():
    code = """
    function f(): integer {
        return 1;
        let x = 2;      // dead
        const y: integer = 3; // dead
    }
    """
    diags = run(code, "_tmp_dead_return.comp")
    assert count(diags, "DC01") >= 2

def test_dead_after_break_in_loop():
    code = """
    while (true) {
        break;
        let x = 1;  // dead
    }
    """
    diags = run(code, "_tmp_dead_break.comp")
    assert count(diags, "DC01") >= 1

def test_dead_after_continue_in_loop():
    code = """
    while (true) {
        continue;
        let x = 1;  # dead
    }
    """
    diags = run(code, "_tmp_dead_continue.comp")
    assert count(diags, "DC01") >= 1
