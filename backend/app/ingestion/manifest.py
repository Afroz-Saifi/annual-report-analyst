from pathlib import Path

import yaml
from pydantic import BaseModel


class ReportEntry(BaseModel):
    company: str
    ticker: str
    fiscal_year: int
    source_url: str
    file: str


class Manifest(BaseModel):
    reports: list[ReportEntry]


def load_manifest(path: Path) -> Manifest:
    return Manifest.model_validate(yaml.safe_load(path.read_text()))
