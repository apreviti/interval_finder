# Author: Alessandro Previti
"""Run local regression tests and the bundled CLI example with the active Python."""
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    try:
        import z3
    except ImportError:
        print('Z3 is missing. Install the project dependency: pip install z3-solver', file=sys.stderr)
        return 1
    print(f'Python {platform.python_version()} / Z3 {z3.get_version_string()}', flush=True)
    env = dict(os.environ)
    env['PYTHONPATH'] = str(ROOT / 'src') + (os.pathsep + env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    try:
        print('\nRunning regression tests...', flush=True)
        subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                       cwd=ROOT, env=env, timeout=60, check=True)
        print('\nChecking bundled CLI example...', flush=True)
        result = subprocess.run(
            [sys.executable, '-m', 'interval_finder', 'instances/examples/simple_test.smt2',
             '--vars', 'a', 'b', '--verify'],
            cwd=ROOT, env=env, timeout=15, check=True, capture_output=True, text=True)
        print(result.stdout, end='')
        if result.stderr:
            print(result.stderr, file=sys.stderr, end='')
        required = ('Var a (Int) intervals: [3, 5]; [9, 12];',
                    'Var b (Int) intervals: (-∞, 0]; [5, 9];')
        if (not all(line in result.stdout for line in required)
                or result.stdout.count('c verify: Intervals are correct') != 2):
            print('FAILED: bundled CLI example output or verification did not match.', file=sys.stderr)
            return 1
    except subprocess.TimeoutExpired:
        print('FAILED: check exceeded its time limit.', file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as error:
        if error.stdout:
            print(error.stdout, file=sys.stderr)
        if error.stderr:
            print(error.stderr, file=sys.stderr)
        print('FAILED: a check returned an error.', file=sys.stderr)
        return 1
    print('\nAll local checks passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
