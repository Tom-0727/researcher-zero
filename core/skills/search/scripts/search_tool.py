"""Single entry CLI for search skill."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Ensure this script also works when launched via:
# python core/skills/search/scripts/search_tool.py
REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for unified search entry."""
    parser = argparse.ArgumentParser(description="Search skill entry")
    parser.add_argument(
        "--provider",
        required=True,
        choices=["semantic_scholar", "arxiv", "general"],
        help="Search backend",
    )
    parser.add_argument("--query", required=True, help="Search query text")
    parser.add_argument("--limit", type=int, default=5, help="Result limit")
    parser.add_argument(
        "--kwargs-json",
        help="Extra kwargs JSON object for --provider general",
    )
    return parser


def _parse_kwargs_json(raw: str | None) -> dict[str, Any]:
    """Parse optional kwargs JSON for general search."""
    if raw is None:
        return {}
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("--kwargs-json must be a JSON object.")
    return payload


def run_search(args: argparse.Namespace) -> dict[str, Any]:
    """Dispatch by provider and return JSON-serializable payload."""
    if args.limit <= 0:
        raise ValueError("--limit must be a positive integer.")

    if args.provider == "semantic_scholar":
        from core.skills.search.scripts.semantic_scholar_search import search_semantic_scholar

        results = search_semantic_scholar.invoke({"query": args.query, "limit": args.limit})
        return {
            "provider": args.provider,
            "query": args.query,
            "limit": args.limit,
            "results": results,
        }

    if args.provider == "arxiv":
        from core.skills.search.scripts.arxiv_search import search_arxiv

        results = search_arxiv.invoke({"query": args.query, "limit": args.limit})
        return {
            "provider": args.provider,
            "query": args.query,
            "limit": args.limit,
            "results": results,
        }

    from core.skills.search.scripts.general_search import search as general_search

    kwargs = {"max_results": args.limit}
    kwargs.update(_parse_kwargs_json(args.kwargs_json))
    results = general_search(args.query, **kwargs)
    return {
        "provider": args.provider,
        "query": args.query,
        "kwargs": kwargs,
        "results": results,
    }


def main() -> None:
    """CLI entry."""
    args = build_parser().parse_args()
    result = run_search(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
