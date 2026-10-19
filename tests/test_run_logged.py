import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import loop


class RunLoggedTests(unittest.TestCase):
    def test_completed_process_uses_combined_output_limit(self):
        # Complete the real child before the first poll so this deterministically
        # exercises the final check, not the running-process polling check.
        popen = subprocess.Popen

        def completed_process(*args, **kwargs):
            process = popen(*args, **kwargs)
            process.wait(timeout=5)
            return process

        cases = [
            (6, 6, 0, True, 125),
            (10, 0, 0, False, 0),
            (5, 5, 0, False, 0),
            (0, 11, 0, True, 125),
            (2, 2, 7, False, 7),
        ]
        for stdout_bytes, stderr_bytes, exit_code, exceeded, expected_code in cases:
            with self.subTest(stdout=stdout_bytes, stderr=stderr_bytes, exit_code=exit_code):
                with tempfile.TemporaryDirectory() as temp:
                    prefix = pathlib.Path(temp) / 'command'
                    command = [sys.executable, '-c',
                               f'import sys; sys.stdout.write("a" * {stdout_bytes}); '
                               f'sys.stderr.write("b" * {stderr_bytes}); sys.exit({exit_code})']
                    with mock.patch.object(loop.subprocess, 'Popen', side_effect=completed_process):
                        result = loop.run_logged(command, temp, 10, prefix, 10)
                    self.assertEqual(result['output_limit_exceeded'], exceeded)
                    self.assertEqual(result['exit_code'], expected_code)
                    self.assertEqual(result['stdout'], 'a' * min(stdout_bytes, 10))
                    self.assertEqual(result['stderr'], 'b' * min(stderr_bytes, 10))
