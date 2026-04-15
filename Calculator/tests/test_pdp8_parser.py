"""
Tests for Layer 2: pdp8_parser — Command Parsing & Dispatch

Test categories:
  TestParseNumber       — numeric parsing across all bases and modes
  TestModeCommands      — BASE and MODE session commands
  TestNoArgCommands     — I, CIA, CLA, CMA, SET, CLL, CML, STL, RAL, RAR
  TestArgCommands       — LOAD, ADD, SUB, AND, OR, XOR
  TestAliases           — +, -, &, |, ^ symbolic aliases
  TestLastString        — LAST field formatting and propagation
  TestInputNormalization — case, whitespace, empty lines
  TestErrorHandling     — unknown commands, wrong arity, bad numbers
  TestSessionImmutability — errors never modify session
"""

import unittest
from pdp8_core import MachineState
from pdp8_parser import SessionState, dispatch, parse_number


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def s(**kwargs):
    """Build a SessionState starting from defaults, overriding named fields."""
    return SessionState(**{**SessionState()._asdict(), **kwargs})


def ok(line, session=None):
    """dispatch a line; assert no error and return the new session."""
    if session is None:
        session = SessionState()
    new_s, err = dispatch(line, session)
    assert err is None, f"Unexpected error: {err}"
    return new_s


def err(line, session=None):
    """dispatch a line; assert an error occurred and return the error string."""
    if session is None:
        session = SessionState()
    _, e = dispatch(line, session)
    assert e is not None, "Expected an error but got none"
    return e


# ---------------------------------------------------------------------------
# TestParseNumber
# ---------------------------------------------------------------------------

class TestParseNumber(unittest.TestCase):

    # --- DEC / SIGNED ---

    def test_dec_signed_positive(self):
        v, e = parse_number("42", "DEC", "SIGNED")
        assert e is None and v == 42

    def test_dec_signed_zero(self):
        v, e = parse_number("0", "DEC", "SIGNED")
        assert e is None and v == 0

    def test_dec_signed_max_positive(self):
        v, e = parse_number("2047", "DEC", "SIGNED")
        assert e is None and v == 2047

    def test_dec_signed_negative_minus1(self):
        # -1 → 4095 (0o7777)
        v, e = parse_number("-1", "DEC", "SIGNED")
        assert e is None and v == 4095

    def test_dec_signed_negative_min(self):
        # -2048 → 2048 (0o4000)
        v, e = parse_number("-2048", "DEC", "SIGNED")
        assert e is None and v == 2048

    def test_dec_signed_wraps_over_4095(self):
        # 4096 → 0 (masks to 12 bits)
        v, e = parse_number("4096", "DEC", "SIGNED")
        assert e is None and v == 0

    def test_dec_signed_wraps_negative_overflow(self):
        # -2049 wraps: -2049 & 0xFFF = 2047
        v, e = parse_number("-2049", "DEC", "SIGNED")
        assert e is None and v == 2047

    def test_dec_signed_invalid(self):
        v, e = parse_number("abc", "DEC", "SIGNED")
        assert e is not None

    # --- DEC / UNSIGNED ---

    def test_dec_unsigned_positive(self):
        v, e = parse_number("4095", "DEC", "UNSIGNED")
        assert e is None and v == 4095

    def test_dec_unsigned_zero(self):
        v, e = parse_number("0", "DEC", "UNSIGNED")
        assert e is None and v == 0

    def test_dec_unsigned_wraps(self):
        v, e = parse_number("4096", "DEC", "UNSIGNED")
        assert e is None and v == 0

    def test_dec_unsigned_rejects_negative(self):
        v, e = parse_number("-1", "DEC", "UNSIGNED")
        assert e is not None

    def test_dec_unsigned_invalid(self):
        v, e = parse_number("xyz", "DEC", "UNSIGNED")
        assert e is not None

    # --- OCT ---

    def test_oct_valid(self):
        v, e = parse_number("7777", "OCT", "SIGNED")
        assert e is None and v == 0o7777

    def test_oct_zero(self):
        v, e = parse_number("0", "OCT", "SIGNED")
        assert e is None and v == 0

    def test_oct_wraps(self):
        # 10000 octal = 4096, masks to 0
        v, e = parse_number("10000", "OCT", "SIGNED")
        assert e is None and v == 0

    def test_oct_rejects_negative_prefix(self):
        v, e = parse_number("-17", "OCT", "SIGNED")
        assert e is not None

    def test_oct_rejects_positive_prefix(self):
        v, e = parse_number("+17", "OCT", "SIGNED")
        assert e is not None

    def test_oct_invalid_digit(self):
        v, e = parse_number("89", "OCT", "SIGNED")
        assert e is not None

    def test_oct_letters_invalid(self):
        v, e = parse_number("abc", "OCT", "SIGNED")
        assert e is not None

    # --- BIN ---

    def test_bin_valid(self):
        v, e = parse_number("111111111111", "BIN", "SIGNED")
        assert e is None and v == 0o7777

    def test_bin_zero(self):
        v, e = parse_number("0", "BIN", "SIGNED")
        assert e is None and v == 0

    def test_bin_wraps(self):
        # 13 ones = 8191; masked to 12 bits = 4095
        v, e = parse_number("1111111111111", "BIN", "SIGNED")
        assert e is None and v == 4095

    def test_bin_rejects_negative_prefix(self):
        v, e = parse_number("-1", "BIN", "SIGNED")
        assert e is not None

    def test_bin_invalid_digit(self):
        v, e = parse_number("102", "BIN", "SIGNED")
        assert e is not None


