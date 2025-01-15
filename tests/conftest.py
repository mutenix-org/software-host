# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger matthias@bilger.info
from __future__ import annotations

import logging

import pytest


@pytest.fixture(scope="session", autouse=True)
def loggingconfig():
    print("Setting up logging configuration")
    logging.basicConfig(level=logging.DEBUG)
    loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
    for logger in loggers:
        logger.setLevel(logging.DEBUG)
