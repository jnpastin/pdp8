"""
Unit and smoke tests for pdp8_tui.py.

All tests that exercise pure helper functions require no curses session.
The smoke test mocks curses.initscr / wrapper to verify _run() completes
without exceptions on a synthetic 80×24 window.
"""
import unittest
import unittest.mock as mock
import curses

import pdp8_core as core
import pdp8_tui as tui
from pdp8_parser import SessionState
from pdp8_core import MachineState


# ---------------------------------------------------------------------------
# 3.8.1  Status bar composition
# ---------------------------------------------------------------------------

class TestComposeStatus(unittest.TestCase):

    def _s(self, base="OCT", mode="SIGNED", last=""):
        return SessionState(machine=MachineState(), base=base, mode=mode, last=last)

    # BASE always present
    def test_base_oct_only(self):
        s = tui._compose_status(self._s("OCT"))
        self.assertTrue(s.startswith("BASE: OCT"))
        self.assertNotIn("DECIMAL", s)
        self.assertNotIn("LAST", s)

    def test_base_bin_only(self):
        s = tui._compose_status(self._s("BIN"))
        self.assertTrue(s.startswith("BASE: BIN"))

    def test_base_dec_only(self):
        s = tui._compose_status(self._s("DEC"))
        self.assertTrue(s.startswith("BASE: DEC"))

    # DECIMAL only when BASE = DEC
    def test_decimal_signed_shown_for_dec(self):
        s = tui._compose_status(self._s("DEC", "SIGNED"))
        self.assertIn("DECIMAL: SIGNED", s)

    def test_decimal_unsigned_shown_for_dec(self):
        s = tui._compose_status(self._s("DEC", "UNSIGNED"))
        self.assertIn("DECIMAL: UNSIGNED", s)

    def test_decimal_not_shown_for_oct(self):
        s = tui._compose_status(self._s("OCT", "SIGNED"))
        self.assertNotIn("DECIMAL", s)

    def test_decimal_not_shown_for_bin(self):
        s = tui._compose_status(self._s("BIN", "UNSIGNED"))
        self.assertNotIn("DECIMAL", s)

    # LAST only when non-empty
    def test_last_shown_when_set(self):
        s = tui._compose_status(self._s("OCT", last="RAL"))
        self.assertIn("LAST: RAL", s)

    def test_last_not_shown_when_empty(self):
        s = tui._compose_status(self._s("OCT", last=""))
        self.assertNotIn("LAST", s)

    # Full three-field combination
    def test_all_three_fields(self):
        s = tui._compose_status(self._s("DEC", "SIGNED", "CIA"))
        self.assertIn("BASE: DEC", s)
        self.assertIn("DECIMAL: SIGNED", s)
        self.assertIn("LAST: CIA", s)

    # BASE+LAST without DECIMAL
    def test_base_and_last_no_decimal(self):
        s = tui._compose_status(self._s("OCT", last="CLA CLL IAC"))
        self.assertIn("BASE: OCT", s)
        self.assertIn("LAST: CLA CLL IAC", s)
        self.assertNotIn("DECIMAL", s)

    # Right side always "Q : quit"
    def test_quit_hint_always_present(self):
        for base in ("OCT", "BIN", "DEC"):
            s = tui._compose_status(self._s(base))
            self.assertTrue(s.endswith("Q : quit"), f"base={base}: {s!r}")

    # Total length exactly CONTENT_COLS
    def test_length_exactly_content_cols(self):
        for base, mode, last in [
            ("OCT", "SIGNED", ""),
            ("DEC", "SIGNED", ""),
            ("DEC", "UNSIGNED", ""),
            ("DEC", "SIGNED", "CIA"),
            ("DEC", "UNSIGNED", "LOAD 7777"),
            ("BIN", "SIGNED", "RAL RAR"),
        ]:
            s = tui._compose_status(self._s(base, mode, last))
            self.assertEqual(len(s), tui.CONTENT_COLS,
                             f"base={base} mode={mode} last={last!r}: len={len(s)}")


# ---------------------------------------------------------------------------
# 3.8.2  Triad / octal rendering helpers
# ---------------------------------------------------------------------------

class TestFmtBitsRow(unittest.TestCase):

    def test_all_zeros(self):
        row = tui._fmt_bits_row(0, 0)
        self.assertEqual(len(row), tui.CONTENT_COLS)
        self.assertIn("0  000 000 000 000", row)

    def test_all_ones(self):
        row = tui._fmt_bits_row(1, 0o7777)
        self.assertEqual(len(row), tui.CONTENT_COLS)
        self.assertIn("1  111 111 111 111", row)

    def test_link_zero_ac_full(self):
        row = tui._fmt_bits_row(0, 0o7777)
        self.assertIn("0  111 111 111 111", row)

    def test_link_one_ac_zero(self):
        row = tui._fmt_bits_row(1, 0)
        self.assertIn("1  000 000 000 000", row)

    def test_link_bit_position(self):
        row0 = tui._fmt_bits_row(0, 0)
        row1 = tui._fmt_bits_row(1, 0)
        # Link bit at _REG_PAD + 1
        pos = tui._REG_PAD + 1
        self.assertEqual(row0[pos], "0")
        self.assertEqual(row1[pos], "1")

    def test_triad_start_position(self):
        row = tui._fmt_bits_row(0, 0o7777)
        # "0  111 111 111 111" — link at _REG_PAD+1, then two spaces, then triads
        # First '1' of first triad is at _REG_PAD + 1 + 3 = _REG_PAD + 4
        pos = tui._REG_PAD + 4
        self.assertEqual(row[pos], "1")
        self.assertEqual(row[pos:pos+3], "111")