# ---------------------------------------------------------------------------
# TestModeCommands
# ---------------------------------------------------------------------------

class TestModeCommands(unittest.TestCase):

    def test_base_dec(self):
        s0 = s(base="OCT")
        s1 = ok("base dec", s0)
        assert s1.base == "DEC"

    def test_base_oct(self):
        s1 = ok("base oct")
        assert s1.base == "OCT"

    def test_base_bin(self):
        s1 = ok("base bin")
        assert s1.base == "BIN"

    def test_base_uppercase_input(self):
        s1 = ok("BASE OCT")
        assert s1.base == "OCT"

    def test_base_does_not_change_last(self):
        s0 = s(last="CIA")
        s1 = ok("base oct", s0)
        assert s1.last == "CIA"

    def test_base_does_not_change_machine(self):
        m = MachineState(ac=42, link=1)
        s0 = s(machine=m)
        s1 = ok("base oct", s0)
        assert s1.machine == m

    def test_base_unknown(self):
        e = err("base hex")
        assert "hex" in e.lower() or "DEC" in e or "OCT" in e

    def test_base_missing_arg(self):
        e = err("base")
        assert e is not None

    def test_mode_signed(self):
        s0 = s(mode="UNSIGNED")
        s1 = ok("mode signed", s0)
        assert s1.mode == "SIGNED"

    def test_mode_unsigned(self):
        s1 = ok("mode unsigned")
        assert s1.mode == "UNSIGNED"

    def test_mode_does_not_change_last(self):
        s0 = s(last="ADD 5")
        s1 = ok("mode unsigned", s0)
        assert s1.last == "ADD 5"

    def test_mode_unknown(self):
        e = err("mode twos")
        assert e is not None

    def test_mode_missing_arg(self):
        e = err("mode")
        assert e is not None


# ---------------------------------------------------------------------------
# TestNoArgCommands
# ---------------------------------------------------------------------------

