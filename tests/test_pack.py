from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from the_ringo.pack import CurriculumPackError, CurriculumPackLoader


class CurriculumPackLoaderTests(unittest.TestCase):
    def test_loads_starter_pack_in_prerequisite_order(self) -> None:
        pack = CurriculumPackLoader().load(
            Path(__file__).parents[1] / "packs" / "ja-starter.toml"
        )

        self.assertEqual(pack.identifier, "ja-starter")
        self.assertEqual(pack.title, "Japanese starter")
        self.assertEqual(pack.language, "ja")
        self.assertEqual(
            [concept.identifier for concept in pack.curriculum.ordered_concepts],
            ["ja.greetings", "ja.self-introduction", "ja.copula"],
        )

    def test_rejects_a_pack_with_a_bad_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.toml"
            path.write_text(
                '[pack]\nid = "bad"\ntitle = "Bad"\nlanguage = "ja"\n\n'
                '[[concepts]]\nidentifier = "ja.basic"\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(CurriculumPackError, "requires string"):
                CurriculumPackLoader().load(path)


if __name__ == "__main__":
    unittest.main()
