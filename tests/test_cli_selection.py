# Author: Alessandro Previti
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from interval_finder.cli import main


class CliSelectionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'selection.smt2'
        self.path.write_text('(declare-const x Int) (declare-const y Int) '
                             '(declare-const b Bool) (assert (= x 1)) '
                             '(assert (= y 2)) (assert b)')

    def run_cli(self, flags):
        output = io.StringIO()
        with patch('sys.argv', ['interval-finder', str(self.path), *flags]), contextlib.redirect_stdout(output):
            self.assertEqual(main(), 0)
        return output.getvalue()

    def test_single_multiple_default_and_deduplication(self):
        text = self.run_cli(['--var', 'x'])
        self.assertIn('Var x (Int)', text)
        self.assertNotIn('Var y (Int)', text)
        self.assertNotIn('Var b (Bool)', text)
        text = self.run_cli(['--vars', 'b', 'x', 'b', '--verify'])
        self.assertLess(text.index('Var b (Bool)'), text.index('Var x (Int)'))
        self.assertEqual(text.count('Var b (Bool)'), 1)
        self.assertNotIn('Var y (Int)', text)
        text = self.run_cli([])
        for name in ('Var x (Int)', 'Var y (Int)', 'Var b (Bool)'):
            self.assertIn(name, text)

    def test_repeated_conflicting_empty_and_unknown_selections_rejected(self):
        cases = [
            ['--var', 'x', '--var', 'y'],
            ['--var', 'x', '--var', 'x'],
            ['--vars', 'x', '--vars', 'y'],
            ['--var', 'x', '--vars', 'y'],
            ['--vars', 'x', '--var', 'y'],
            ['--vars'], ['--var'], ['--vars', 'missing'],
        ]
        for flags in cases:
            error = io.StringIO()
            with self.subTest(flags=flags), patch('sys.argv', ['interval-finder', str(self.path), *flags]), \
                 contextlib.redirect_stderr(error), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    main()
                self.assertEqual(raised.exception.code, 2)
                self.assertTrue(error.getvalue())


if __name__ == '__main__':
    unittest.main()
