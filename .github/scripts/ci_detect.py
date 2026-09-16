#!/usr/bin/env python3
"""Resolve whether frontend validation is affected by git changes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import PurePosixPath

SERVICES = ("frontend",)
SERVICE_ROOT = "src/frontend/"
DOCKER_INPUTS = {"Dockerfile", ".dockerignore", "pyproject.toml", "uv.lock"}
COMMON_DOCKER_PREFIXES = (".github/workflows/", ".github/scripts/")
COMMON_DOCKER_FILES = {".github/dependabot.yml"}
COMMON_VALIDATION_FILES = {".github/CODEOWNERS"}
DOC_PREFIXES = ("docs/", ".github/ISSUE_TEMPLATE/", ".github/PULL_REQUEST_TEMPLATE/")
DOC_FILES = {"README.md", "LICENSE", "NOTICE", ".gitignore", ".gitattributes"}


def normalize(path: str) -> str:
    normalized = PurePosixPath(path.strip().replace("\\", "/")).as_posix()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def paths_from_name_status(text: str) -> list[str]:
    paths: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith(("R", "C")):
            if len(parts) != 3:
                raise ValueError(f"invalid rename/copy entry: {line!r}")
            paths.extend((normalize(parts[1]), normalize(parts[2])))
        else:
            if len(parts) != 2:
                raise ValueError(f"invalid name-status entry: {line!r}")
            paths.append(normalize(parts[1]))
    return sorted(set(paths))


def is_docs_only(path: str) -> bool:
    return path in DOC_FILES or path.endswith(".md") or any(
        path.startswith(prefix) for prefix in DOC_PREFIXES
    )


def classify(paths: list[str]) -> tuple[list[str], list[str]]:
    selected = False
    docker_selected = False
    unknown: list[str] = []
    for raw_path in paths:
        path = normalize(raw_path)
        if is_docs_only(path):
            continue
        if path.startswith(SERVICE_ROOT):
            selected = True
            if path.removeprefix(SERVICE_ROOT) in DOCKER_INPUTS:
                docker_selected = True
        elif path in COMMON_DOCKER_FILES or any(path.startswith(p) for p in COMMON_DOCKER_PREFIXES):
            selected = True
            docker_selected = True
        elif path in COMMON_VALIDATION_FILES:
            selected = True
        else:
            unknown.append(path)
    if unknown:
        raise ValueError("unclassified paths; update CI mapping: " + ", ".join(sorted(unknown)))
    services = ["frontend"] if selected else []
    docker_services = ["frontend"] if docker_selected else []
    return services, docker_services


def emit(services: list[str], docker_services: list[str]) -> None:
    compact = {"separators": (",", ":")}
    print(f"services={json.dumps(services, **compact)}")
    print(f"docker_services={json.dumps(docker_services, **compact)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", help="git diff --name-status file")
    parser.add_argument("--all", action="store_true", help="select frontend")
    args = parser.parse_args()
    try:
        if args.all:
            emit(["frontend"], ["frontend"])
        else:
            if not args.input:
                parser.error("--input is required unless --all is used")
            with open(args.input, encoding="utf-8") as file:
                paths = paths_from_name_status(file.read())
            emit(*classify(paths))
    except (OSError, ValueError) as error:
        print(f"::error::{error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