class TestNoArgCommands(unittest.TestCase):

    def test_i_increments(self):
        s0 = s(machine=MachineState(ac=1, link=0))
        s1 = ok("i", s0)
        assert s1.machine.ac == 2 and s1.machine.link == 0

    def test_i_wrap_and_link_toggle(self):
        s0 = s(machine=MachineState(ac=0o7777, link=0))
        s1 = ok("i", s0)
        assert s1.machine.ac == 0 and s1.machine.link == 1

    def test_i_last(self):
        s1 = ok("i")
        assert s1.last == "IAC"  # I is an alias; canonical is IAC

    def test_cia_basic(self):
        s0 = s(machine=MachineState(ac=1, link=0))
        s1 = ok("cia", s0)
        assert s1.machine.ac == 0o7777

    def test_cia_zero_identity(self):
        # CIA(0) = 0; carry out of bit 11 toggles link
        s0 = s(machine=MachineState(ac=0, link=0))
        s1 = ok("cia", s0)
        assert s1.machine.ac == 0 and s1.machine.link == 1

    def test_cia_zero_toggles_link_back(self):
        # CIA(0) with L=1 toggles back to 0
        s0 = s(machine=MachineState(ac=0, link=1))
        s1 = ok("cia", s0)
        assert s1.machine.ac == 0 and s1.machine.link == 0

    def test_cia_does_not_change_link(self):
        # AC != 0: no carry, link unchanged
        s0 = s(machine=MachineState(ac=5, link=1))
        s1 = ok("cia", s0)
        assert s1.machine.link == 1

    def test_cla(self):
        s0 = s(machine=MachineState(ac=0o7777, link=1))
        s1 = ok("cla", s0)
        assert s1.machine.ac == 0 and s1.machine.link == 1

    def test_cma(self):
        s0 = s(machine=MachineState(ac=0o7777, link=0))
        s1 = ok("cma", s0)
        assert s1.machine.ac == 0 and s1.machine.link == 0

    def test_set(self):
        s0 = s(machine=MachineState(ac=0, link=0))
        s1 = ok("set", s0)
        assert s1.machine.ac == 0o7777

    def test_cll(self):
        s0 = s(machine=MachineState(ac=10, link=1))
        s1 = ok("cll", s0)
        assert s1.machine.link == 0 and s1.machine.ac == 10

    def test_cml(self):
        s0 = s(machine=MachineState(ac=0, link=0))
        s1 = ok("cml", s0)
        assert s1.machine.link == 1

    def test_stl(self):
        s0 = s(machine=MachineState(ac=0, link=0))
        s1 = ok("stl", s0)
        assert s1.machine.link == 1

    def test_ral_rotates(self):
        # AC=1, L=0 → rotate left → AC=2, L=0
        s0 = s(machine=MachineState(ac=1, link=0))
        s1 = ok("ral", s0)
        assert s1.machine.ac == 2 and s1.machine.link == 0

    def test_ral_link_flows_into_ac_bit0(self):
        # AC=0, L=1 → rotate left → AC=1, L=0
        s0 = s(machine=MachineState(ac=0, link=1))
        s1 = ok("ral", s0)
        assert s1.machine.ac == 1 and s1.machine.link == 0

    def test_ral_ac_msb_flows_into_link(self):
        # AC=4000 octal (bit 11 set), L=0 → rotate left → AC=0, L=1
        s0 = s(machine=MachineState(ac=0o4000, link=0))
        s1 = ok("ral", s0)
        assert s1.machine.ac == 0 and s1.machine.link == 1

    def test_rar_rotates(self):
        # AC=2, L=0 → rotate right → AC=1, L=0
        s0 = s(machine=MachineState(ac=2, link=0))
        s1 = ok("rar", s0)
        assert s1.machine.ac == 1 and s1.machine.link == 0

    def test_rar_link_flows_into_ac_msb(self):
        # AC=0, L=1 → rotate right → AC=4000 octal, L=0
        s0 = s(machine=MachineState(ac=0, link=1))
        s1 = ok("rar", s0)
        assert s1.machine.ac == 0o4000 and s1.machine.link == 0

    def test_rar_ac_bit0_flows_into_link(self):
        # AC=1, L=0 → rotate right → AC=0, L=1
        s0 = s(machine=MachineState(ac=1, link=0))
        s1 = ok("rar", s0)
        assert s1.machine.ac == 0 and s1.machine.link == 1

    def test_noarg_rejects_extra_token(self):
        e = err("cla 5")
        assert "CLA" in e and "no argument" in e.lower()

    def test_all_noarg_commands_update_last(self):
        # Maps user input to expected last value (aliases resolve to canonical)
        cases = {
            "i": "IAC", "cia": "CIA", "cla": "CLA", "cma": "CMA", "set": "SET",
            "cll": "CLL", "cml": "CML", "stl": "STL", "ral": "RAL", "rar": "RAR",
        }
        for cmd, expected_last in cases.items():
            s1 = ok(cmd)
            assert s1.last == expected_last, f"LAST wrong for {cmd}: got {s1.last!r}"


