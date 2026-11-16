"""Workspace indexer — produces a project snapshot for the system prompt."""
from __future__ import annotations

from pathlib import Path

_INDEX_IGNORE = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "env",
    "dist", "build", ".next", ".cache", ".mypy_cache", ".pytest_cache",
    "coverage", ".turbo", "out",
}

_KEY_FILES = {
    "package.json", "pyproject.toml", "setup.py", "Cargo.toml",
    "go.mod", "README.md", "CLAUDE.md", ".env.example",
    "main.py", "app.py", "index.ts", "index.js", "main.ts", "main.go",
    "Makefile", "docker-compose.yml", "Dockerfile",
}


def build_workspace_index(root: Path) -> str:
    """Return a compact project overview to inject into the system prompt."""
    lines: list[str] = [f"# Project: {root.name}", ""]

    tree: list[str] = []
    try:
        for p in sorted(root.rglob("*")):
            if any(ig in p.parts for ig in _INDEX_IGNORE):
                continue
            try:
                rel = p.relative_to(root)
            except ValueError:
                continue
            depth = len(rel.parts) - 1
            if depth > 5:
                continue
            indent = "  " * depth
            if p.is_dir():
                tree.append(f"{indent}{rel.parts[-1]}/")
            else:
                try:
                    sz = p.stat().st_size
                    tree.append(f"{indent}{rel.parts[-1]}  ({_fmt_size(sz)})")
                except OSError:
                    tree.append(f"{indent}{rel.parts[-1]}")
            if len(tree) >= 120:
                tree.append("  ... (truncated)")
                break
    except Exception:
        pass

    lines.append("## File tree")
    lines.extend(tree)

    previews: list[str] = []
    for name in _KEY_FILES:
        for match in list(root.glob(f"**/{name}"))[:1]:
            if any(ig in match.parts for ig in _INDEX_IGNORE):
                continue
            try:
                text = match.read_text(encoding="utf-8", errors="replace")
                rel = match.relative_to(root)
                snippet = "\n".join(text.splitlines()[:40])
                previews.append(f"\n### {rel}\n```\n{snippet}\n```")
            except Exception:
                pass

    if previews:
        lines.append("\n## Key files")
        lines.extend(previews[:5])

    return "\n".join(lines)


def _fmt_size(b: int) -> str:
    if b < 1024:
        return f"{b}B"
    if b < 1024 * 1024:
        return f"{b // 1024}KB"
    return f"{b // (1024 * 1024)}MB"
