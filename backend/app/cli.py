import asyncio
import json
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.evaluation.dataset import load_dataset
from app.evaluation.runner import QuestionResult, Summary, evaluate_question, summarise
from app.ingestion.embed import LocalEmbeddings
from app.ingestion.manifest import load_manifest
from app.ingestion.pipeline import ingest_report
from app.qa.baseline import GeminiAnswerGenerator

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


@cli.command(name="eval")
def evaluate(
    dataset: Annotated[Path, typer.Option(help="Questions with their accepted answers.")] = Path(
        "evals/questions.yaml"
    ),
    top_k: Annotated[int, typer.Option(help="Sources shown to the model per question.")] = 8,
    output_dir: Annotated[Path, typer.Option(help="Where the full results are saved.")] = Path(
        "evals/results"
    ),
) -> None:
    """Answer every evaluation question and report how many were right."""
    settings = get_settings()
    if settings.google_api_key is None or not settings.google_api_key.get_secret_value():
        typer.echo("GOOGLE_API_KEY is not set in backend/.env")
        raise typer.Exit(code=1)
    generator = GeminiAnswerGenerator(settings.llm_model, settings.google_api_key)
    results = asyncio.run(_evaluate(dataset, generator, top_k))
    summaries = summarise(results)

    typer.echo(_format_results(results))
    typer.echo(_format_summary(summaries))

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
    output_path.write_text(
        json.dumps(
            {
                "llm_model": settings.llm_model,
                "embedding_model": settings.embedding_model,
                "top_k": top_k,
                "summary": [asdict(summary) for summary in summaries],
                "results": [asdict(result) for result in results],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    typer.echo(f"Full results saved to {output_path}")


async def _evaluate(
    dataset_path: Path, generator: GeminiAnswerGenerator, top_k: int
) -> list[QuestionResult]:
    questions = load_dataset(dataset_path).questions
    embeddings = LocalEmbeddings(get_settings().embedding_model)
    results = []
    try:
        async with SessionLocal() as session:
            for question in questions:
                results.append(
                    await evaluate_question(session, embeddings, generator, question, top_k)
                )
    finally:
        await engine.dispose()
    return results


def _mark(value: bool | None) -> str:
    return "-" if value is None else "yes" if value else "NO"


def _format_results(results: list[QuestionResult]) -> str:
    lines = [f"{'question':<28} {'correct':<8} {'retrieved':<10} {'supported':<10} cited pages"]
    for result in results:
        pages = "error: " + result.error[:60] if result.error else str(result.cited_pages)
        lines.append(
            f"{result.id:<28} {_mark(result.correct):<8} {_mark(result.retrieved):<10} "
            f"{_mark(result.supported):<10} {pages}"
        )
    return "\n".join(lines)


def _format_summary(summaries: list[Summary]) -> str:
    def share(part: int, whole: int) -> str:
        return f"{part}/{whole} ({part / whole:.0%})" if whole else "-"

    lines = ["", f"{'category':<22} {'correct':<14} {'retrieved':<14} supported"]
    for summary in summaries:
        lines.append(
            f"{summary.label:<22} {share(summary.correct, summary.total):<14} "
            f"{share(summary.retrieved, summary.answerable):<14} "
            f"{share(summary.supported, summary.answerable)}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    cli()