# ---------------------------------------------------------------------------
# TestArgCommands
# ---------------------------------------------------------------------------

class TestArgCommands(unittest.TestCase):

    def test_load(self):
        # 52 octal == 42 decimal
        s1 = ok("load 52")
        assert s1.machine.ac == 0o52

    def test_load_masks_to_12_bits(self):
        # 10000 octal == 4096, masks to 0
        s1 = ok("load 10000")
        assert s1.machine.ac == 0

    def test_load_does_not_change_link(self):
        s0 = s(machine=MachineState(ac=0, link=1))
        s1 = ok("load 10", s0)
        assert s1.machine.link == 1

    def test_add(self):
        s0 = s(machine=MachineState(ac=5, link=0))
        s1 = ok("add 3", s0)
        assert s1.machine.ac == 8 and s1.machine.link == 0

    def test_add_carry_toggles_link(self):
        s0 = s(machine=MachineState(ac=0o7777, link=0))
        s1 = ok("add 1", s0)
        assert s1.machine.ac == 0 and s1.machine.link == 1

    def test_sub(self):
        s0 = s(machine=MachineState(ac=5, link=0))
        s1 = ok("sub 3", s0)
        assert s1.machine.ac == 2

    def test_sub_zero(self):
        s0 = s(machine=MachineState(ac=3, link=0))
        s1 = ok("sub 3", s0)
        assert s1.machine.ac == 0

    def test_and(self):
        s0 = s(machine=MachineState(ac=0o7700, link=0), base="OCT")
        s1 = ok("and 77", s0)
        assert s1.machine.ac == 0

    def test_and_link_unchanged(self):
        s0 = s(machine=MachineState(ac=0o7777, link=1), base="OCT")
        s1 = ok("and 0", s0)
        assert s1.machine.link == 1

    def test_or(self):
        s0 = s(machine=MachineState(ac=0o7700, link=0), base="OCT")
        s1 = ok("or 77", s0)
        assert s1.machine.ac == 0o7777

    def test_xor(self):
        s0 = s(machine=MachineState(ac=0o7777, link=0), base="OCT")
        s1 = ok("xor 7777", s0)
        assert s1.machine.ac == 0

    def test_arg_commands_update_last(self):
        s1 = ok("load 5")
        assert s1.last == "LOAD 5"

    def test_arg_missing(self):
        e = err("load")
        assert "LOAD" in e

    def test_arg_too_many(self):
        e = err("load 1 2")
        assert e is not None and "load" in e.lower()  # "load" appears in the rejected input repr

    # OCT base numeric argument
    def test_load_oct_base(self):
        s0 = s(base="OCT")
        s1 = ok("load 17", s0)
        assert s1.machine.ac == 0o17  # 15 decimal

    # BIN base numeric argument
    def test_load_bin_base(self):
        s0 = s(base="BIN")
        s1 = ok("load 1010", s0)
        assert s1.machine.ac == 0b1010  # 10 decimal

    # DEC signed negative argument
    def test_load_dec_signed_negative(self):
        s0 = s(base="DEC")
        s1 = ok("load -1", s0)
        assert s1.machine.ac == 0o7777

    # DEC unsigned rejects negative
    def test_load_dec_unsigned_negative_fails(self):
        s0 = s(base="DEC", mode="UNSIGNED")
        e = err("load -1", s0)
        assert e is not None

    def test_sub_zero_arg_is_identity(self):
        # SUB 0: CIA(0) treated as the mathematical value 0, not an OPR on state.
        # Real PDP-8: CIA(0) as OPR would toggle Link; here it does not.
        s0 = s(machine=MachineState(ac=0o1234, link=1), base="OCT")
        s1 = ok("sub 0", s0)
        assert s1.machine.ac == 0o1234
        assert s1.machine.link == 1  # link NOT toggled — design choice

    def test_sub_borrow_toggles_link(self):
        # AC=3, sub 3: CIA(3)=7775, 3+7775=10000 octal → carry, link toggles, AC=0
        s0 = s(machine=MachineState(ac=3, link=0), base="OCT")
        s1 = ok("sub 3", s0)
        assert s1.machine.ac == 0 and s1.machine.link == 1

    def test_or_link_unchanged(self):
        s0 = s(machine=MachineState(ac=0o7700, link=1), base="OCT")
        s1 = ok("or 77", s0)
        assert s1.machine.link == 1

    def test_xor_link_unchanged(self):
        s0 = s(machine=MachineState(ac=0o7777, link=1), base="OCT")
        s1 = ok("xor 7777", s0)
        assert s1.machine.link == 1

    def test_cia_7777_gives_0001(self):
        s0 = s(machine=MachineState(ac=0o7777, link=0))
        s1 = ok("cia", s0)
        assert s1.machine.ac == 1


