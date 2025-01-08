from __future__ import annotations

import os
import pathlib
import unittest
from unittest.mock import MagicMock
from unittest.mock import mock_open
from unittest.mock import patch

import requests
from mutenix.hid_commands import HardwareTypes
from mutenix.updates import check_for_device_update
from mutenix.updates import check_for_self_update
from mutenix.updates import Chunk
from mutenix.updates import FileChunk
from mutenix.updates import FileEnd
from mutenix.updates import FileStart
from mutenix.updates import MAX_CHUNK_SIZE
from mutenix.updates import perform_hid_upgrade
from mutenix.updates import RequestChunk
from mutenix.updates import TransferFile
from mutenix.updates import VersionInfo


class TestUpdates(unittest.TestCase):
    @patch("mutenix.updates.requests.get")
    @patch("mutenix.updates.semver.compare")
    def test_check_for_device_update_up_to_date(self, mock_compare, mock_get):
        mock_compare.return_value = 0
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"latest": "1.0.0"}
        device_version = VersionInfo(
            buffer=bytes([1, 0, 0, HardwareTypes.UNKNOWN.value, 0, 0, 0, 0]),
        )
        mock_device = MagicMock()
        check_for_device_update(mock_device, device_version)

        mock_get.assert_called_once()
        mock_compare.assert_called_once_with("1.0.0", "1.0.0")

    @patch("mutenix.updates.requests.get")
    @patch("mutenix.updates.semver.compare")
    @patch("mutenix.updates.perform_hid_upgrade")
    def test_check_for_device_update_needs_update(
        self, mock_upgrade, mock_compare, mock_get,
    ):
        mock_compare.return_value = -1
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "latest": "2.0.0",
            "2.0.0": {"url": "http://example.com/update.tar.gz"},
        }

        mock_update_response = MagicMock()
        mock_update_response.status_code = 200
        mock_update_response.content = b"fake content"
        mock_get.side_effect = [mock_get.return_value, mock_update_response]

        device_version = VersionInfo(
            buffer=bytes([1, 0, 0, HardwareTypes.UNKNOWN.value, 0, 0, 0, 0]),
        )
        with patch("tarfile.open") as mock_tarfile:
            mock_tarfile.return_value.__enter__.return_value.extractall = MagicMock()
            mock_device = MagicMock()
            check_for_device_update(mock_device, device_version)

        mock_get.assert_called()
        mock_compare.assert_called_once_with("1.0.0", "2.0.0")
        mock_upgrade.assert_called_once()

    @patch("mutenix.updates.requests.get")
    def test_check_for_device_update_no_response(self, mock_get):
        mock_get.return_value.status_code = 500
        mock_get.return_value.json.return_value = None
        device_version = VersionInfo(
            buffer=bytes([1, 0, 0, HardwareTypes.UNKNOWN.value, 0, 0, 0, 0]),
        )
        mock_device = MagicMock()
        check_for_device_update(mock_device, device_version)

        mock_get.assert_called_once()

    @patch("mutenix.updates.requests.get")
    @patch("mutenix.updates.semver.compare")
    @patch("mutenix.updates.perform_hid_upgrade")
    def test_check_for_device_update_needs_update_but_fails(
        self, mock_upgrade, mock_compare, mock_get,
    ):
        mock_compare.return_value = -1
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "latest": "2.0.0",
            "2.0.0": {"url": "http://example.com/update.tar.gz"},
        }

        mock_update_response = MagicMock()
        mock_update_response.side_effect = requests.RequestException("Network error")
        mock_get.side_effect = [mock_get.return_value, requests.RequestException("Network error")]

        device_version = VersionInfo(
            buffer=bytes([1, 0, 0, HardwareTypes.UNKNOWN.value, 0, 0, 0, 0]),
        )

        mock_device = MagicMock()
        check_for_device_update(mock_device, device_version)

        mock_get.assert_called()
        mock_compare.assert_called_once_with("1.0.0", "2.0.0")
        mock_upgrade.assert_not_called()

    @patch("mutenix.updates.requests.get")
    @patch("mutenix.updates.semver.compare")
    def test_check_for_self_update_up_to_date(self, mock_compare, mock_get):
        mock_compare.return_value = 0
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"latest": "1.0.0"}

        check_for_self_update(1, 0, 0)

        mock_get.assert_called_once()
        mock_compare.assert_called_once_with("1.0.0", "1.0.0")

    @patch("mutenix.updates.requests.get")
    @patch("mutenix.updates.semver.compare")
    def test_check_for_self_update_needs_update(self, mock_compare, mock_get):
        mock_compare.return_value = -1
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "latest": "2.0.0",
            "2.0.0": {"url": "http://example.com/update.tar.gz"},
        }

        mock_update_response = MagicMock()
        mock_update_response.status_code = 200
        mock_update_response.content = b"fake content"
        mock_get.side_effect = [mock_get.return_value, mock_update_response]

        with patch("tarfile.open") as mock_tarfile:
            mock_tarfile.return_value.__enter__.return_value.extract = MagicMock()
            check_for_self_update(1, 0, 0)

        mock_get.assert_called()
        mock_compare.assert_called_once_with("1.0.0", "2.0.0")



    @patch("mutenix.updates.hid.device")
    def test_perform_hid_upgrade_success(self, mock_device):
        mock_device_instance = MagicMock()
        mock_device.return_value = mock_device_instance

        mock_device_instance.read.return_value = bytes()

        with patch("mutenix.updates.DATA_TRANSFER_SLEEP_TIME", 0.0001):
            with patch("mutenix.updates.STATE_CHANGE_SLEEP_TIME", 0.0001):
                with patch("builtins.open", mock_open(read_data=b"fake content")):
                    with patch("pathlib.Path.is_file", return_value=True):
                        with patch(
                            "pathlib.Path.open", mock_open(read_data=b"fake content"),
                        ):
                            perform_hid_upgrade(mock_device_instance, ["file1.py", "file2.py", "file3.py"])

        self.assertEqual(
            mock_device_instance.write.call_count, 12,
        )  # 3 files * 3 chunks each + 3 state change commands

    @patch("mutenix.updates.hid.device")
    def test_perform_hid_upgrade_file_not_found(self, mock_device):
        mock_device_instance = MagicMock()
        mock_device.return_value = mock_device_instance

        mock_device_instance.read.side_effect = [
            bytes([82, 81, 1, 0, 0, 0, 0, 0]),  # RequestChunk for first file
            bytes(),  # No more requests
        ]

        with patch("mutenix.updates.DATA_TRANSFER_SLEEP_TIME", 0.0001):
            with patch("mutenix.updates.STATE_CHANGE_SLEEP_TIME", 0.0001):
                with patch("builtins.open", mock_open(read_data=b"fake content")):
                    with patch("pathlib.Path.is_file", return_value=False):
                        with self.assertRaises(FileNotFoundError):
                            perform_hid_upgrade(mock_device_instance, ["file1.py"])

    @patch("mutenix.updates.hid.device")
    def test_perform_hid_upgrade_invalid_identifier(self, mock_device):
        mock_device_instance = MagicMock()
        mock_device.return_value = mock_device_instance

        def read_side_effect(*args):
            def generator():
                yield bytes([81, 81, 1, 0, 0, 0, 0, 0])
                while True:
                    yield bytes()
            return next(generator())

        mock_device_instance.read.side_effect = read_side_effect

        with patch("mutenix.updates.DATA_TRANSFER_SLEEP_TIME", 0.0001):
            with patch("mutenix.updates.STATE_CHANGE_SLEEP_TIME", 0.0001):
                with patch("builtins.open", mock_open(read_data=b"fake content")):
                    with patch("pathlib.Path.is_file", return_value=False):
                        perform_hid_upgrade(mock_device_instance, ["file1.py"])


    @patch("mutenix.updates.hid.device")
    def test_perform_hid_upgrade_invalid_request(self, mock_device):
        mock_device_instance = MagicMock()
        mock_device.return_value = mock_device_instance

        mock_device_instance.read.side_effect = [
            bytes([82, 81, 0, 0, 0, 0, 0, 0]),  # RequestChunk for first file
            bytes([82, 81, 0, 0, 99, 0, 0, 0]),  # Invalid RequestChunk
            bytes(),  # No more requests
            bytes(),  # No more requests
            bytes(),  # No more requests
            bytes(),  # No more requests
        ]

        with patch("mutenix.updates.DATA_TRANSFER_SLEEP_TIME", 0.0001):
            with patch("mutenix.updates.STATE_CHANGE_SLEEP_TIME", 0.0001):
                with patch("builtins.open", mock_open(read_data=b"fake content")):
                    with patch("pathlib.Path.is_file", return_value=True):
                        with patch(
                            "pathlib.Path.open", mock_open(read_data=b"fake content"),
                        ):
                            with self.assertRaises(ValueError):
                                perform_hid_upgrade(mock_device_instance, ["file1.py"])

        self.assertEqual(
            mock_device_instance.write.call_count, 3,
        )  # 1 file * 3 chunks
    @patch("mutenix.updates.requests.get")
    def test_check_for_self_update_request_error(self, mock_get):
        mock_get.side_effect = requests.RequestException("Network error")

        with self.assertLogs("mutenix.updates", level="ERROR") as log:
            check_for_self_update(1, 0, 0)

        self.assertIn("Failed to check for application update availability", log.output[0])

    @patch("mutenix.updates.requests.get")
    def test_check_for_self_update_status_code_error(self, mock_get):
        mock_get.return_value.status_code = 500

        with self.assertLogs("mutenix.updates", level="ERROR") as log:
            check_for_self_update(1, 0, 0)

        self.assertIn("Failed to download the release info, status code: 500", log.output[0])
