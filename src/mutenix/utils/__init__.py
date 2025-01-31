# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
import asyncio
import functools
import logging
import pathlib
import platform
import tempfile
import time


_logger = logging.getLogger(__name__)

if platform.system().lower() == "windows":  # pragma: no cover
    from mutenix.utils.windows import bring_teams_to_foreground, ensure_process_run_once
elif platform.system().lower() == "linux":  # pragma: no cover
    from mutenix.utils.linux import bring_teams_to_foreground, ensure_process_run_once
elif platform.system().lower() == "darwin":  # pragma: no cover
    from mutenix.utils.darwin import bring_teams_to_foreground, ensure_process_run_once
else:
    _logger.error("Platform not supported")

    def bring_teams_to_foreground() -> None:
        pass

    def ensure_process_run_once(
        lockfile_path: pathlib.Path = pathlib.Path(tempfile.gettempdir())
        / "mutenix.lock",
    ):
        def wrapper(func):
            return func

        return wrapper


def run_loop(func):
    if asyncio.iscoroutinefunction(func):

        async def wrapper(self, *args, **kwargs):
            while self._run:
                await func(self, *args, **kwargs)
                await asyncio.sleep(0)

    else:
        raise Exception("only for async functions")  # pragma: no cover
    return wrapper


def block_parallel(func):
    """Blocks parallel calls to the function."""
    func._already_running = False

    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        _logger.debug("block_parallel %s %s", func.__name__, func._already_running)
        if func._already_running:
            while func._already_running:
                await asyncio.sleep(0.1)
            return
        func._already_running = True
        result = await func(self, *args, **kwargs)
        func._already_running = False
        return result

    return wrapper


def run_till_some_loop(sleep_time: float = 0):
    def decorator(func):
        if asyncio.iscoroutinefunction(func):

            async def wrapper(self, *args, **kwargs):
                while self._run:
                    some = await func(self, *args, **kwargs)
                    if some:
                        return some
                    if sleep_time > 0:
                        await asyncio.sleep(sleep_time)
        else:

            def wrapper(self, *args, **kwargs):
                while self._run:
                    some = func(self, *args, **kwargs)
                    if some:
                        return some
                    if sleep_time > 0:
                        time.sleep(sleep_time)

        return wrapper

    return decorator


def rate_limited_logger(logger, limit=3, interval=10):
    """
    A decorator to limit repeated log messages.

    Args:
        logger (logging.Logger): The logger instance to use.
        limit (int): The number of allowed repeated log messages.
        interval (int): The time interval in seconds within which repeated log messages are limited.

    Returns:
        function: The wrapped logging function.
    """

    def decorator(func):
        last_logged = {}
        log_count = {}

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            message = args[0] if args else ""
            current_time = time.monotonic()

            if message not in last_logged:
                last_logged[message] = 0
                log_count[message] = 0

            if current_time - last_logged[message] > interval:
                if log_count[message] > limit:
                    logger.warning(
                        f"Message '{message}' was suppressed {log_count[message] - limit} times in the last {interval} seconds.",
                    )
                log_count[message] = 0

            if log_count[message] < limit:
                func(*args, **kwargs)
                last_logged[message] = current_time
                log_count[message] += 1
            else:
                log_count[message] += 1
                last_logged[message] = current_time

        return wrapper

    return decorator
