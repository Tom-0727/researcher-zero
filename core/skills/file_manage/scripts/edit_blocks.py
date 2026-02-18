import difflib
import re
from dataclasses import dataclass
from pathlib import Path

from .errors import EditBlockParseError, EditMatchError

DEFAULT_FENCE = ("```", "```")
SEARCH_MARK = r"^<{5,9} SEARCH>?\s*$"
DIVIDER_MARK = r"^={5,9}\s*$"
REPLACE_MARK = r"^>{5,9} REPLACE\s*$"


@dataclass(frozen=True)
class EditBlock:
    path: str
    search: str
    replace: str


def _normalize_filename(raw: str, fence: tuple[str, str]) -> str | None:
    text = raw.strip()
    if not text or text == "...":
        return None

    if text.startswith(fence[0]) or text.startswith("```"):
        candidate = text.split(maxsplit=1)[-1] if " " in text else ""
        if candidate and ("." in candidate or "/" in candidate or "\\" in candidate):
            return candidate
        return None

    text = text.rstrip(":").lstrip("#").strip().strip("`").strip("*")
    return text or None


def _choose_filename(lines: list[str], valid_files: list[str], fence: tuple[str, str]) -> str | None:
    candidates: list[str] = []
    for line in reversed(lines[-3:]):
        candidate = _normalize_filename(line, fence)
        if candidate:
            candidates.append(candidate)
        if not line.startswith(fence[0]) and not line.startswith("```"):
            break

    if not candidates:
        return None

    for cand in candidates:
        if cand in valid_files:
            return cand
    for cand in candidates:
        for valid in valid_files:
            if cand == Path(valid).name:
                return valid
    for cand in candidates:
        close = difflib.get_close_matches(cand, valid_files, n=1, cutoff=0.8)
        if close:
            return close[0]
    return candidates[0]


def parse_edit_blocks(
    text: str,
    valid_files: list[str] | None = None,
    fence: tuple[str, str] = DEFAULT_FENCE,
) -> list[EditBlock]:
    valid_files = valid_files or []
    lines = text.splitlines(keepends=True)
    head_re = re.compile(SEARCH_MARK)
    divider_re = re.compile(DIVIDER_MARK)
    replace_re = re.compile(REPLACE_MARK)

    blocks: list[EditBlock] = []
    current_filename: str | None = None
    i = 0
    while i < len(lines):
        if not head_re.match(lines[i].strip()):
            i += 1
            continue

        filename = _choose_filename(lines[max(0, i - 3) : i], valid_files, fence) or current_filename
        if not filename:
            raise EditBlockParseError("Missing filename before SEARCH block.")
        current_filename = filename

        i += 1
        search_buf: list[str] = []
        while i < len(lines) and not divider_re.match(lines[i].strip()):
            search_buf.append(lines[i])
            i += 1
        if i >= len(lines):
            raise EditBlockParseError("Expected divider line: =======")

        i += 1
        replace_buf: list[str] = []
        while i < len(lines) and not replace_re.match(lines[i].strip()) and not divider_re.match(
            lines[i].strip()
        ):
            replace_buf.append(lines[i])
            i += 1
        if i >= len(lines):
            raise EditBlockParseError("Expected closing line: >>>>>>> REPLACE")

        blocks.append(EditBlock(path=filename, search="".join(search_buf), replace="".join(replace_buf)))
        i += 1

    return blocks


def _ensure_final_newline(text: str) -> str:
    if text and not text.endswith("\n"):
        return text + "\n"
    return text


def _strip_wrapping(text: str, path: str | None, fence: tuple[str, str]) -> str:
    if not text:
        return text
    lines = text.splitlines()
    if lines and path and lines[0].strip().endswith(Path(path).name):
        lines = lines[1:]
    if len(lines) >= 2 and lines[0].startswith(fence[0]) and lines[-1].startswith(fence[1]):
        lines = lines[1:-1]
    return _ensure_final_newline("\n".join(lines))