class TestRequestChunk(unittest.TestCase):
    def test_request_chunk_valid(self):
        data = b"RQ" + (1).to_bytes(2, "little") + (2).to_bytes(2, "little") + b"\0" * 2
        chunk = RequestChunk(data)
        self.assertTrue(chunk.is_valid())
        self.assertEqual(chunk.id, 1)
        self.assertEqual(chunk.segment, 2)

    def test_request_chunk_invalid_identifier(self):
        data = b"XX" + (1).to_bytes(2, "little") + (2).to_bytes(2, "little") + b"\0" * 2
        chunk = RequestChunk(data)
        self.assertFalse(chunk.is_valid())

    def test_request_chunk_invalid_length(self):
        data = b"RR" + (1).to_bytes(2, "little") + (2).to_bytes(2, "little")
        chunk = RequestChunk(data)
        self.assertFalse(chunk.is_valid())
        assert str(chunk) == "Invalid Request"

class TestFileChunk(unittest.TestCase):
    def test_file_chunk_packet(self):
        chunk = FileChunk(1, 2, 3, b"content")
        packet = chunk.packet()
        self.assertEqual(packet[:2], (2).to_bytes(2, "little"))
        self.assertEqual(packet[2:4], (1).to_bytes(2, "little"))
        self.assertEqual(packet[4:6], (3).to_bytes(2, "little"))
        self.assertEqual(packet[6:8], (2).to_bytes(2, "little"))
        self.assertEqual(packet[8:16], b"content" + b"\0")

