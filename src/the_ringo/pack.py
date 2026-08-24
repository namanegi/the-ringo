"""Load compact TOML curriculum packs into the curriculum kernel."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .curriculum import Concept, Curriculum


class CurriculumPackError(ValueError):
    """Raised when a TOML curriculum pack cannot be loaded."""


@dataclass(frozen=True, slots=True)
class CurriculumPack:
    """Immutable pack metadata paired with its validated curriculum."""

    identifier: str
    title: str
    language: str
    curriculum: Curriculum


class CurriculumPackLoader:
    """Turn the small, stable TOML pack format into a :class:`CurriculumPack`."""

    def load(self, path: str | Path) -> CurriculumPack:
        """Load and validate a curriculum pack from *path*."""
        pack_path = Path(path)
        try:
            with pack_path.open("rb") as source:
                document = tomllib.load(source)
        except FileNotFoundError as error:
            raise CurriculumPackError(
                f"curriculum pack not found: {pack_path}"
            ) from error
        except OSError as error:
            raise CurriculumPackError(
                f"could not read curriculum pack {pack_path}: {error}"
            ) from error
        except tomllib.TOMLDecodeError as error:
            raise CurriculumPackError(
                f"invalid TOML in curriculum pack {pack_path}: {error}"
            ) from error

        return self._pack_from_document(document, pack_path)

    @staticmethod
    def _pack_from_document(
        document: dict[str, Any], path: Path
    ) -> CurriculumPack:
        if not isinstance(document, dict):
            raise CurriculumPackError(f"curriculum pack {path} must be a TOML table")

        metadata = document.get("pack")
        if not isinstance(metadata, dict):
            raise CurriculumPackError(
                f"curriculum pack {path} requires a [pack] metadata table"
            )
        for field in ("id", "title", "language"):
            if not isinstance(metadata.get(field), str) or not metadata[field].strip():
                raise CurriculumPackError(
                    f"curriculum pack {path} requires non-empty pack.{field!s}"
                )

        raw_concepts = document.get("concepts")
        if not isinstance(raw_concepts, list) or not raw_concepts:
            raise CurriculumPackError(
                f"curriculum pack {path} requires a non-empty [[concepts]] list"
            )

        concepts: list[Concept] = []
        for index, raw_concept in enumerate(raw_concepts, start=1):
            if not isinstance(raw_concept, dict):
                raise CurriculumPackError(
                    f"curriculum pack {path} concept #{index} must be a table"
                )
            allowed = {"identifier", "title", "prerequisites"}
            unknown = sorted(set(raw_concept) - allowed)
            if unknown:
                raise CurriculumPackError(
                    f"curriculum pack {path} concept #{index} has unsupported "
                    f"field(s): {', '.join(unknown)}"
                )
            identifier = raw_concept.get("identifier")
            title = raw_concept.get("title")
            prerequisites = raw_concept.get("prerequisites", [])
            if not isinstance(identifier, str) or not isinstance(title, str):
                raise CurriculumPackError(
                    f"curriculum pack {path} concept #{index} requires string "
                    "identifier and title"
                )
            if not isinstance(prerequisites, list) or not all(
                isinstance(item, str) for item in prerequisites
            ):
                raise CurriculumPackError(
                    f"curriculum pack {path} concept #{index}.prerequisites "
                    "must be a list of strings"
                )
            try:
                concepts.append(Concept(identifier, title, tuple(prerequisites)))
            except (TypeError, ValueError) as error:
                raise CurriculumPackError(
                    f"curriculum pack {path} concept #{index} is invalid: {error}"
                ) from error

        try:
            curriculum = Curriculum(concepts)
        except (TypeError, ValueError) as error:
            raise CurriculumPackError(
                f"curriculum pack {path} has an invalid curriculum: {error}"
            ) from error
        return CurriculumPack(
            identifier=metadata["id"],
            title=metadata["title"],
            language=metadata["language"],
            curriculum=curriculum,
        )
