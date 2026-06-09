"""Export FastAPI OpenAPI JSON and grouped Markdown endpoint docs."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from novel_writer.server import app

DOCS_DIR = ROOT / "docs"
OPENAPI_PATH = DOCS_DIR / "openapi.json"
API_MD_PATH = DOCS_DIR / "API.md"


def infer_group(path: str, method: str, operation: dict[str, Any]) -> str:
    tags = operation.get("tags") or []
    if tags and tags[0] not in {"novel"}:
        return str(tags[0])
    if path.startswith("/api/v2"):
        return "v2"
    if "/chapters/" in path or path.endswith("/chapters/reorder"):
        return "chapters"
    if "/generate" in path or path.endswith("/draft") or path.endswith("/expand"):
        return "generation"
    if any(part in path for part in ("/export", "/publish", "/tts", "/audio", "/voice")):
        return "publishing-audio"
    if any(part in path for part in ("/quality", "/analytics", "/analysis", "/check", "/score", "/report")):
        return "quality-analytics"
    if any(part in path for part in ("/foreshadowing", "/outline", "/characters", "/factions", "/world")):
        return "story-world"
    if path.startswith("/api/providers") or path.startswith("/api/settings"):
        return "settings-providers"
    if path.startswith("/api/novels"):
        return "novels"
    if path.startswith("/api/"):
        return "system"
    return method.lower()


def op_summary(operation: dict[str, Any]) -> str:
    return str(operation.get("summary") or operation.get("operationId") or "").replace("\n", " ").strip()


def main() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    OPENAPI_PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    grouped: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for path, path_item in sorted(schema.get("paths", {}).items()):
        if not path.startswith("/api"):
            continue
        for method, operation in sorted(path_item.items()):
            if method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                continue
            group = infer_group(path, method.upper(), operation)
            grouped[group].append((method.upper(), path, op_summary(operation)))

    lines = [
        "# API Reference",
        "",
        "Generated from `novel_writer.server:app` with `python3 scripts/export_api_docs.py`.",
        "",
        f"Total endpoints: {sum(len(v) for v in grouped.values())}",
        "",
    ]
    for group in sorted(grouped):
        lines.extend([f"## {group}", "", "| Method | Path | Summary |", "|---|---|---|"])
        for method, path, summary in grouped[group]:
            lines.append(f"| `{method}` | `{path}` | {summary} |")
        lines.append("")

    API_MD_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OPENAPI_PATH.relative_to(ROOT)}")
    print(f"Wrote {API_MD_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