# ---------------------------------------------------------------------------
# TestAliases
# ---------------------------------------------------------------------------

class TestAliases(unittest.TestCase):

    def test_plus_is_add(self):
        s0 = s(machine=MachineState(ac=10, link=0))
        s1 = ok("+ 5", s0)
        assert s1.machine.ac == 15

    def test_plus_last_shows_add(self):
        s1 = ok("+ 5")
        assert s1.last == "ADD 5"

    def test_minus_is_sub(self):
        s0 = s(machine=MachineState(ac=10, link=0))
        s1 = ok("- 3", s0)
        assert s1.machine.ac == 7

    def test_minus_last_shows_sub(self):
        s1 = ok("- 3")
        assert s1.last == "SUB 3"

    def test_ampersand_is_and(self):
        s0 = s(machine=MachineState(ac=0o7770, link=0))
        s1 = ok("& 7", s0)
        assert s1.machine.ac == 0

    def test_pipe_is_or(self):
        s0 = s(machine=MachineState(ac=0o7700, link=0), base="OCT")
        s1 = ok("| 77", s0)
        assert s1.machine.ac == 0o7777

    def test_caret_is_xor(self):
        s0 = s(machine=MachineState(ac=0o0101, link=0), base="OCT")
        s1 = ok("^ 7676", s0)
        assert s1.machine.ac == 0o7777

    def test_alias_requires_arg(self):
        e = err("+")
        assert e is not None

    def test_alias_rejects_extra_arg(self):
        e = err("+ 1 2")
        assert e is not None

    # --- LAST strings for logical aliases ---

    def test_ampersand_last(self):
        s1 = ok("& 7")
        assert s1.last == "AND 7"

    def test_pipe_last(self):
        s0 = s(base="OCT")
        s1 = ok("| 77", s0)
        assert s1.last == "OR 77"

    def test_caret_last(self):
        s0 = s(base="OCT")
        s1 = ok("^ 7777", s0)
        assert s1.last == "XOR 7777"


# ---------------------------------------------------------------------------
# TestLastString
# ---------------------------------------------------------------------------

class TestLastString(unittest.TestCase):

    def test_last_starts_empty(self):
        assert SessionState().last == ""

    def test_last_updated_after_op(self):
        s1 = ok("cia")
        assert s1.last == "CIA"

    def test_last_updated_after_arg_op(self):
        s1 = ok("add 42")
        assert s1.last == "ADD 42"

    def test_last_preserves_original_token(self):
        # Token as typed (uppercased), not reformatted
        s0 = s(base="OCT")
        s1 = ok("load 17", s0)
        assert s1.last == "LOAD 17"

    def test_last_not_changed_on_error(self):
        s0 = s(last="CIA")
        _, e = dispatch("load abc", s0)
        assert e is not None
        # session returned on error is the original
        new_s, _ = dispatch("load abc", s0)
        assert new_s.last == "CIA"

    def test_last_not_changed_by_base_command(self):
        s0 = s(last="RAL")
        s1 = ok("base oct", s0)
        assert s1.last == "RAL"

    def test_last_not_changed_by_mode_command(self):
        s0 = s(last="ADD 5")
        s1 = ok("mode unsigned", s0)
        assert s1.last == "ADD 5"

    def test_last_overwritten_by_next_op(self):
        s1 = ok("cia")
        s2 = ok("cla", s1)
        assert s2.last == "CLA"


