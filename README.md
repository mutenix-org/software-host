# Mutenix Host Application

Mutenix is a host application designed to translate the button presses of the hardware device into something usefull.

It consists of basically those parts

- **HID Device Communication**: General communication with the device
- **Update**: Updating the device firmware (via USB HID)
- **Teams Websocket Communication**: Connect with teams using the [local api](#enable-local-api)
- **Virtual Keypad**: Offers a virtual keypad to play around without the hardware.

Mutenix is ideal for software teams looking to enhance their project management and collaboration capabilities.

## Installation

### Executable

Download the executable here: [Releases](https://github.com/mutenix-org/software-host/releases/latest)
Run it.

### Using uv

```bash
uv tool mutenix
```

or

```bash
uvx mutenix
```

## Configuration

Mutenix tries to find a file called `mutenix.yaml` in the directory it is run from or `$HOME/.config/`. It it does not find one, it will create one in the current directory.

The file could be used to configure the action triggered by each of the buttons.

There are are two sections to configure actions:

- `actions`: actions triggered by a single press
- `double_tap_actions`: actions triggered by a double tap on a button

Each of the buttons can be configured in one of the following ways:

```yaml
actions:
- action: send-reaction
  button_id: 4
  extra: like
```

- `action`:
    - Simple action: `mute`, `unmute`, `toggle-mute`, `hide-video`, `show-video`, `toggle-video`, `unblur-background`, `blur-background`, `toggle-background-blur`, `lower-hand`, `raise-hand`, `toggle-hand`, `leave-call`, `toggle-ui`, `stop-sharing`
    - Send Reaction: `send-reaction`, this requires `extra` to be one of: `applause`, `laugh`, `like`, `love`, `wow`
    - Additional Options:
      - `activate-teams` to trigger an action to bring teams into the foreground
      - `cmd` to run an arbitrary command. This is to be used with case, as no check is performed on the output or what command is run. Specify the command in `extra`.
- `button_id`: the id of the buttons, starting with 1
- `extra`: see the actions which require it


## Contributing

### Setting up pre-commit hooks

To set up pre-commit hooks for this project, run the following commands:

```sh
pip install pre-commit
pre-commit install
pre-commit run --all-files
```


## Links

- [Hardware](https://github.com/mutenix-org/hardware-macropad)
- [Firmware](https://github.com/mutenix-org/firmware-macroboard)
