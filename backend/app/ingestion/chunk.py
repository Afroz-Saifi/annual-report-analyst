from dataclasses import dataclass
from typing import Literal

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.ingestion.parse import ParsedPage

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150


@dataclass(frozen=True)
class ChunkDraft:
    page_number: int
    kind: Literal["text", "table"]
    content: str


def chunk_pages(pages: list[ParsedPage]) -> list[ChunkDraft]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    drafts: list[ChunkDraft] = []
    for page in pages:
        drafts.extend(
            ChunkDraft(page_number=page.number, kind="text", content=piece)
            for piece in splitter.split_text(page.text)
        )
        # Tables stay whole: splitting one separates the figures from their headers.
        drafts.extend(
            ChunkDraft(page_number=page.number, kind="table", content=table)
            for table in page.tables
        )
    return drafts
