from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from engram.models import DataChunk


class DataParser(ABC):
    name: str
    description: str

    @abstractmethod
    def validate(self, path: Path) -> bool:
        """Check if the file/directory is valid for this parser."""

    @abstractmethod
    def parse(self, path: Path) -> list[DataChunk]:
        """Parse the data source into standardized DataChunks."""

    @abstractmethod
    def get_import_guide(self) -> str:
        """Return instructions for how to export data from this platform."""
