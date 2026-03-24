from __future__ import annotations

from pathlib import Path
import re

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / "src"


def _read_python_files() -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    for path in SRC_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        files.append((path, text))
    return files


def test_forbid_source_fetch_result_symbol_in_source_code() -> None:
    offenders: list[str] = []
    for path, text in _read_python_files():
        if re.search(r"\bSourceFetchResult\b", text):
            offenders.append(str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"))

    assert not offenders, (
        "Found forbidden compatibility symbol 'SourceFetchResult' in source code files: "
        + ", ".join(sorted(offenders))
    )


def test_forbid_free_dict_payload_annotations_in_fetch_results() -> None:
    offenders: list[str] = []
    # Guard against adding weakly typed payload annotations back into fetch-result models.
    pattern = re.compile(r"payload\s*:\s*list\s*\[\s*dict\s*\[", re.MULTILINE)

    for path, text in _read_python_files():
        if path.name != "models.py":
            continue
        if pattern.search(text):
            offenders.append(str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"))

    assert not offenders, (
        "Found forbidden free dict payload annotation in fetch-result models: "
        + ", ".join(sorted(offenders))
    )