class TestFileStart(unittest.TestCase):
    def test_file_start_packet(self):
        start = FileStart(1, 0, 3, "test.py", 100)
        packet = start.packet()
        self.assertEqual(packet[:2], (1).to_bytes(2, "little"))
        self.assertEqual(packet[2:4], (1).to_bytes(2, "little"))
        self.assertEqual(packet[4:6], (3).to_bytes(2, "little"))
        self.assertEqual(packet[6:8], (0).to_bytes(2, "little"))
        self.assertEqual(packet[8:9], bytes((7,)))
        self.assertEqual(packet[9:19], b"test.py" + bytes((2,)) + (100).to_bytes(2, "little"))

class TestFileEnd(unittest.TestCase):
    def test_file_end_packet(self):
        end = FileEnd(1)
        packet = end.packet()
        self.assertEqual(packet[:2], (3).to_bytes(2, "little"))
        self.assertEqual(packet[2:4], (1).to_bytes(2, "little"))
        self.assertEqual(packet[4:], b"\0" * (MAX_CHUNK_SIZE + 4))

class TestTransferFile(unittest.TestCase):
    def setUp(self):
        self.file_content = b"fake content" * 10
        self.file_path = "test_file.py"
        with open(self.file_path, "wb") as f:
            f.write(self.file_content)

    def tearDown(self):
        os.remove(self.file_path)

    def test_transfer_file_chunks(self):
        transfer_file = TransferFile(1, self.file_path)
        self.assertEqual(transfer_file.size, len(self.file_content))
        self.assertEqual(len(transfer_file._chunks), transfer_file.chunks)

    def test_transfer_file_get_next_chunk(self):
        transfer_file = TransferFile(1, self.file_path)
        chunk = transfer_file.get_next_chunk()
        self.assertIsInstance(chunk, Chunk)

    def test_transfer_file_get_chunk(self):
        transfer_file = TransferFile(1, self.file_path)
        request_chunk = RequestChunk(b"RQ" + (1).to_bytes(2, "little") + (0).to_bytes(2, "little") + b"\0" * 2)
        chunk = transfer_file.get_chunk(request_chunk)
        self.assertIsInstance(chunk, Chunk)

    def test_transfer_file_is_complete(self):
        transfer_file = TransferFile(1, self.file_path)
        while not transfer_file.is_complete():
            transfer_file.get_next_chunk()
        self.assertTrue(transfer_file.is_complete())

    def test_transfer_file_from_path(self):
        transfer_file = TransferFile(1, pathlib.Path(self.file_path))
        self.assertEqual(transfer_file.filename, "test_file.py")
        self.assertEqual(transfer_file.size, len(self.file_content))

if __name__ == "__main__":
    unittest.main()
