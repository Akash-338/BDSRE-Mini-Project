"""Safely refresh known generated artifacts after a successful run."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile


def refresh_directory(destination: Path, build, patterns: tuple[str, ...], inputs=()):
    destination = destination.expanduser().resolve()
    for source in inputs:
        source = Path(source).expanduser().resolve()
        if source == destination or destination in source.parents or (source.is_dir() and source in destination.parents):
            raise ValueError("output directory and input cannot contain one another")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".bdsre-stage-", dir=destination.parent) as temporary:
        stage = Path(temporary) / "output"
        result = build(stage)
        # Update paths in manifests before publishing the staged artifacts.
        old, new = str(stage), str(destination)
        for file in stage.rglob("*.json"):
            value = json.loads(file.read_text(encoding="utf-8"))
            file.write_text(json.dumps(replace_paths(value, old, new), indent=2) + "\n", encoding="utf-8")
        result = replace_paths(result, old, new)
        destination.mkdir(parents=True, exist_ok=True)
        for pattern in patterns:
            for file in destination.glob(pattern):
                if file.is_file():
                    file.unlink()
        for file in stage.rglob("*"):
            if file.is_file():
                target = destination / file.relative_to(stage)
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(file, target)
        return result


def replace_paths(value, old: str, new: str):
    if isinstance(value, str):
        return value.replace(old, new)
    if isinstance(value, list):
        return [replace_paths(item, old, new) for item in value]
    if isinstance(value, dict):
        return {key: replace_paths(item, old, new) for key, item in value.items()}
    return value


def refresh_json(destination: Path, build):
    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".bdsre-stage-", dir=destination.parent) as temporary:
        stage = Path(temporary) / "result.json"
        result = build(stage)
        os.replace(stage, destination)
        return result
