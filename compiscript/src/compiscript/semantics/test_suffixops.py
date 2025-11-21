from tests._utils import run, has

def test_index_must_be_integer():
    code = "let arr: integer[] = [1,2]; let v = arr[true];"
    diags = run(code, "_tmp_idx_int.comp")
    assert not diags.ok()
    assert has(diags, "SX01")

def test_index_target_must_be_array():
    code = "let a: integer = 1; let v = a[0];"
    diags = run(code, "_tmp_idx_target.comp")
    assert not diags.ok()
    assert has(diags, "SX02")

def test_property_access_on_non_object():
    code = "let a: integer = 1; let x = a.len;"
    diags = run(code, "_tmp_prop_nonobj.comp")
    assert not diags.ok()
    assert has(diags, "SX03")
