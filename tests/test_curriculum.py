from __future__ import annotations

import unittest

from the_ringo.curriculum import (
    Concept,
    Curriculum,
    CurriculumCycleError,
    DuplicateConceptError,
    InvalidIdentifierError,
    MissingPrerequisiteError,
)


class CurriculumTests(unittest.TestCase):
    def test_order_is_stable_and_respects_prerequisites(self) -> None:
        basic = Concept("ja.greetings", "Greetings")
        polite = Concept("ja.polite", "Polite forms", (basic.identifier,))
        curriculum = Curriculum((polite, basic))

        self.assertEqual(curriculum.ordered_concepts, (basic, polite))
        self.assertEqual(curriculum.get("ja.polite"), polite)

    def test_rejects_invalid_identifiers(self) -> None:
        with self.assertRaises(InvalidIdentifierError):
            Concept("Ja Greetings", "Greetings")

    def test_rejects_duplicate_and_missing_concepts(self) -> None:
        with self.assertRaises(DuplicateConceptError):
            Curriculum((Concept("ja.basic", "Basic"), Concept("ja.basic", "Again")))

        with self.assertRaises(MissingPrerequisiteError):
            Curriculum((Concept("ja.polite", "Polite", ("ja.basic",)),))

    def test_rejects_cycles(self) -> None:
        first = Concept("ja.first", "First", ("ja.second",))
        second = Concept("ja.second", "Second", ("ja.first",))

        with self.assertRaises(CurriculumCycleError):
            Curriculum((first, second))

    def test_objects_are_immutable(self) -> None:
        concept = Concept("ja.basic", "Basic")
        curriculum = Curriculum((concept,))

        with self.assertRaises((AttributeError, TypeError)):
            concept.title = "Changed"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            curriculum.concepts["ja.other"] = concept  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()
