"""Single entry CLI for read skill."""

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import trafilatura
from pypdf import PdfReader

CACHE_DIR_NAME = ".read_cache"
TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for chunk-based reading workflow."""
    parser = argparse.ArgumentParser(description="Read skill entry")
    parser.add_argument("--workspace", required=True, help="Absolute workspace path")
    subparsers = parser.add_subparsers(dest="op", required=True)

    ingest = subparsers.add_parser("ingest", help="Ingest one source into cache")
    ingest.add_argument("--source", required=True, help="URL or local file path")
    ingest.add_argument("--title", default="", help="Optional document title")
    ingest.add_argument("--chunk-size", type=int, default=1200, help="Chunk size in chars")
    ingest.add_argument(
        "--chunk-overlap",
        type=int,
        default=150,
        help="Chunk overlap in chars",
    )
    ingest.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing cached doc_id",
    )

    outline = subparsers.add_parser("outline", help="Read document outline/meta only")
    outline.add_argument("--doc-id", required=True, help="Document id from ingest")
    outline.add_argument(
        "--max-chunks",
        type=int,
        default=12,
        help="How many chunk previews to return",
    )

    find = subparsers.add_parser("find", help="Find relevant chunks by query")
    find.add_argument("--doc-id", required=True, help="Document id from ingest")
    find.add_argument("--query", required=True, help="Keyword query")
    find.add_argument("--top-k", type=int, default=5, help="Return top-k chunks")
    find.add_argument(
        "--preview-chars",
        type=int,
        default=220,
        help="Preview chars per result",
    )

    read = subparsers.add_parser("read", help="Read selected chunks by ids")
    read.add_argument("--doc-id", required=True, help="Document id from ingest")
    read.add_argument("--chunk-ids", required=True, help="Comma-separated chunk ids")
    return parser


def _resolve_workspace(raw_workspace: str) -> Path:
    """Resolve and validate workspace directory."""
    workspace = Path(raw_workspace).expanduser().resolve()
    if not workspace.exists() or not workspace.is_dir():
        raise ValueError(f"Workspace is not a directory: {workspace}")
    return workspace


def _cache_root(workspace: Path) -> Path:
    """Get workspace cache root."""
    return workspace / CACHE_DIR_NAME


def _doc_dir(workspace: Path, doc_id: str) -> Path:
    """Get one cached document directory."""
    return _cache_root(workspace) / doc_id


def _is_url(source: str) -> bool:
    """Check whether input source is a HTTP(S) URL."""
    parsed = urlparse(source)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _looks_like_pdf_url(url: str) -> bool:
    """Best-effort extension check for PDF URLs."""
    parsed = urlparse(url)
    return parsed.path.lower().endswith(".pdf")


def _normalize_text(text: str) -> str:
    """Normalize whitespace for stable chunking."""
    lines = [line.strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    normalized = "\n".join(lines)
    normalized = re.sub(r"[ \t]{2,}", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = normalized.strip()
    if not normalized:
        raise ValueError("Extracted text is empty.")
    return normalized


def _extract_html_text(html: str) -> str:
    """Extract readable text from HTML content."""
    text = trafilatura.extract(
        html,
        output_format="txt",
        include_comments=False,
        include_tables=False,
    )
    if not text:
        raise RuntimeError("Failed to extract readable text from HTML.")
    return _normalize_text(text)


def _extract_pdf_text_from_bytes(raw: bytes) -> str:
    """Extract text from PDF bytes."""
    reader = PdfReader(BytesIO(raw))
    fragments: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            fragments.append(text)
    if not fragments:
        raise RuntimeError("Failed to extract readable text from PDF.")
    return _normalize_text("\n\n".join(fragments))


def _extract_pdf_text_from_path(path: Path) -> str:
    """Extract text from local PDF file."""
    reader = PdfReader(str(path))
    fragments: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            fragments.append(text)
    if not fragments:
        raise RuntimeError("Failed to extract readable text from PDF.")
    return _normalize_text("\n\n".join(fragments))


def _download_url(url: str) -> tuple[str, bytes]:
    """Download URL and return (content_type, raw_bytes)."""
    request = Request(url, headers={"User-Agent": "researcher-zero-read-skill/0.1"})
    with urlopen(request, timeout=30) as response:
        content_type = (response.headers.get("Content-Type") or "").lower()
        return content_type, response.read()


def _chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[dict[str, Any]]:
    """Chunk text with fixed-size sliding window."""
    if chunk_size <= 0:
        raise ValueError("--chunk-size must be positive.")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("--chunk-overlap must be in [0, chunk-size).")

    step = chunk_size - chunk_overlap
    output: list[dict[str, Any]] = []
    start = 0
    chunk_id = 1

    # Sliding window keeps overlap to preserve cross-boundary context.
    while start < len(text):
        end = min(start + chunk_size, len(text))
        fragment = text[start:end].strip()
        if fragment:
            output.append(
                {
                    "id": chunk_id,
                    "start": start,
                    "end": end,
                    "length": len(fragment),
                    "text": fragment,
                }
            )
            chunk_id += 1
        if end >= len(text):
            break
        start += step

    if not output:
        raise ValueError("No chunks were generated from extracted text.")
    return output


def _infer_title(source: str) -> str:
    """Infer title when explicit title is not provided."""
    if _is_url(source):
        parsed = urlparse(source)
        tail = parsed.path.rstrip("/").split("/")[-1]
        return tail or parsed.netloc
    return Path(source).stem


def _build_doc_id(source: str) -> str:
    """Build deterministic document id from source string."""
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return digest[:16]


def _meta_path(workspace: Path, doc_id: str) -> Path:
    """Path to meta.json."""
    return _doc_dir(workspace, doc_id) / "meta.json"


def _chunks_path(workspace: Path, doc_id: str) -> Path:
    """Path to chunks.jsonl."""
    return _doc_dir(workspace, doc_id) / "chunks.jsonl"


def _write_cache(workspace: Path, meta: dict[str, Any], chunks: list[dict[str, Any]], force: bool) -> None:
    """Persist one ingested document cache."""
    doc_id = str(meta["doc_id"])
    doc_dir = _doc_dir(workspace, doc_id)
    if doc_dir.exists() and not force:
        raise FileExistsError(f"Document already ingested: {doc_id}. Use --force to overwrite.")

    doc_dir.mkdir(parents=True, exist_ok=True)
    _meta_path(workspace, doc_id).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with _chunks_path(workspace, doc_id).open("w", encoding="utf-8") as fp:
        for chunk in chunks:
            fp.write(json.dumps(chunk, ensure_ascii=False))
            fp.write("\n")


def _load_meta(workspace: Path, doc_id: str) -> dict[str, Any]:
    """Load one cached document metadata."""
    path = _meta_path(workspace, doc_id)
    if not path.exists():
        raise FileNotFoundError(f"Cached document not found: {doc_id}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid metadata format for doc_id: {doc_id}")
    return payload


def _load_chunks(workspace: Path, doc_id: str) -> list[dict[str, Any]]:
    """Load cached chunks."""
    path = _chunks_path(workspace, doc_id)
    if not path.exists():
        raise FileNotFoundError(f"Chunks file not found for doc_id: {doc_id}")

    output: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        chunk = json.loads(line)
        if not isinstance(chunk, dict):
            raise ValueError(f"Invalid chunk line for doc_id: {doc_id}")
        output.append(chunk)

    if not output:
        raise ValueError(f"Chunks are empty for doc_id: {doc_id}")
    return output


def _tokenize(text: str) -> list[str]:
    """Lowercase tokenization for lexical retrieval."""
    return [token.lower() for token in TOKEN_RE.findall(text)]


def _score_chunk(query_tokens: list[str], chunk_text: str) -> int:
    """Simple term-frequency score."""
    counts = Counter(_tokenize(chunk_text))
    return sum(counts[token] for token in query_tokens)


def _parse_chunk_ids(raw: str) -> list[int]:
    """Parse comma-separated chunk ids."""
    parts = [part.strip() for part in raw.split(",")]
    parts = [part for part in parts if part]
    if not parts:
        raise ValueError("--chunk-ids must contain at least one id.")

    ids: list[int] = []
    seen: set[int] = set()
    for part in parts:
        if not part.isdigit() or part == "0":
            raise ValueError(f"Invalid chunk id: {part!r}")
        value = int(part)
        if value in seen:
            raise ValueError(f"Duplicate chunk id: {value}")
        seen.add(value)
        ids.append(value)
    return ids


def _run_ingest(workspace: Path, args: argparse.Namespace) -> dict[str, Any]:
    """Ingest source and write chunk cache."""
    source = args.source.strip()
    if not source:
        raise ValueError("--source cannot be empty.")

    source_type: str
    if _is_url(source):
        content_type, raw = _download_url(source)
        if _looks_like_pdf_url(source) or "application/pdf" in content_type:
            text = _extract_pdf_text_from_bytes(raw)
            source_type = "web_pdf"
        else:
            html = raw.decode("utf-8", errors="ignore")
            text = _extract_html_text(html)
            source_type = "web_html"
    else:
        local_path = Path(source).expanduser().resolve()
        if not local_path.exists() or not local_path.is_file():
            raise FileNotFoundError(f"Source file not found: {local_path}")
        source = str(local_path)
        suffix = local_path.suffix.lower()
        if suffix == ".pdf":
            text = _extract_pdf_text_from_path(local_path)
            source_type = "local_pdf"
        elif suffix in {".html", ".htm"}:
            text = _extract_html_text(local_path.read_text(encoding="utf-8"))
            source_type = "local_html"
        elif suffix in {".txt", ".md"}:
            text = _normalize_text(local_path.read_text(encoding="utf-8"))
            source_type = "local_text"
        else:
            raise ValueError(f"Unsupported local file type: {suffix}")

    doc_id = _build_doc_id(source)
    chunks = _chunk_text(text, args.chunk_size, args.chunk_overlap)
    title = args.title.strip() if args.title else _infer_title(source)

    meta = {
        "doc_id": doc_id,
        "source": source,
        "source_type": source_type,
        "title": title,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "char_count": len(text),
        "chunk_size": args.chunk_size,
        "chunk_overlap": args.chunk_overlap,
        "chunk_count": len(chunks),
    }
    _write_cache(workspace, meta, chunks, args.force)
    return meta


def _run_outline(workspace: Path, args: argparse.Namespace) -> dict[str, Any]:
    """Return document-level summary plus first chunk previews."""
    if args.max_chunks <= 0:
        raise ValueError("--max-chunks must be positive.")
    meta = _load_meta(workspace, args.doc_id)
    chunks = _load_chunks(workspace, args.doc_id)

    chunk_previews = []
    for chunk in chunks[: args.max_chunks]:
        chunk_previews.append(
            {
                "id": chunk["id"],
                "length": chunk["length"],
                "preview": str(chunk["text"])[:180],
            }
        )

    return {
        "doc_id": meta["doc_id"],
        "title": meta["title"],
        "source": meta["source"],
        "source_type": meta["source_type"],
        "char_count": meta["char_count"],
        "chunk_count": meta["chunk_count"],
        "chunk_previews": chunk_previews,
    }


def _run_find(workspace: Path, args: argparse.Namespace) -> dict[str, Any]:
    """Find relevant chunks for query."""
    if args.top_k <= 0:
        raise ValueError("--top-k must be positive.")
    if args.preview_chars <= 0:
        raise ValueError("--preview-chars must be positive.")

    meta = _load_meta(workspace, args.doc_id)
    chunks = _load_chunks(workspace, args.doc_id)
    query_tokens = _tokenize(args.query)
    if not query_tokens:
        raise ValueError("--query must contain at least one alphanumeric token.")

    ranked: list[tuple[int, dict[str, Any]]] = []
    for chunk in chunks:
        score = _score_chunk(query_tokens, str(chunk["text"]))
        if score > 0:
            ranked.append((score, chunk))
    ranked.sort(key=lambda item: (-item[0], int(item[1]["id"])))

    results = []
    for score, chunk in ranked[: args.top_k]:
        results.append(
            {
                "id": chunk["id"],
                "score": score,
                "preview": str(chunk["text"])[: args.preview_chars],
            }
        )

    return {
        "doc_id": meta["doc_id"],
        "query": args.query,
        "results": results,
    }


def _run_read(workspace: Path, args: argparse.Namespace) -> dict[str, Any]:
    """Read selected chunks by ids."""
    meta = _load_meta(workspace, args.doc_id)
    chunks = _load_chunks(workspace, args.doc_id)
    selected_ids = _parse_chunk_ids(args.chunk_ids)

    index = {int(chunk["id"]): chunk for chunk in chunks}
    missing = [chunk_id for chunk_id in selected_ids if chunk_id not in index]
    if missing:
        raise ValueError(f"Chunk ids not found: {missing}")

    selected_chunks = [index[chunk_id] for chunk_id in selected_ids]
    return {
        "doc_id": meta["doc_id"],
        "title": meta["title"],
        "chunks": selected_chunks,
    }


def run_operation(args: argparse.Namespace) -> dict[str, Any]:
    """Dispatch operation and return JSON payload."""
    workspace = _resolve_workspace(args.workspace)
    if args.op == "ingest":
        return {"op": "ingest", "data": _run_ingest(workspace, args)}
    if args.op == "outline":
        return {"op": "outline", "data": _run_outline(workspace, args)}
    if args.op == "find":
        return {"op": "find", "data": _run_find(workspace, args)}
    return {"op": "read", "data": _run_read(workspace, args)}


def main() -> None:
    """CLI entry."""
    args = build_parser().parse_args()
    result = run_operation(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
