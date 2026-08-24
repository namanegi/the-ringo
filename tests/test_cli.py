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
        self.assertEqual(report["preferences"]["daily_items"], 10)

    def test_configure_supports_partial_updates(self) -> None:
        exit_code, _ = self.invoke(
            "init",
            "--native-language",
            "zh-CN",
            "--target-language",
            "ja",
        )
        self.assertEqual(exit_code, 0)

        exit_code, output = self.invoke(
            "configure",
            "--daily-items",
            "12",
            "--explanation-style",
            "Explain with concise examples and direct corrections.",
        )
        self.assertEqual(exit_code, 0)
        configuration = json.loads(output)
        self.assertEqual(configuration["daily_items"], 12)
        self.assertEqual(configuration["new_content_ratio"], 0.25)
        self.assertEqual(
            configuration["explanation_style"],
            "Explain with concise examples and direct corrections.",
        )

        exit_code, output = self.invoke("configure")
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output), configuration)

    def test_protocol_is_machine_readable(self) -> None:
        exit_code, output = self.invoke("protocol")
        protocol = json.loads(output)

        self.assertEqual(exit_code, 0)
        self.assertEqual(protocol["protocol_version"], 1)
        self.assertIn("local_state", protocol["capabilities"])
        self.assertIn("curriculum_catalog", protocol["capabilities"])
        self.assertIn("catalog", protocol["commands"])
        self.assertIn("active_learning_goal", protocol["capabilities"])
        self.assertIn("goal", protocol["commands"])

    def test_goal_command_reads_sets_and_keeps_same_value_idempotent(self) -> None:
        self.invoke(
            "init",
            "--native-language",
            "zh-CN",
            "--target-language",
            "ja",
        )

        exit_code, output = self.invoke("goal", "--json")
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output), {"active_goal": None})

        exit_code, output = self.invoke(
            "goal", "--set", "准备商务面试常用日语", "--json"
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            json.loads(output), {"active_goal": "准备商务面试常用日语"}
        )
        self.invoke("goal", "--set", "准备商务面试常用日语")
        self.assertEqual(self.invoke("doctor", "--json")[0], 0)
        report = json.loads(self.invoke("doctor", "--json")[1])
        self.assertEqual(report["active_goal"], "准备商务面试常用日语")
        self.assertEqual(report["event_count"], 2)

    def test_catalog_json_uses_custom_pack_and_dependency_order(self) -> None:
        pack_path = self.root / "custom.toml"
        pack_path.write_text(
            """
[pack]
id = "custom"
title = "Custom course"
language = "xx"

[[concepts]]
identifier = "xx.first"
title = "First"

[[concepts]]
identifier = "xx.second"
title = "Second"
prerequisites = ["xx.first"]
""".strip(),
            encoding="utf-8",
        )

        exit_code, output = self.invoke("catalog", "--pack", "custom.toml", "--json")

        self.assertEqual(exit_code, 0)
        catalog = json.loads(output)
        self.assertEqual(catalog["id"], "custom")
        self.assertEqual(
            [concept["identifier"] for concept in catalog["concepts"]],
            ["xx.first", "xx.second"],
        )

    def test_catalog_human_output_is_compact(self) -> None:
        packs_directory = self.root / "packs"
        packs_directory.mkdir()
        pack_path = packs_directory / "ja-starter.toml"
        pack_path.write_text(
            """
[pack]
id = "tiny"
title = "Tiny course"
language = "xx"

[[concepts]]
identifier = "xx.greeting"
title = "Greeting"
""".strip(),
            encoding="utf-8",
        )

        exit_code, output = self.invoke("catalog")

        self.assertEqual(exit_code, 0)
        self.assertEqual(output.splitlines(), [
            "Tiny course [xx] (tiny)",
            "1. xx.greeting — Greeting",
        ])

    def test_next_and_record_json_round_trip(self) -> None:
        self._write_pack()

        exit_code, output = self.invoke("next", "--json", "--pack", "custom.toml")
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output)["identifier"], "xx.first")

        exit_code, output = self.invoke(
            "record", "xx.first", "--outcome", "good", "--pack", "custom.toml"
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output)["streak"], 1)

        exit_code, output = self.invoke("next", "--json", "--pack", "custom.toml")
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output)["identifier"], "xx.second")

    def test_status_json_is_compact_and_uses_custom_pack(self) -> None:
        self._write_pack()
        self.invoke("init", "--native-language", "zh-CN", "--target-language", "xx")
        exit_code, output = self.invoke("status", "--json", "--pack", "custom.toml")
        status = json.loads(output)
        self.assertEqual(exit_code, 0)
        self.assertEqual(status["progress"], {"started": 0, "total": 2})
        self.assertEqual(status["next"]["reason"], "new")

    def test_session_cli_defaults_resumes_and_record_completes_exactly(self) -> None:
        self._write_pack()
        self.invoke("init", "--native-language", "zh-CN", "--target-language", "xx")
        self.invoke("goal", "--set", "商务面试常用日语")

        exit_code, output = self.invoke("session", "start", "--items", "2", "--json")
        self.assertEqual(exit_code, 0)
        started = json.loads(output)
        self.assertEqual(started["status"], "active")
        self.assertEqual(started["remaining_items"], 2)

        exit_code, output = self.invoke("record", "xx.first", "--outcome", "good", "--pack", "custom.toml")
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output)["session"]["completed_items"], 1)

        exit_code, output = self.invoke("record", "xx.second", "--outcome", "good", "--pack", "custom.toml")
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output)["session"]["status"], "completed")
        self.assertEqual(json.loads(output)["session"]["remaining_items"], 0)

        exit_code, output = self.invoke("status", "--json", "--pack", "custom.toml")
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output)["session"]["status"], "completed")

    def _write_pack(self) -> None:
        (self.root / "custom.toml").write_text(
            """
[pack]
id = "custom"
title = "Custom course"
language = "xx"

[[concepts]]
identifier = "xx.first"
title = "First"

[[concepts]]
identifier = "xx.second"
title = "Second"
prerequisites = ["xx.first"]
""".strip(),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
