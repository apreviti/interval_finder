# Author: Alessandro Previti
import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from interval_finder.cli import main


class CliExitStatusTests(unittest.TestCase):
    def test_main_keeps_failure_when_later_target_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'two.smt2'
            path.write_text('(declare-const x Int) (declare-const y Int) '
                            '(assert (= x 0)) (assert (= y 1))')
            for results, expected in [
                ([(True, 'correct'), (True, 'correct')], 0),
                ([(False, 'bad first'), (True, 'correct')], 1),
                ([(True, 'correct'), (False, 'bad second')], 1),
            ]:
                output = io.StringIO()
                with self.subTest(results=results):
                    with patch('sys.argv', ['interval-finder', '--verify', str(path)]), \
                         patch('interval_finder.cli.verify_intervals', side_effect=results) as verify, \
                         contextlib.redirect_stdout(output):
                        self.assertEqual(main(), expected)
                    self.assertEqual(verify.call_count, 2)
                    self.assertIn('c END', output.getvalue())
            with patch('sys.argv', ['interval-finder', str(path)]), \
                 patch('interval_finder.cli.verify_intervals') as verify, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 0)
                verify.assert_not_called()

    def test_process_propagates_failed_verification(self):
        root = Path(__file__).resolve().parents[1]
        # Force a verifier failure in a separate interpreter, leaving real
        # formula parsing and interval computation in place.
        code = '''
import runpy, sys
from unittest.mock import patch
sys.argv = ['interval-finder', '--var', 'a', '--verify', 'instances/examples/simple_test.smt2']
with patch('interval_finder.verify.verify_intervals', return_value=(False, 'controlled failure')):
    runpy.run_module('interval_finder', run_name='__main__')
'''
        env = dict(os.environ, PYTHONPATH=str(root / 'src'), PYTHONDONTWRITEBYTECODE='1')
        result = subprocess.run([sys.executable, '-c', code], cwd=root, env=env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('controlled failure', result.stdout)
        self.assertIn('c END', result.stdout)


if __name__ == '__main__':
    unittest.main()
