from __future__ import annotations

import argparse
from unittest.mock import patch

import pytest
from mutenix.__main__ import main
from mutenix.__main__ import parse_arguments


def test_parse_arguments_no_update_file():
    test_args = []
    with patch("sys.argv", ["__main__.py"] + test_args):
        args = parse_arguments()
        assert args.update_file is None


def test_parse_arguments_with_update_file():
    test_args = ["--update-file", "path/to/update.tar.gz"]
    with patch("sys.argv", ["__main__.py"] + test_args):
        args = parse_arguments()
        assert args.update_file == "path/to/update.tar.gz"


@pytest.fixture
def mock_macropad():
    with patch("mutenix.__main__.Macropad", autospec=True) as MockMacropad:
        yield MockMacropad.return_value


@pytest.fixture
def mock_check_for_self_update():
    with patch("mutenix.__main__.check_for_self_update") as mock_update:
        yield mock_update


@pytest.fixture
def mock_run_trayicon():
    with patch("mutenix.__main__.run_trayicon") as mock_trayicon:
        yield mock_trayicon


@pytest.fixture
def mock_signal():
    with patch("signal.signal") as mock_signal:
        yield mock_signal


def test_main_no_update_file(
    mock_macropad,
    mock_check_for_self_update,
    mock_run_trayicon,
    mock_signal,
):
    args = argparse.Namespace(update_file=None)

    with (
        patch("threading.Thread.start", autospec=True) as mock_thread_start,
        patch("threading.Thread.join", autospec=True) as mock_thread_join,
        patch("asyncio.run", autospec=True),
    ):
        main(args)

        mock_check_for_self_update.assert_called_once()
        mock_signal.assert_called_once()
        mock_thread_start.assert_called_once()
        mock_run_trayicon.assert_called_once_with(mock_macropad)
        mock_thread_join.assert_called_once()


def test_main_with_update_file(mock_macropad, mock_check_for_self_update, mock_signal):
    args = argparse.Namespace(update_file="path/to/update.tar.gz")

    with patch("asyncio.run", autospec=True) as mock_asyncio_run:
        main(args)

        mock_check_for_self_update.assert_called_once()
        mock_signal.assert_called_once()
        mock_asyncio_run.assert_called_once()