# ---------------------------------------------------------------------------
# TestInputNormalization
# ---------------------------------------------------------------------------

class TestInputNormalization(unittest.TestCase):

    def test_empty_line_is_noop(self):
        s0 = SessionState()
        s1, e = dispatch("", s0)
        assert e is None and s1 == s0

    def test_whitespace_only_is_noop(self):
        s0 = SessionState()
        s1, e = dispatch("   ", s0)
        assert e is None and s1 == s0

    def test_lowercase_command_accepted(self):
        s1 = ok("cla")
        assert s1.machine.ac == 0

    def test_mixed_case_command_accepted(self):
        s1 = ok("ClA")
        assert s1.machine.ac == 0

    def test_extra_whitespace_between_tokens(self):
        s1 = ok("load   5")
        assert s1.machine.ac == 5

    def test_leading_trailing_whitespace(self):
        s1 = ok("  load 5  ")
        assert s1.machine.ac == 5


# ---------------------------------------------------------------------------
# TestErrorHandling
# ---------------------------------------------------------------------------

class TestErrorHandling(unittest.TestCase):

    def test_unknown_command(self):
        e = err("foo")
        assert "foo" in e.lower() or "unknown" in e.lower()

    def test_unknown_base(self):
        e = err("base hex")
        assert e is not None

    def test_unknown_mode(self):
        e = err("mode twos")
        assert e is not None

    def test_invalid_dec_number(self):
        e = err("load abc")
        assert e is not None

    def test_invalid_oct_number(self):
        s0 = s(base="OCT")
        e = err("load 89", s0)
        assert e is not None

    def test_invalid_bin_number(self):
        s0 = s(base="BIN")
        e = err("load 201", s0)
        assert e is not None

    def test_noarg_command_with_arg_fails(self):
        e = err("cia 5")
        assert e is not None

    def test_arg_command_without_arg_fails(self):
        e = err("add")
        assert e is not None

    def test_arg_command_with_two_args_fails(self):
        e = err("add 1 2")
        assert e is not None

    def test_base_without_arg_fails(self):
        e = err("base")
        assert e is not None

    def test_mode_without_arg_fails(self):
        e = err("mode")
        assert e is not None

    def test_base_with_extra_token_fails(self):
        e = err("base dec extra")
        assert e is not None

    def test_mode_with_extra_token_fails(self):
        e = err("mode signed extra")
        assert e is not None


# ---------------------------------------------------------------------------
# TestSessionImmutability
# ---------------------------------------------------------------------------

class TestSessionImmutability(unittest.TestCase):

    def test_error_returns_original_session(self):
        m = MachineState(ac=0o1234, link=1)
        s0 = s(machine=m, base="OCT", mode="UNSIGNED", last="RAL")
        returned, e = dispatch("load abc", s0)
        assert e is not None
        assert returned is s0

    def test_success_returns_new_session(self):
        s0 = SessionState()
        s1, e = dispatch("cla", s0)
        assert e is None
        assert s1 is not s0

    def test_base_change_preserves_machine(self):
        m = MachineState(ac=99, link=1)
        s0 = s(machine=m)
        s1 = ok("base oct", s0)
        assert s1.machine == m

    def test_mode_change_preserves_machine(self):
        m = MachineState(ac=77, link=0)
        s0 = s(machine=m)
        s1 = ok("mode unsigned", s0)
        assert s1.machine == m


# ---------------------------------------------------------------------------
# TestBaseModePropagation — live dispatch sequences
# ---------------------------------------------------------------------------

