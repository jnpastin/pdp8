"""
Unit tests for PDP-8 Calculator — Layer 1: AC/Link Core Engine

Covers all operations with edge cases from the design specification.
Run with:  python -m unittest discover -s tests
"""

import unittest
from pdp8_core import (
    AC_MASK, MachineState,
    op_load, op_add, op_sub, op_i, op_cia,
    op_cla, op_cma, op_set,
    op_cll, op_cml, op_stl,
    op_and, op_or, op_xor,
    op_ral, op_rar,
    to_signed, to_unsigned, to_octal, to_binary_triads,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

AC_MAX = 0o7777   # 4095
AC_MID = 0o4000   # 2048 — also the sign bit for 12-bit two's complement


# ---------------------------------------------------------------------------
# LOAD
# ---------------------------------------------------------------------------

class TestLoad(unittest.TestCase):
    def test_load_zero(self):
        assert op_load(MachineState(0o1234, 1), 0) == MachineState(0, 1)

    def test_load_max(self):
        assert op_load(MachineState(0, 0), AC_MAX) == MachineState(AC_MAX, 0)

    def test_load_masks_to_12_bits(self):
        assert op_load(MachineState(0, 0), 0o10001) == MachineState(0o0001, 0)

    def test_load_does_not_change_link(self):
        s = op_load(MachineState(0, 1), 42)
        assert s.link == 1


# ---------------------------------------------------------------------------
# ADD
# ---------------------------------------------------------------------------

class TestAdd(unittest.TestCase):
    def test_simple_add(self):
        s = op_add(MachineState(0o0001, 0), 0o0002)
        assert s.ac == 0o0003
        assert s.link == 0

    def test_add_no_carry_link_unchanged(self):
        s = op_add(MachineState(0o0001, 1), 0o0001)
        assert s.ac == 0o0002
        assert s.link == 1  # unchanged — no carry

    def test_add_carry_toggles_link_0_to_1(self):
        s = op_add(MachineState(0o7777, 0), 1)
        assert s.ac == 0o0000
        assert s.link == 1

    def test_add_carry_toggles_link_1_to_0(self):
        s = op_add(MachineState(0o7777, 1), 1)
        assert s.ac == 0o0000
        assert s.link == 0

    def test_add_wrap_result(self):
        # Confirmed spec example: 7777 + 0001 → AC=0000, Link toggled
        s = op_add(MachineState(0o7777, 0), 0o0001)
        assert s.ac == 0o0000
        assert s.link == 1

    def test_add_zero(self):
        s = op_add(MachineState(0o1234, 0), 0)
        assert s.ac == 0o1234
        assert s.link == 0


# ---------------------------------------------------------------------------
# SUB
# ---------------------------------------------------------------------------

class TestSub(unittest.TestCase):
    def test_sub_same_value_gives_zero(self):
        s = op_sub(MachineState(0o0005, 0), 0o0005)
        assert s.ac == 0o0000

    def test_sub_1_from_1(self):
        # CIA(1) = 7777; 0001 + 7777 = 10000 → AC=0000, carry → link toggled
        s = op_sub(MachineState(0o0001, 0), 0o0001)
        assert s.ac == 0o0000
        assert s.link == 1

    def test_sub_result(self):
        s = op_sub(MachineState(0o0010, 0), 0o0003)
        assert s.ac == 0o0005

    def test_sub_underflow_wraps(self):
        # 0 - 1: CIA(1)=7777; 0+7777=7777, no carry at bit 12
        s = op_sub(MachineState(0o0000, 0), 0o0001)
        assert s.ac == 0o7777
        assert s.link == 0

    def test_sub_zero_arg_is_identity(self):
        # SUB(0): CIA(0) is used as a *mathematical value* (0), not a state op.
        # Differs from real PDP-8 where CIA(0) as an OPR would toggle Link.
        # Design choice: CIA(operand) in SUB is a pure numeric transform.
        s = op_sub(MachineState(0o1234, 1), 0)
        assert s.ac == 0o1234
        assert s.link == 1  # link NOT toggled (no carry; CIA-as-math gives 0)


# ---------------------------------------------------------------------------
# I (Increment)
# ---------------------------------------------------------------------------

class TestIncrement(unittest.TestCase):
    def test_increment_basic(self):
        s = op_i(MachineState(0o0001, 0))
        assert s.ac == 0o0002
        assert s.link == 0

    def test_increment_wrap(self):
        s = op_i(MachineState(0o7777, 0))
        assert s.ac == 0o0000
        assert s.link == 1

    def test_increment_toggles_link_back(self):
        s = op_i(MachineState(0o7777, 1))
        assert s.ac == 0o0000
        assert s.link == 0


# ---------------------------------------------------------------------------
# CIA
# ---------------------------------------------------------------------------

class TestCIA(unittest.TestCase):
    def test_cia_identity_zero(self):
        # CIA(0) = 0; ~0 = 7777, 7777+1 = 10000 → carry toggles link
        s = op_cia(MachineState(0o0000, 0))
        assert s.ac == 0o0000
        assert s.link == 1  # carry out of bit 11

    def test_cia_identity_zero_link_already_set(self):
        # CIA(0) with L=1: carry toggles link back to 0
        s = op_cia(MachineState(0o0000, 1))
        assert s.ac == 0o0000
        assert s.link == 0

    def test_cia_0001_gives_7777(self):
        s = op_cia(MachineState(0o0001, 0))
        assert s.ac == 0o7777

    def test_cia_7777_gives_0001(self):
        s = op_cia(MachineState(0o7777, 0))
        assert s.ac == 0o0001

    def test_cia_involution(self):
        # CIA(CIA(n)) == n
        for n in (0, 1, 0o1234, 0o4000, 0o7777):
            s = op_cia(MachineState(n, 0))
            s2 = op_cia(MachineState(s.ac, 0))
            assert s2.ac == n, f"CIA(CIA({oct(n)})) != {oct(n)}"

    def test_cia_does_not_change_link(self):
        s = op_cia(MachineState(0o0001, 1))
        assert s.link == 1


# ---------------------------------------------------------------------------
# CLA
# ---------------------------------------------------------------------------

class TestCLA(unittest.TestCase):
    def test_cla_clears_ac(self):
        s = op_cla(MachineState(0o7777, 0))
        assert s.ac == 0

    def test_cla_leaves_link(self):
        s = op_cla(MachineState(0o7777, 1))
        assert s.link == 1


# ---------------------------------------------------------------------------
# CMA
# ---------------------------------------------------------------------------

class TestCMA(unittest.TestCase):
    def test_cma_all_ones_gives_zero(self):
        s = op_cma(MachineState(0o7777, 0))
        assert s.ac == 0o0000

    def test_cma_zero_gives_all_ones(self):
        s = op_cma(MachineState(0o0000, 0))
        assert s.ac == 0o7777

    def test_cma_involution(self):
        for n in (0, 1, 0o1234, 0o7777):
            s = op_cma(MachineState(n, 0))
            s2 = op_cma(MachineState(s.ac, 0))
            assert s2.ac == n

    def test_cma_leaves_link(self):
        s = op_cma(MachineState(0o1234, 1))
        assert s.link == 1


# ---------------------------------------------------------------------------
# SET
# ---------------------------------------------------------------------------

class TestSet(unittest.TestCase):
    def test_set_gives_7777(self):
        s = op_set(MachineState(0, 0))
        assert s.ac == 0o7777

    def test_set_leaves_link(self):
        s = op_set(MachineState(0, 1))
        assert s.link == 1


# ---------------------------------------------------------------------------
# CLL
# ---------------------------------------------------------------------------

class TestCLL(unittest.TestCase):
    def test_cll_clears_link(self):
        s = op_cll(MachineState(0o1234, 1))
        assert s.link == 0

    def test_cll_leaves_ac(self):
        s = op_cll(MachineState(0o1234, 1))
        assert s.ac == 0o1234

    def test_cll_already_zero(self):
        s = op_cll(MachineState(0, 0))
        assert s.link == 0


# ---------------------------------------------------------------------------
# CML
# ---------------------------------------------------------------------------

class TestCML(unittest.TestCase):
    def test_cml_0_to_1(self):
        s = op_cml(MachineState(0, 0))
        assert s.link == 1

    def test_cml_1_to_0(self):
        s = op_cml(MachineState(0, 1))
        assert s.link == 0

    def test_cml_leaves_ac(self):
        s = op_cml(MachineState(0o5432, 0))
        assert s.ac == 0o5432


# ---------------------------------------------------------------------------
# STL
# ---------------------------------------------------------------------------

class TestSTL(unittest.TestCase):
    def test_stl_sets_link(self):
        s = op_stl(MachineState(0, 0))
        assert s.link == 1

    def test_stl_already_one(self):
        s = op_stl(MachineState(0, 1))
        assert s.link == 1

    def test_stl_leaves_ac(self):
        s = op_stl(MachineState(0o1234, 0))
        assert s.ac == 0o1234


# ---------------------------------------------------------------------------
# AND
# ---------------------------------------------------------------------------

class TestAND(unittest.TestCase):
    def test_and_basic(self):
        s = op_and(MachineState(0o7777, 0), 0o0707)
        assert s.ac == 0o0707

    def test_and_with_zero(self):
        s = op_and(MachineState(0o7777, 0), 0)
        assert s.ac == 0

    def test_and_all_ones(self):
        s = op_and(MachineState(0o7777, 0), 0o7777)
        assert s.ac == 0o7777

    def test_and_leaves_link(self):
        s = op_and(MachineState(0o7777, 1), 0o0000)
        assert s.link == 1


# ---------------------------------------------------------------------------
# OR
# ---------------------------------------------------------------------------

class TestOR(unittest.TestCase):
    def test_or_basic(self):
        s = op_or(MachineState(0o0000, 0), 0o1234)
        assert s.ac == 0o1234

    def test_or_all_ones_stays_all_ones(self):
        s = op_or(MachineState(0o7777, 0), 0o0000)
        assert s.ac == 0o7777

    def test_or_leaves_link(self):
        s = op_or(MachineState(0, 1), 0)
        assert s.link == 1


# ---------------------------------------------------------------------------
# XOR
# ---------------------------------------------------------------------------

class TestXOR(unittest.TestCase):
    def test_xor_with_all_ones_is_cma(self):
        s = op_xor(MachineState(0o3456, 0), 0o7777)
        assert s.ac == (~0o3456) & AC_MASK

    def test_xor_with_self_is_zero(self):
        s = op_xor(MachineState(0o5555, 0), 0o5555)
        assert s.ac == 0

    def test_xor_leaves_link(self):
        s = op_xor(MachineState(0, 1), 0o7777)
        assert s.link == 1


# ---------------------------------------------------------------------------
# RAL (Rotate Left through Link)
# ---------------------------------------------------------------------------

class TestRAL(unittest.TestCase):
    def test_ral_link_0_ac_0(self):
        s = op_ral(MachineState(0, 0))
        assert s.ac == 0
        assert s.link == 0

    def test_ral_link_1_shifts_into_bit_0(self):
        # L=1, AC=0000 → L shifts into bit-0; new L gets old bit-11=0
        s = op_ral(MachineState(0o0000, 1))
        assert s.ac == 0o0001
        assert s.link == 0

    def test_ral_ac_bit11_shifts_into_link(self):
        # L=0, AC=4000 (bit 11 set) → L becomes 1, AC becomes 0000
        s = op_ral(MachineState(0o4000, 0))
        assert s.ac == 0o0000
        assert s.link == 1

    def test_ral_full_rotation(self):
        # 13 RALs → back to original
        orig = MachineState(0o1234, 1)
        s = orig
        for _ in range(13):
            s = op_ral(s)
        assert s == orig

    def test_ral_all_ones(self):
        # L=1, AC=7777 → all bits 1, rotation leaves it unchanged
        s = op_ral(MachineState(0o7777, 1))
        assert s.ac == 0o7777
        assert s.link == 1


# ---------------------------------------------------------------------------
# RAR (Rotate Right through Link)
# ---------------------------------------------------------------------------

class TestRAR(unittest.TestCase):
    def test_rar_link_0_ac_0(self):
        s = op_rar(MachineState(0, 0))
        assert s.ac == 0
        assert s.link == 0

    def test_rar_ac_bit0_shifts_into_link(self):
        # L=0, AC=0001 → bit-0 → link=1, AC becomes 0000
        s = op_rar(MachineState(0o0001, 0))
        assert s.ac == 0o0000
        assert s.link == 1

    def test_rar_link_1_shifts_into_bit11(self):
        # L=1, AC=0000 → L into bit-11: AC=4000, link=0
        s = op_rar(MachineState(0o0000, 1))
        assert s.ac == 0o4000
        assert s.link == 0

    def test_rar_full_rotation(self):
        # 13 RARs → back to original
        orig = MachineState(0o5670, 0)
        s = orig
        for _ in range(13):
            s = op_rar(s)
        assert s == orig

    def test_ral_rar_inverses(self):
        # RAR(RAL(state)) == state
        for ac_init, link_init in [(0o1234, 0), (0o7777, 1), (0, 0), (0o4000, 1)]:
            s = MachineState(ac_init, link_init)
            assert op_rar(op_ral(s)) == s


# ---------------------------------------------------------------------------
# Numeric interpretation helpers
# ---------------------------------------------------------------------------

class TestInterpretation(unittest.TestCase):
    def test_signed_negative(self):
        assert to_signed(0o7777) == -1

    def test_signed_most_negative(self):
        assert to_signed(0o4000) == -2048

    def test_signed_most_positive(self):
        assert to_signed(0o3777) == 2047

    def test_signed_zero(self):
        assert to_signed(0) == 0

    def test_unsigned_max(self):
        assert to_unsigned(0o7777) == 4095

    def test_unsigned_zero(self):
        assert to_unsigned(0) == 0

    def test_octal_formatting(self):
        assert to_octal(0o7777) == "7777"
        assert to_octal(0o0001) == "0001"
        assert to_octal(0) == "0000"

    def test_binary_triads_all_ones(self):
        assert to_binary_triads(0o7777) == "111 111 111 111"

    def test_binary_triads_all_zeros(self):
        assert to_binary_triads(0) == "000 000 000 000"

    def test_binary_triads_pattern(self):
        # 0o5252 = 101 010 101 010
        assert to_binary_triads(0o5252) == "101 010 101 010"
