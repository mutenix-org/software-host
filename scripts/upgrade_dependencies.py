#!/usr/bin/env python
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "toml",
# ]
# ///
# https://gist.github.com/yhoiseth/c80c1e44a7036307e424fce616eed25e
from __future__ import annotations

import subprocess
from re import Match
from re import match
from typing import Any

import toml


def main() -> None:
    with open("pyproject.toml", "r") as file:
        pyproject: dict[str, Any] = toml.load(file)
    dependencies: list[str] = pyproject["project"]["dependencies"]
    package_name_pattern = r"^[a-zA-Z0-9\-]+"
    for dependency in dependencies:
        package_match = match(package_name_pattern, dependency)
        assert isinstance(package_match, Match)
        package = package_match.group(0)
        uv("remove", package)
        uv("add", package)


def uv(command: str, package: str) -> None:
    subprocess.run(["uv", command, package])


if __name__ == "__main__":
    main()