def _exact_replace(whole_lines: list[str], search_lines: list[str], replace_lines: list[str]) -> str | None:
    if not search_lines:
        return None
    needle = tuple(search_lines)
    n = len(search_lines)
    for idx in range(len(whole_lines) - n + 1):
        if tuple(whole_lines[idx : idx + n]) == needle:
            merged = whole_lines[:idx] + replace_lines + whole_lines[idx + n :]
            return "".join(merged)
    return None


def _indent_flexible_replace(
    whole_lines: list[str], search_lines: list[str], replace_lines: list[str]
) -> str | None:
    if not search_lines:
        return None

    leading = [len(l) - len(l.lstrip()) for l in search_lines + replace_lines if l.strip()]
    if leading and min(leading) > 0:
        outdent = min(leading)
        search_lines = [line[outdent:] if line.strip() else line for line in search_lines]
        replace_lines = [line[outdent:] if line.strip() else line for line in replace_lines]

    n = len(search_lines)
    for idx in range(len(whole_lines) - n + 1):
        window = whole_lines[idx : idx + n]
        if not all(window[j].lstrip() == search_lines[j].lstrip() for j in range(n)):
            continue

        prefixes = {
            window[j][: len(window[j]) - len(search_lines[j])]
            for j in range(n)
            if window[j].strip()
        }
        if len(prefixes) != 1:
            continue

        prefix = next(iter(prefixes))
        patched = [prefix + line if line.strip() else line for line in replace_lines]
        merged = whole_lines[:idx] + patched + whole_lines[idx + n :]
        return "".join(merged)
    return None


def _split_by_dots(text: str) -> list[str]:
    return re.split(r"(^\s*\.\.\.\n)", text, flags=re.MULTILINE | re.DOTALL)


def _replace_with_dots(whole: str, search: str, replace: str) -> str | None:
    search_parts = _split_by_dots(search)
    replace_parts = _split_by_dots(replace)
    if len(search_parts) != len(replace_parts) or len(search_parts) == 1:
        return None
    if any(search_parts[i] != replace_parts[i] for i in range(1, len(search_parts), 2)):
        raise EditMatchError("Mismatched '...' segments between SEARCH and REPLACE.")

    search_chunks = [search_parts[i] for i in range(0, len(search_parts), 2)]
    replace_chunks = [replace_parts[i] for i in range(0, len(replace_parts), 2)]
    updated = whole
    for src, dst in zip(search_chunks, replace_chunks):
        if not src and not dst:
            continue
        if not src and dst:
            updated = _ensure_final_newline(updated) + dst
            continue
        if updated.count(src) != 1:
            return None
        updated = updated.replace(src, dst, 1)
    return updated


def apply_search_replace(
    content: str,
    search: str,
    replace: str,
    path: str | None = None,
    fence: tuple[str, str] = DEFAULT_FENCE,
) -> str:
    search = _strip_wrapping(search, path, fence)
    replace = _strip_wrapping(replace, path, fence)

    if not search.strip():
        return content + replace

    whole = _ensure_final_newline(content)
    search = _ensure_final_newline(search)
    replace = _ensure_final_newline(replace)

    whole_lines = whole.splitlines(keepends=True)
    search_lines = search.splitlines(keepends=True)
    replace_lines = replace.splitlines(keepends=True)

    for candidate in (search_lines, search_lines[1:] if len(search_lines) > 2 and not search_lines[0].strip() else None):
        if candidate is None:
            continue
        replaced = _exact_replace(whole_lines, candidate, replace_lines)
        if replaced is not None:
            return replaced
        replaced = _indent_flexible_replace(whole_lines, candidate, replace_lines)
        if replaced is not None:
            return replaced

    dots = _replace_with_dots(whole, search, replace)
    if dots is not None:
        return dots

    raise EditMatchError("SEARCH block did not match target file content.")