class TestFmtOctalRow(unittest.TestCase):

    def test_length(self):
        self.assertEqual(len(tui._fmt_octal_row(0)), tui.CONTENT_COLS)
        self.assertEqual(len(tui._fmt_octal_row(0o7777)), tui.CONTENT_COLS)

    def test_all_zeros(self):
        row = tui._fmt_octal_row(0)
        self.assertIn("0   0   0   0", row)

    def test_all_sevens(self):
        row = tui._fmt_octal_row(0o7777)
        self.assertIn("7   7   7   7", row)

    def test_mixed(self):
        row = tui._fmt_octal_row(0o1234)
        self.assertIn("1   2   3   4", row)

    def test_label_present(self):
        row = tui._fmt_octal_row(0)
        self.assertIn("Octal:", row)

    def test_octal_digits_under_triads(self):
        # Each octal digit at _OCTAL_COL + n*4
        row = tui._fmt_octal_row(0o5274)
        digits = [row[tui._OCTAL_COL + n * 4] for n in range(4)]
        self.assertEqual(digits, ["5", "2", "7", "4"])


class TestFmtDecimalRow(unittest.TestCase):

    def test_length(self):
        for ac in (0, 1, 0o7777, 0o4000):
            self.assertEqual(len(tui._fmt_decimal_row(ac)), tui.CONTENT_COLS,
                             f"ac={oct(ac)}")

    def test_zero(self):
        row = tui._fmt_decimal_row(0)
        self.assertIn("signed:      0", row)
        self.assertIn("unsigned:    0", row)

    def test_all_ones(self):
        row = tui._fmt_decimal_row(0o7777)
        # 0o7777 = 4095 unsigned; signed = -1
        self.assertIn("signed:     -1", row)
        self.assertIn("unsigned: 4095", row)

    def test_most_negative(self):
        # 0o4000 = 2048 unsigned; signed = -2048
        row = tui._fmt_decimal_row(0o4000)
        self.assertIn("signed:  -2048", row)
        self.assertIn("unsigned: 2048", row)


class TestFmtRegHelpers(unittest.TestCase):

    def test_labels_length(self):
        self.assertEqual(len(tui._fmt_reg_labels()), tui.CONTENT_COLS)

    def test_labels_content(self):
        row = tui._fmt_reg_labels()
        self.assertIn("L", row)
        self.assertIn("Accumulator", row)

    def test_sep_length(self):
        self.assertEqual(len(tui._fmt_reg_sep()), tui.CONTENT_COLS)

    def test_sep_content(self):
        row = tui._fmt_reg_sep()
        self.assertIn("---", row)
        self.assertIn("---------------", row)


# ---------------------------------------------------------------------------
# 3.8.3  Smoke test — _run() completes without exceptions on 80×24 window
# ---------------------------------------------------------------------------

class TestTUISmoke(unittest.TestCase):

    def _make_window(self, rows=24, cols=80):
        """Return a MagicMock that looks like a curses window of given size."""
        win = mock.MagicMock()
        win.getmaxyx.return_value = (rows, cols)
        # getch: immediately return Ctrl+C to exit the input loop
        win.getch.return_value = 0x03
        return win

    def test_startup_no_exception(self):
        """_run() must complete without raising on a valid 80×24 window."""
        win = self._make_window()
        with mock.patch("curses.noecho"), \
             mock.patch("curses.cbreak"), \
             mock.patch("curses.curs_set"), \
             mock.patch("curses.start_color"), \
             mock.patch("curses.use_default_colors"):
            tui._run(win)   # should not raise

    def test_startup_too_small_raises(self):
        """_run() must raise SystemExit on a window that is too small."""
        win = self._make_window(rows=20, cols=70)
        with mock.patch("curses.noecho"), \
             mock.patch("curses.cbreak"), \
             mock.patch("curses.curs_set"), \
             mock.patch("curses.start_color"), \
             mock.patch("curses.use_default_colors"):
            with self.assertRaises(SystemExit):
                tui._run(win)

    def test_initial_render_calls_register_display(self):
        win = self._make_window()
        with mock.patch("curses.noecho"), \
             mock.patch("curses.cbreak"), \
             mock.patch("curses.curs_set"), \
             mock.patch("curses.start_color"), \
             mock.patch("curses.use_default_colors"), \
             mock.patch.object(tui, "_draw_register_display") as dr, \
             mock.patch.object(tui, "_draw_status_bar") as ds:
            tui._run(win)
        self.assertTrue(dr.called)
        self.assertTrue(ds.called)


if __name__ == "__main__":
    unittest.main(verbosity=2)
