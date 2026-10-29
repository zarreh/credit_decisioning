"""Fetch, verify and parse the UCI Statlog (German Credit) data.

The file is downloaded once into ``data/raw/`` (git-ignored) and pinned by checksum,
so every run trains on byte-identical data. Class coding is fixed here, once:
UCI's 1 = good, 2 = bad becomes ``bad`` = 0 / 1.
"""

from __future__ import annotations

import hashlib
import io
import urllib.request
import zipfile
from pathlib import Path
from typing import Final

import pandas as pd

from credit.pipeline.attributes import CATEGORY_LABELS, COLUMNS, NUMERIC, TARGET
from credit.schemas import Application

SOURCE_URL: Final = "https://archive.ics.uci.edu/static/public/144/statlog+german+credit+data.zip"
SOURCE_SHA256: Final = "b21f3d81db8071257d5ff1deaeba1fd4303b62712e6fcc9715c7a86202cb5871"
CITATION: Final = (
    "Hofmann, H. (1994). Statlog (German Credit Data) [Dataset]. "
    "UCI Machine Learning Repository. https://doi.org/10.24432/C5NC77. CC BY 4.0."
)


class DataIntegrityError(RuntimeError):
    """The source file is not the one this project was validated against."""


def fetch(raw_dir: Path) -> Path:
    """Return the path to ``german.data``, downloading it if absent."""
    target = raw_dir / "german.data"
    if not target.exists():
        raw_dir.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(SOURCE_URL, timeout=60) as response:  # noqa: S310
            archive = zipfile.ZipFile(io.BytesIO(response.read()))
        target.write_bytes(archive.read("german.data"))
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    if digest != SOURCE_SHA256:
        raise DataIntegrityError(f"german.data checksum {digest} != pinned {SOURCE_SHA256}")
    return target


def parse(text: str) -> pd.DataFrame:
    """Parse whitespace-separated german.data rows into a typed frame."""
    rows = [line.split() for line in text.splitlines() if line.strip()]
    if any(len(r) != len(COLUMNS) + 1 for r in rows):
        raise DataIntegrityError("every row must have 20 attributes plus the class")
    frame = pd.DataFrame(rows, columns=[*COLUMNS, "uci_class"])
    for column in NUMERIC:
        frame[column] = frame[column].astype(int)
    for column, codes in CATEGORY_LABELS.items():
        unknown = set(frame[column]) - set(codes)
        if unknown:
            raise DataIntegrityError(f"{column}: unknown codes {sorted(unknown)}")
    classes = set(frame["uci_class"])
    if classes != {"1", "2"}:
        raise DataIntegrityError(f"class must be 1 or 2, got {sorted(classes)}")
    frame[TARGET] = (frame.pop("uci_class") == "2").astype(int)
    frame.insert(0, "row_id", [f"uci-{i:04d}" for i in range(len(frame))])
    return frame


def load(raw_dir: Path = Path("data/raw")) -> pd.DataFrame:
    """The full, verified benchmark: 1,000 rows, 300 bad."""
    frame = parse(fetch(raw_dir).read_text())
    if len(frame) != 1000 or int(frame[TARGET].sum()) != 300:
        raise DataIntegrityError("expected 1,000 rows with 300 bad")
    return frame


def to_application(row: pd.Series) -> Application:
    """A typed application from one frame row (codes kept, numerics as int)."""
    values = {c: (int(row[c]) if c in NUMERIC else str(row[c])) for c in COLUMNS}
    return Application.model_validate(values)


def to_frame(application: Application) -> pd.DataFrame:
    return pd.DataFrame([application.model_dump()], columns=list(COLUMNS))
