"""Diff text utilities — pure functions, no UI.

``build_split_rows`` turns a unified diff into paired side-by-side rows for
the workspace's split view. ``build_untracked_diff`` renders an untracked
file's content as an all-additions unified diff (shared by the diff viewer
and the workspace).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Row kinds for split view cells.
KIND_CONTEXT = "context"
KIND_DEL = "del"
KIND_ADD = "add"
KIND_EMPTY = "empty"

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

# Unified-diff metadata prefixes that end/precede hunks.
_HEADER_PREFIXES = (
    "diff ",
    "index ",
    "--- ",
    "+++ ",
    "new file",
    "deleted file",
    "old mode",
    "new mode",
    "similarity",
    "rename ",
    "copy ",
    "Binary",
)


@dataclass
class SplitRow:
    """One visual row of a side-by-side diff.

    ``*_kind`` is one of ``context`` / ``del`` / ``add`` / ``empty``;
    ``*_no`` is the 1-based line number on that side (``None`` for empty
    cells and spacer rows).
    """

    left_no: int | None
    left_text: str
    left_kind: str
    right_no: int | None
    right_text: str
    right_kind: str


def build_split_rows(unified_diff: str) -> list[SplitRow]:
    """Pair up a unified diff into side-by-side rows.

    Walks hunks; within a hunk, consecutive removals and additions are paired
    index-wise (a modify shows old|new on one row) and unpaired lines get an
    ``empty`` opposite cell. Context lines appear on both sides. Hunks are
    separated by a spacer row (both kinds ``empty``). File headers and
    ``\\ No newline at end of file`` markers are skipped.
    """
    rows: list[SplitRow] = []
    left_no = right_no = 0
    in_hunk = False
    pending_del: list[str] = []
    pending_add: list[str] = []

    def flush() -> None:
        nonlocal left_no, right_no
        count = max(len(pending_del), len(pending_add))
        for i in range(count):
            if i < len(pending_del):
                l_no, l_text, l_kind = left_no, pending_del[i], KIND_DEL
                left_no += 1
            else:
                l_no, l_text, l_kind = None, "", KIND_EMPTY
            if i < len(pending_add):
                r_no, r_text, r_kind = right_no, pending_add[i], KIND_ADD
                right_no += 1
            else:
                r_no, r_text, r_kind = None, "", KIND_EMPTY
            rows.append(SplitRow(l_no, l_text, l_kind, r_no, r_text, r_kind))
        pending_del.clear()
        pending_add.clear()

    for line in unified_diff.splitlines():
        hunk = _HUNK_RE.match(line)
        if hunk:
            flush()
            if in_hunk and rows:
                # Spacer row between hunks.
                rows.append(SplitRow(None, "", KIND_EMPTY, None, "", KIND_EMPTY))
            left_no = int(hunk.group(1))
            right_no = int(hunk.group(3))
            in_hunk = True
            continue
        if not in_hunk:
            continue  # file headers before the first hunk
        if line.startswith("\\"):
            continue  # "\ No newline at end of file"
        if line.startswith("-"):
            pending_del.append(line[1:])
        elif line.startswith("+"):
            pending_add.append(line[1:])
        elif line.startswith(" ") or line == "":
            flush()
            text = line[1:] if line.startswith(" ") else ""
            rows.append(SplitRow(left_no, text, KIND_CONTEXT, right_no, text, KIND_CONTEXT))
            left_no += 1
            right_no += 1
        elif line.startswith(_HEADER_PREFIXES):
            # A new file section within a multi-file diff ends the hunk.
            flush()
            in_hunk = False
        # Anything else: ignore defensively.

    flush()
    return rows


def build_untracked_diff(rel_path: str, text: str) -> str:
    """Render an untracked file's content as an all-additions unified diff."""
    lines = text.split("\n")
    # A trailing newline produces one empty trailing element — drop it so we
    # don't show a phantom added line.
    if lines and lines[-1] == "":
        lines = lines[:-1]
    header = [
        f"diff --git a/{rel_path} b/{rel_path}",
        "new file",
        "--- /dev/null",
        f"+++ b/{rel_path}",
        f"@@ -0,0 +1,{len(lines)} @@",
    ]
    return "\n".join(header + [f"+{line}" for line in lines])
