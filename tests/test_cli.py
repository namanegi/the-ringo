from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from the_ringo.cli import main


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)

    def invoke(self, *arguments: str) -> tuple[int, str]:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(["--root", str(self.root), *arguments])
        return exit_code, output.getvalue()

    def test_init_and_doctor_json_round_trip(self) -> None:
        exit_code, _ = self.invoke(
            "init",
            "--native-language",
            "zh-CN",
            "--target-language",
            "ja",
        )
        self.assertEqual(exit_code, 0)

        exit_code, output = self.invoke("doctor", "--json")
        report = json.loads(output)

        self.assertEqual(exit_code, 0)
        self.assertTrue(report["initialized"])
        self.assertEqual(report["profile"]["native_language"], "zh-CN")
        self.assertEqual(report["profile"]["target_language"], "ja")

    def test_protocol_is_machine_readable(self) -> None:
        exit_code, output = self.invoke("protocol")
        protocol = json.loads(output)

        self.assertEqual(exit_code, 0)
        self.assertEqual(protocol["protocol_version"], 1)
        self.assertIn("local_state", protocol["capabilities"])


if __name__ == "__main__":
    unittest.main()
