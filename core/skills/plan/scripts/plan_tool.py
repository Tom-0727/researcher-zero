"""Deterministic SEARCH/REPLACE patcher for <PLAN> files."""

import argparse
import re
from pathlib import Path

PLAN_RE = re.compile(r"<PLAN>\s*(.*?)\s*</PLAN>", re.DOTALL)
ITEM_RE = re.compile(r"^- (.+)$")


def parse_plan(text: str) -> list[str]:
    """Parse a strict <PLAN> block into a list of step strings."""
    match = PLAN_RE.search(text)
    if not match:
        raise ValueError("Missing <PLAN>...</PLAN> block.")
    body = match.group(1).strip()
    if not body:
        return []
    items = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        item_match = ITEM_RE.fullmatch(line)
        if not item_match:
            raise ValueError(f"Invalid plan line: {raw!r}. Expected '- <text>'.")
        items.append(item_match.group(1).strip())
    return items


def _render_plan(items: list[str]) -> str:
    """Render list items to normalized text used by patch matching."""
    if not items:
        return ""
    return "\n".join(f"- {item.strip()}" for item in items) + "\n"


def render_plan_block(items: list[str]) -> str:
    """Render plan items to canonical <PLAN> block text."""
    body = _render_plan(items).rstrip("\n")
    return f"<PLAN>\n{body}\n</PLAN>" if body else "<PLAN>\n</PLAN>"


def _normalize_patch_block(block_text: str) -> str:
    """Normalize SEARCH/REPLACE block lines to canonical bullet format."""
    stripped = block_text.strip()
    if not stripped:
        return ""
    lines = []
    for raw in stripped.splitlines():
        line = raw.strip()
        if not line:
            continue
        item_match = ITEM_RE.fullmatch(line)
        if not item_match:
            raise ValueError(f"Invalid patch line: {raw!r}. Expected '- <text>'.")
        lines.append(f"- {item_match.group(1).strip()}")
    return "\n".join(lines) + ("\n" if lines else "")


def _parse_patch_blocks(patch_text: str) -> list[tuple[str, str]]:
    """Parse SEARCH/REPLACE patch blocks with strict markers."""
    lines = patch_text.splitlines()
    blocks: list[tuple[str, str]] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line != "<<<<<<< SEARCH":
            raise ValueError(f"Unexpected patch line outside block: {lines[i]!r}")

        i += 1
        search_lines: list[str] = []
        while i < len(lines) and lines[i].strip() != "=======":
            search_lines.append(lines[i])
            i += 1
        if i >= len(lines):
            raise ValueError("Missing '=======' marker in patch block.")

        i += 1
        replace_lines: list[str] = []
        while i < len(lines) and lines[i].strip() != ">>>>>>> REPLACE":
            replace_lines.append(lines[i])
            i += 1
        if i >= len(lines):
            raise ValueError("Missing '>>>>>>> REPLACE' marker in patch block.")

        blocks.append(("\n".join(search_lines), "\n".join(replace_lines)))
        i += 1
    return blocks


def apply_patch(plan: list[str], patch_text: str) -> list[str]:
    """Apply one or more SEARCH/REPLACE blocks to a plan list."""
    blocks = _parse_patch_blocks(patch_text)
    if not blocks:
        raise ValueError("No valid SEARCH/REPLACE block found.")

    content = _render_plan(plan)
    for search_raw, replace_raw in blocks:
        search = _normalize_patch_block(search_raw)
        replace = _normalize_patch_block(replace_raw)

        # Empty SEARCH means append.
        if not search:
            content += replace
            continue

        hits = content.count(search)
        if hits != 1:
            raise ValueError(f"SEARCH must match exactly once, found {hits}.")
        content = content.replace(search, replace, 1)

    return parse_plan(f"<PLAN>\n{content}</PLAN>")


def patch_plan_file(plan_path: str | Path, patch_text: str) -> str:
    """Apply patch to a plan file, persist the result, and return new plan text."""
    path = Path(plan_path)
    if path.exists():
        original = path.read_text(encoding="utf-8")
    else:
        original = "<PLAN>\n</PLAN>\n"
    patched = apply_patch(parse_plan(original), patch_text)
    output = render_plan_block(patched)
    # Always write canonical block back, so subsequent patches stay deterministic.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{output}\n", encoding="utf-8")
    return output


def main() -> None:
    """CLI: input plan path + patch text, output patched <PLAN> block text."""
    parser = argparse.ArgumentParser(description="Apply SEARCH/REPLACE patch to a <PLAN> file")
    parser.add_argument("--plan", required=True, help="Path to plan file")
    parser.add_argument("--patch", required=True, help="Patch text with SEARCH/REPLACE blocks")
    args = parser.parse_args()
    print(patch_plan_file(args.plan, args.patch))


if __name__ == "__main__":
    main()
