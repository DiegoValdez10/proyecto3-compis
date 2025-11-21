from tests._utils import run, has

def test_call_non_function_identifier_error():
    code = """
    let f: integer = 10;
    let x = f(1);
    """
    diags = run(code, "_tmp_call_nonfunc.comp")
    assert not diags.ok()
    assert has(diags, "FN10")

def test_method_call_ok_and_arg_checks():
    code = """
    class A {
        function sum(a: integer, b: integer): integer { return a + b; }
    }
    let o = new A();
    let x: integer = o.sum(1, 2);
    """
    diags = run(code, "_tmp_method_call_ok.comp")
    assert diags.ok()

def test_method_call_arity_mismatch():
    code = """
    class A {
        function sum(a: integer, b: integer): integer { return a + b; }
    }
    let o = new A();
    let x = o.sum(1);
    """
    diags = run(code, "_tmp_method_call_arity.comp")
    assert not diags.ok()
    assert has(diags, "FN11")

def test_method_call_type_mismatch():
    code = """
    class A {
        function sum(a: integer, b: integer): integer { return a + b; }
    }
    let o = new A();
    let x = o.sum(1, true);
    """
    diags = run(code, "_tmp_method_call_typemismatch.comp")
    assert not diags.ok()
    assert has(diags, "FN12")
