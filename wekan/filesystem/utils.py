"""Utility functions for filesystem operations."""

import json
import re
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse


def sanitize_filename(name: str) -> str:
    """Sanitize a string to be safe for filesystem use."""
    # Replace invalid characters with safe alternatives
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    # Replace multiple spaces/underscores with single underscore
    name = re.sub(r"[_\s]+", "_", name)
    # Remove leading/trailing underscores and dots
    name = name.strip("_. ")
    # Truncate if too long
    if len(name) > 200:
        name = name[:200].rstrip("_. ")
    return name or "untitled"


def host_from_url(base_url: str) -> str:
    """Convert a base URL to a filesystem-safe host directory name."""
    parsed = urlparse(base_url)
    host = parsed.netloc or parsed.path

    # Handle port numbers
    if parsed.port:
        host = f"{host.split(':')[0]}:{parsed.port}"

    return sanitize_filename(host)


def write_json_file(file_path: Path, data: dict[str, Any]) -> None:
    """Write data to a JSON file with proper formatting."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def read_json_file(file_path: Path) -> Optional[dict[str, Any]]:
    """Read data from a JSON file."""
    if not file_path.exists():
        return None
    try:
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def write_markdown_file(file_path: Path, content: str) -> None:
    """Write content to a markdown file."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)


def read_markdown_file(file_path: Path) -> Optional[str]:
    """Read content from a markdown file."""
    if not file_path.exists():
        return None
    try:
        with open(file_path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def ensure_directory(path: Path) -> Path:
    """Ensure a directory exists, creating it if necessary."""
    path.mkdir(parents=True, exist_ok=True)
    return path
