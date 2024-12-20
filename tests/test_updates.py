import unittest
from unittest.mock import patch, MagicMock, mock_open
from mutenix.updates import check_for_device_update, check_for_self_update, VersionInfo, perform_hid_upgrade
from mutenix.hid_commands import HardwareTypes


class TestUpdates(unittest.TestCase):
    @patch("mutenix.updates.requests.get")
    @patch("mutenix.updates.semver.compare")
    def test_check_for_device_update_up_to_date(self, mock_compare, mock_get):
        mock_compare.return_value = 0
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"latest": "1.0.0"}
        device_version = VersionInfo(
            buffer=bytes([1, 0, 0, HardwareTypes.UNKNOWN.value, 0, 0, 0, 0])
        )
        mock_device = MagicMock()
        check_for_device_update(mock_device, device_version)

        mock_get.assert_called_once()
        mock_compare.assert_called_once_with("1.0.0", "1.0.0")

    @patch("mutenix.updates.requests.get")
    @patch("mutenix.updates.semver.compare")
    @patch("mutenix.updates.perform_hid_upgrade")
    def test_check_for_device_update_needs_update(
        self, mock_upgrade, mock_compare, mock_get
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
            buffer=bytes([1, 0, 0, HardwareTypes.UNKNOWN.value, 0, 0, 0, 0])
        )
        with patch("tarfile.open") as mock_tarfile:
            mock_tarfile.return_value.__enter__.return_value.extractall = MagicMock()
            mock_device = MagicMock()
            check_for_device_update(mock_device, device_version)

        mock_get.assert_called()
        mock_compare.assert_called_once_with("1.0.0", "2.0.0")
        mock_upgrade.assert_called_once()

    @patch("mutenix.updates.requests.get")
    @patch("mutenix.updates.semver.compare")
    def test_check_for_self_update_up_to_date(self, mock_compare, mock_get):
        mock_compare.return_value = 0
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"latest": "1.0.0"}

        with patch("mutenix.updates.__version__", "1.0.0"):
            check_for_self_update()

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

        with patch("mutenix.updates.__version__", "1.0.0"):
            with patch("tarfile.open") as mock_tarfile:
                mock_tarfile.return_value.__enter__.return_value.extract = MagicMock()
                check_for_self_update()

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
                            "pathlib.Path.open", mock_open(read_data=b"fake content")
                        ):
                            perform_hid_upgrade(mock_device_instance, ["file1.py", "file2.py", "file3.py"])

        self.assertEqual(
            mock_device_instance.write.call_count, 12
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
                            "pathlib.Path.open", mock_open(read_data=b"fake content")
                        ):
                            with self.assertRaises(ValueError):
                                perform_hid_upgrade(mock_device_instance, ["file1.py"])

        self.assertEqual(
            mock_device_instance.write.call_count, 3
        )  # 1 file * 3 chunks


if __name__ == "__main__":
    unittest.main()
