# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger matthias@bilger.info
from __future__ import annotations

import asyncio
import logging
import time
from unittest.mock import patch

import pytest
from mutenix.utils import block_parallel
from mutenix.utils import rate_limited_logger
from mutenix.utils import run_till_some_loop


@pytest.mark.asyncio
async def test_block_parallel_allows_single_execution():
    class TestClass:
        @block_parallel
        async def test_method(self):
            await asyncio.sleep(0.1)
            return "done"

    test_instance = TestClass()
    result = await test_instance.test_method()
    assert result == "done"


@pytest.mark.asyncio
async def test_block_parallel_blocks_parallel_execution():
    class TestClass:
        @block_parallel
        async def test_method(self):
            await asyncio.sleep(0.1)
            return "done"

    test_instance = TestClass()

    async def call_method():
        return await test_instance.test_method()

    task1 = asyncio.create_task(call_method())
    task2 = asyncio.create_task(call_method())

    results = await asyncio.gather(task1, task2)
    assert results == ["done", None]


@pytest.mark.asyncio
async def test_block_parallel_resets_after_execution():
    class TestClass:
        @block_parallel
        async def test_method(self):
            await asyncio.sleep(0.1)
            return "done"

    test_instance = TestClass()
    await test_instance.test_method()
    result = await test_instance.test_method()
    assert result == "done"


@pytest.mark.asyncio
async def test_block_parallel_logs_debug_messages():
    class TestClass:
        @block_parallel
        async def test_method(self):
            await asyncio.sleep(0.1)
            return "done"

    test_instance = TestClass()

    with patch("mutenix.utils._logger.debug") as mock_debug:
        await test_instance.test_method()
        mock_debug.assert_called_with("block_parallel %s %s", "test_method", False)


@pytest.mark.asyncio
async def test_run_till_some_loop_async():
    class TestClass:
        _run = True

        @run_till_some_loop(sleep_time=0.1)
        async def test_method(self):
            await asyncio.sleep(0.1)
            return "done"

    test_instance = TestClass()
    result = await test_instance.test_method()
    assert result == "done"


def test_run_till_some_loop_sync():
    class TestClass:
        _run = True
        _first = True

        @run_till_some_loop(sleep_time=0.1)
        def test_method(self):
            time.sleep(0.1)
            if self._first:
                self._first = False
                return None
            return "done"

    test_instance = TestClass()
    result = test_instance.test_method()
    assert result == "done"


@pytest.mark.asyncio
async def test_run_till_some_loop_async_stops_on_condition():
    class TestClass:
        _run = True
        _first = True

        @run_till_some_loop(sleep_time=0.1)
        async def test_method(self):
            await asyncio.sleep(0.1)
            if self._first:
                self._first = False
                return None
            self._run = False
            return "done"

    test_instance = TestClass()
    result = await test_instance.test_method()
    assert result == "done"


def test_run_till_some_loop_sync_stops_on_condition():
    class TestClass:
        _run = True

        @run_till_some_loop(sleep_time=0.1)
        def test_method(self):
            time.sleep(0.1)
            self._run = False
            return "done"

    test_instance = TestClass()
    result = test_instance.test_method()
    assert result == "done"


@pytest.mark.parametrize("limit, interval", [(3, 0.2), (3, 0.4)])
def test_rate_limited_logger(limit, interval):
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.DEBUG)
    log_handler = logging.StreamHandler()
    log_handler.setLevel(logging.DEBUG)
    logger.addHandler(log_handler)

    @rate_limited_logger(logger, limit=limit, interval=interval)
    def log_message(message):
        logger.debug(message)

    with patch.object(logger, "debug") as mock_debug:
        for _ in range(limit + 2):
            log_message("test message")
        assert mock_debug.call_count == limit

    with patch.object(logger, "warning") as mock_warning:
        time.sleep(interval + 1)
        log_message("test message")
        assert mock_warning.call_count == 1
        assert (
            mock_warning.call_args[0][0]
            == f"Message 'test message' was suppressed {2} times in the last {interval} seconds."
        )
