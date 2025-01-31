# Mutenix Host Application

Mutenix is a host application designed to translate the button presses of the hardware device into something usefull.

It consists of basically those parts

- **HID Device Communication**: General communication with the device
- **Update**: Updating the device firmware (via USB HID)
- **Teams Websocket Communication**: Connect with teams using the [local api](#enable-local-api)
- **Virtual Keypad**: Offers a virtual keypad to play around without the hardware.

Mutenix is ideal for software teams looking to enhance their project management and collaboration capabilities.

## Tray Icon & Menu

![images/tray_icon.png]

- **Open Virtual Macroboard**: Opens a virtual Macroboard in the browser, same functionalities as the hardware one.
- **Teams connected**: Status information if teams connection has been established.
- **Device connected**: Status information if the device connection has been established.
- **Help**: Opens the help page in the browser.
- **About**: Opens the about page in the browser.
- **Debug Options**: Set some debug options persistent
  - **Activate Serial Console**: Activates the serial console (Circuitpython)
  - **Deactivate Serial Console**: Deactivates the serial console (Circuitpython)
  - **Enable Filesystem**: Enables the filesystem. This cannot be undone using the tray icon. It has to be done by yourself on the filesystem. The file you need to alter is `debug_on.py`. Reason for this is, that the device cannot mount the drive writeable the same time the host has it mounted.
- **Quit**: Quit Mutenix


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

### Command Line options

**NB**: Command line options may not work on the executable version.

- `--list-devices`: lists HID devices
- `--config <your config file>`: Use that config file
- `--update-file <firmware archive>`: perform an update with that file

## Configuration

Using the configuration file several things could be configured:

- actions of the buttons
- led states/colors
- virtual keypad binding (address and port)
- device identification to connect to

Mutenix tries to find a file called `mutenix.yaml` in the directory it is run from or `$HOME/.config/`. It it does not find one, it will create one in the current directory.


# Actions configuration

The file could be used to configure the action triggered by each of the buttons.

There are are two sections corresponding to trigger types to configure actions:

- `actions`: actions triggered by a single press
- `longpress_actions`: actions triggered by a long press on a button (>400ms)

Each of the buttons can be configured in one of the following ways:

```yaml
actions:
- action: key-press
  button_id: 1
  extra:
    - modifiers: [cmd_l, shift]
      key: p
    - string: Reload Window
    - key: enter
- action: mouse
  button_id: 2
  extra:
    - action: move
      x: 100
      y: 100
    - action: click
      button: left
    - action: move
      x: 200
      y: 200
- action: cmd
  button_id: 3
  extra: net send * Please call me
- action: send-reaction
  button_id: 4
  extra: like
longpress_action:
- action: webhook
  button_id: 5
  extra:
    url: https://some.end.point/wherever
    headers:
      X-Auth: "12345"
    data: {"key": "value"}
```

- `action`:
    - Simple action: `mute`, `unmute`, `toggle-mute`, `hide-video`, `show-video`, `toggle-video`, `unblur-background`, `blur-background`, `toggle-background-blur`, `lower-hand`, `raise-hand`, `toggle-hand`, `leave-call`, `toggle-ui`, `stop-sharing`
    - Send Reaction: `send-reaction`, this requires `extra` to be one of: `applause`, `laugh`, `like`, `love`, `wow`
    - Additional Options:
      - `activate-teams` to trigger an action to bring teams into the foreground
      - `cmd` to run an arbitrary command. This is to be used with case, as no check is performed on the output or what command is run. Specify the command in `extra`.
      - `type`: Type the text in `extra` using keyboard emulation
      - `keypress`: Press keys. In extra you can specify one or many keys or key combinations (can be one or a list)
        - `key`: like 'A', B', ...
        - `modifiers`: with modifiers as `shift`, `alt`, ... see [pynput](https://pynput.readthedocs.io/en/latest/keyboard.html#pynput.keyboard.Key)
        - `string`: a string to type
      - `mouse`: Simulate mouse (can be one or a list)
        - One of the following actions:
          - `action`: `move` (can be omitted), `set`, `click`, `press`, `release`
          - `x`: Relative or Absolute Position
          - `y`: Relative or Absolute Position
          - `button`: Mouse button: `left`, `middle`, `right`
          - `count`: for click, the times to click
      - `webhook` to make a user defined webhook call, make sure `extra has the following information:
        - `url`: the url endpoint
        - `method`: (optional, default: GET) the method to use
        - `data`: (optional) json string to send
        - `headers`: headers to add
- `button_id`: the id of the buttons, starting with 1
- `extra`: see the actions which require it


### LED Configuration

Next section is for the colors of the LED, each LED which is associated with a button can be controlled.

```yaml
leds:
- button_id: 1
  source: teams
  color_off: green
  color_on: red
  extra: is-muted
  interval: 0.0
  read_result: false
```

- `source`:
  - `teams`: based on the information received by the websocket. The following informations are available and could be selected by `extra`: `is-muted`, `is-hand-raised`, `is-in-meeting`, `is-recording-on`, `is-background-blurred`, `is-sharing`, `has-unread-messages`, `is-video-on`
  - `cmd`: A command to execute and take its output/return code.
    - if `read_result` is `false` or not set the exit code will be used so select `color_off` or `color_on`.
    - if `read_result` is `true`, the output of the command will be used. Supported output is one of the colors listed below.
  - `color_on/color_off` define the colors to use in case the state is true or the exit code is 0
  - `interval` the amount of seconds between two checks/runs of the call.

**Supported Colors**: `red`, `green`, `blue`, `white`, `black`, `yellow`, `cyan`, `magenta`, `orange`, `purple`

### Websocket config

- `address`: The bind address.
- `port`: The bind port for the virtual macropad.

### Device Config

```yaml
device_identifications:
-  vendor_id: 12345
   product_id: 1
   serial_number: 9121DB23244
-  vendor_id: 12345
   product_id: 1
   serial_number: 9121DB2324F
```

The settings can configure for which device to look for. If not given it will search for a device with `mutenix` in the `product_string` or the default PID/VID combination.

### Teams Token

After allowing the access to teams, the token is also stored in the file. Changing or deleting requires a reauthentication in teams.


## Teams it not working

In teams the `Third Pary API` must be enabled.

![Privacy Settings in Teams](images/privacy_settings.png)


## Contributing

### Setting up pre-commit hooks

To set up pre-commit hooks for this project, run the following commands:

```sh
pip install pre-commit
pre-commit install
pre-commit run --all-files
```


## Links

- [Hardware](https://github.com/mutenix-org/hardware-macroboard)
- [Firmware](https://github.com/mutenix-org/firmware-macroboard)
