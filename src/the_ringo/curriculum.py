"""Small, immutable curriculum graph objects."""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


class CurriculumError(ValueError):
    """Base class for invalid curriculum definitions."""


class InvalidIdentifierError(CurriculumError):
    """Raised when a concept identifier is not stable and well formed."""


class DuplicateConceptError(CurriculumError):
    """Raised when a curriculum contains the same concept more than once."""


class MissingPrerequisiteError(CurriculumError):
    """Raised when a concept refers to an unknown prerequisite."""


class CurriculumCycleError(CurriculumError):
    """Raised when prerequisites do not form a directed acyclic graph."""


@dataclass(frozen=True, slots=True)
class Concept:
    """A named learning concept and the concepts it depends on."""

    identifier: str
    title: str
    prerequisites: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_identifier(self.identifier)
        if not self.title.strip():
            raise ValueError("concept title must not be empty")

        prerequisites = tuple(self.prerequisites)
        if len(prerequisites) != len(set(prerequisites)):
            raise CurriculumError(
                f"concept {self.identifier!r} has duplicate prerequisites"
            )
        for prerequisite in prerequisites:
            _validate_identifier(prerequisite)
        object.__setattr__(self, "prerequisites", prerequisites)


class Curriculum:
    """An immutable collection of concepts with validated dependencies."""

    def __init__(self, concepts: Iterable[Concept]) -> None:
        concept_list = tuple(concepts)
        by_id: dict[str, Concept] = {}
        for concept in concept_list:
            if not isinstance(concept, Concept):
                raise TypeError("curriculum concepts must be Concept instances")
            if concept.identifier in by_id:
                raise DuplicateConceptError(
                    f"duplicate concept: {concept.identifier!r}"
                )
            by_id[concept.identifier] = concept

        for concept in concept_list:
            for prerequisite in concept.prerequisites:
                if prerequisite not in by_id:
                    raise MissingPrerequisiteError(
                        f"concept {concept.identifier!r} requires unknown "
                        f"concept {prerequisite!r}"
                    )

        self._concepts: Mapping[str, Concept] = MappingProxyType(by_id)
        self._ordered = self._topological_order(concept_list, by_id)

    @property
    def concepts(self) -> Mapping[str, Concept]:
        return self._concepts

    @property
    def ordered_concepts(self) -> tuple[Concept, ...]:
        """Return concepts in stable prerequisite-respecting order."""
        return self._ordered

    def get(self, identifier: str) -> Concept:
        _validate_identifier(identifier)
        return self._concepts[identifier]

    @staticmethod
    def _topological_order(
        concepts: tuple[Concept, ...], by_id: Mapping[str, Concept]
    ) -> tuple[Concept, ...]:
        visiting: set[str] = set()
        visited: set[str] = set()
        ordered: list[Concept] = []

        def visit(identifier: str) -> None:
            if identifier in visiting:
                raise CurriculumCycleError(
                    f"curriculum prerequisite cycle includes {identifier!r}"
                )
            if identifier in visited:
                return
            visiting.add(identifier)
            concept = by_id[identifier]
            for prerequisite in concept.prerequisites:
                visit(prerequisite)
            visiting.remove(identifier)
            visited.add(identifier)
            ordered.append(concept)

        for concept in concepts:
            visit(concept.identifier)
        return tuple(ordered)


def _validate_identifier(identifier: str) -> None:
    if not isinstance(identifier, str) or not _IDENTIFIER.fullmatch(identifier):
        raise InvalidIdentifierError(
            f"invalid concept identifier {identifier!r}; use lowercase "
            "segments separated by '.', '_' or '-'"
        )
