import asyncio
import time
from pathlib import Path
from typing import Annotated

import typer

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.ingestion.embed import LocalEmbeddings
from app.ingestion.manifest import load_manifest
from app.ingestion.pipeline import ingest_report

cli = typer.Typer(no_args_is_help=True)


@cli.callback()
def main() -> None:
    """Commands for the annual-report analyst."""


@cli.command()
def ingest(
    manifest: Annotated[Path, typer.Option(help="List of reports to ingest.")] = Path(
        "../data/reports.yaml"
    ),
    raw_dir: Annotated[Path, typer.Option(help="Folder holding the downloaded PDFs.")] = Path(
        "../data/raw"
    ),
) -> None:
    """Parse, chunk, embed and store every report in the manifest."""
    asyncio.run(_ingest(manifest, raw_dir))


async def _ingest(manifest_path: Path, raw_dir: Path) -> None:
    entries = load_manifest(manifest_path).reports
    embeddings = LocalEmbeddings(get_settings().embedding_model)
    try:
        for entry in entries:
            label = f"{entry.company} FY{entry.fiscal_year}"
            pdf_path = raw_dir / entry.file
            if not pdf_path.exists():
                typer.echo(f"{label}: missing {pdf_path}; download it from {entry.source_url}")
                continue
            started = time.perf_counter()
            async with SessionLocal() as session:
                result = await ingest_report(session, embeddings, entry, pdf_path)
            if result.status == "unchanged":
                typer.echo(f"{label}: already ingested, file unchanged")
                continue
            typer.echo(
                f"{label}: {result.pages} pages, {result.text_chunks} text and "
                f"{result.table_chunks} table chunks in {time.perf_counter() - started:.0f}s"
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    cli()