class TestBaseModePropagation(unittest.TestCase):

    # --- base change propagates to next argument parse ---

    def test_base_change_to_bin_then_load(self):
        s0 = SessionState()                     # starts OCT
        s1 = ok("base bin", s0)
        assert s1.base == "BIN"
        s2 = ok("load 1010", s1)               # 1010 binary = 10 decimal
        assert s2.machine.ac == 0b1010

    def test_base_change_to_dec_then_load(self):
        s0 = SessionState()                     # starts OCT
        s1 = ok("base dec", s0)
        assert s1.base == "DEC"
        s2 = ok("load 255", s1)                # 255 is invalid octal, valid decimal
        assert s2.machine.ac == 255

    def test_base_change_to_oct_then_load(self):
        s0 = s(base="DEC")
        s1 = ok("base oct", s0)
        assert s1.base == "OCT"
        s2 = ok("load 17", s1)                 # 17 octal = 15 decimal
        assert s2.machine.ac == 0o17

    def test_base_change_to_dec_then_add(self):
        s0 = s(machine=MachineState(ac=0, link=0))
        s1 = ok("base dec", s0)
        s2 = ok("add 255", s1)                 # 255 decimal
        assert s2.machine.ac == 255

    def test_reverted_base_uses_new_base(self):
        # OCT → DEC → OCT: final parse uses OCT
        s0 = SessionState()
        s1 = ok("base dec", s0)
        s2 = ok("base oct", s1)
        s3 = ok("load 17", s2)
        assert s3.machine.ac == 0o17

    # --- mode change propagates to next argument parse ---

    def test_mode_change_to_unsigned_rejects_negative(self):
        s0 = s(base="DEC")
        s1 = ok("mode unsigned", s0)
        assert s1.mode == "UNSIGNED"
        e = err("load -1", s1)
        assert e is not None

    def test_mode_change_to_signed_accepts_negative(self):
        s0 = s(base="DEC", mode="UNSIGNED")
        s1 = ok("mode signed", s0)
        assert s1.mode == "SIGNED"
        s2 = ok("load -1", s1)
        assert s2.machine.ac == 0o7777

    def test_base_dec_mode_sequence(self):
        # Full sequence: set base to DEC, mode to unsigned, load, confirm rejection of negative
        s0 = SessionState()
        s1 = ok("base dec", s0)
        s2 = ok("mode unsigned", s1)
        e = err("load -5", s2)
        assert e is not None

    # --- mode has no effect outside DEC base ---

    def test_mode_signed_ignored_for_oct_negative_prefix(self):
        # OCT rejects sign prefix regardless of mode
        s0 = s(base="OCT", mode="SIGNED")
        e = err("load -17", s0)
        assert e is not None

    def test_mode_unsigned_ignored_for_oct_negative_prefix(self):
        s0 = s(base="OCT", mode="UNSIGNED")
        e = err("load -17", s0)
        assert e is not None

    def test_mode_signed_ignored_for_bin_negative_prefix(self):
        s0 = s(base="BIN", mode="SIGNED")
        e = err("load -1", s0)
        assert e is not None

    # --- decimal numbers >7 rejected in OCT base ---

    def test_oct_rejects_decimal_number_with_digit_8(self):
        s0 = s(base="OCT")
        e = err("load 8", s0)
        assert e is not None

    def test_oct_accepts_255_all_digits_valid(self):
        s0 = s(base="OCT")
        s2 = ok("add 255", s0)               # 255 octal = 173 decimal, all digits < 8, valid
        assert s2.machine.ac == 0o255

    def test_dec_large_value_rejected_in_oct(self):
        s0 = s(base="OCT")
        e = err("load 89", s0)               # 8 is invalid octal digit
        assert e is not None

    def test_dec_add_with_dec_base(self):
        # add 8 should work in DEC base but fail in OCT base
        s_oct = s(machine=MachineState(ac=0, link=0), base="OCT")
        e = err("add 8", s_oct)
        assert e is not None
        s_dec = s(machine=MachineState(ac=0, link=0), base="DEC")
        s_result = ok("add 8", s_dec)
        assert s_result.machine.ac == 8
