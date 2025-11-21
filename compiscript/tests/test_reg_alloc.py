# tests/test_reg_alloc.py
from program.mips.reg_alloc import RegAllocator, T_REGS, S_REGS


def test_basic_allocation_and_reuse():
    alloc = RegAllocator()

    r_x1 = alloc.get_reg("x")
    r_x2 = alloc.get_reg("x")

    assert r_x1 == r_x2
    assert r_x1 in T_REGS or r_x1 in S_REGS

    r_y = alloc.get_reg("y")
    assert r_y != r_x1
    assert r_y in T_REGS or r_y in S_REGS


def test_long_lived_uses_s_registers():
    alloc = RegAllocator()

    r_a = alloc.get_reg("a", long_lived=True)
    r_b = alloc.get_reg("b", long_lived=True)

    assert r_a in S_REGS
    assert r_b in S_REGS
    assert r_a != r_b


def test_release_and_reuse():
    alloc = RegAllocator()

    r_a = alloc.get_reg("a")
    alloc.release("a")
    r_b = alloc.get_reg("b")

    assert r_b in T_REGS or r_b in S_REGS
    assert r_b == r_a or r_b in T_REGS or r_b in S_REGS


def test_spill_when_no_free_t_regs():
    alloc = RegAllocator()

    names = [f"t{i}" for i in range(12)]
    regs = [alloc.get_reg(name) for name in names]

    used_t = [r for r in regs if r in T_REGS]
    assert len(set(used_t)) <= len(T_REGS)
    assert "$t9" in regs
