from mutenix.hid_commands import Status, VersionInfo, LedColor, SetLed, HidOutCommands

def test_status():
    buffer = bytes([1, 1, 0, 0, 1])
    status = Status(buffer)
    assert status.button == 1
    assert status.triggered is True
    assert status.doubletap is False
    assert status.pressed is False
    assert status.released is True

def test_version_info():
    buffer = bytes([1, 0, 0, 2])
    version_info = VersionInfo(buffer)
    assert version_info.version == "1.0.0"
    assert version_info.type.name == "FIVE_BUTTON_USB"

def test_set_led():
    led = SetLed(1, LedColor.RED)
    buffer = led.to_buffer()
    assert buffer == bytes([HidOutCommands.SET_LED, 1, 0x00, 0x0A, 0x00, 0x00, 0, 0])
