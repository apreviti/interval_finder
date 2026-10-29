# Author: Alessandro Previti
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import z3
from interval_finder import VarIntervalFinder
from interval_finder.utils import _progress_stage
from interval_finder.cli import main


class ProgressTests(unittest.TestCase):
    def test_api_discovery_reports_timing_and_can_be_silenced(self):
        x = z3.Int('x')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            finder = VarIntervalFinder(x >= 0)
        text = output.getvalue()
        self.assertIn('Collecting variables...', text)
        self.assertIn('No variable list was supplied; extracting variables automatically.', text)
        self.assertIn('This may take some time.', text)
        self.assertRegex(text, r'done in \d+\.\d{3}s')
        self.assertIn('1 variables collected; ready for interval computation.', text)
        self.assertNotIn('\r', text)
        self.assertEqual(text.count('Collecting variables'), 1)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            VarIntervalFinder(x >= 0, show_progress=False)
            VarIntervalFinder(x >= 0, [x])
        self.assertEqual(output.getvalue(), '')
        self.assertEqual(finder.variables, [x])

    def test_discovery_failure_reports_stopped_not_success(self):
        x = z3.Int('x')
        output = io.StringIO()
        with patch('interval_finder.core.z3.z3util.get_vars', side_effect=RuntimeError('discovery failed')):
            with contextlib.redirect_stdout(output), self.assertRaisesRegex(RuntimeError, 'discovery failed'):
                VarIntervalFinder(x >= 0)
        self.assertIn('stopped in', output.getvalue())
        self.assertNotIn('ready for interval computation', output.getvalue())

    def test_interactive_spinner_stops_and_joins(self):
        output = io.StringIO()
        output.isatty = lambda: True
        stopped = Mock()
        stopped.wait.side_effect = [False, True]
        worker = Mock()
        with patch('interval_finder.utils.threading.Event', return_value=stopped), patch('interval_finder.utils.threading.Thread', return_value=worker) as thread:
            worker.start.side_effect = lambda: thread.call_args.kwargs['target']()
            with contextlib.redirect_stdout(output), _progress_stage('Collecting variables'):
                pass
        self.assertIn('Collecting variables... |', output.getvalue())
        self.assertIn('done in', output.getvalue())
        stopped.set.assert_called_once()
        worker.join.assert_called_once()

    def test_cli_setup_precedes_interval_search(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'small.smt2'
            path.write_text('(declare-const x Int) (assert (= x 2))')
            output = io.StringIO()
            with patch('sys.argv', ['interval-finder', str(path)]), contextlib.redirect_stdout(output):
                main()
            text = output.getvalue()
            self.assertLess(text.index('Parsing formula...'), text.index('Collecting variables...'))
            self.assertLess(text.index('Collecting variables... done'), text.index('starting interval computation'))
            self.assertLess(text.index('starting interval computation'), text.index('Var x (Int) intervals: [2, 2]'))
            self.assertNotIn('\r', text)
            self.assertEqual(text.count('Parsing formula'), 1)
            self.assertEqual(text.count('Collecting variables'), 1)
            self.assertNotIn('this may take a while', text)


if __name__ == '__main__':
    unittest.main()
