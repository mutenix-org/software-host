# Configuration Documentation

This document provides details on the configuration parameters for Mutenix, including actions, LEDs, keypad, and more.

## Configuration Schema

### Actions

- **actions**: List of button actions.
    - **button_id**: The ID of the button (1-10).
    - **actions**: List of actions to be performed when the button is pressed.
        - **webhook**: The [webhook action](#actiondetails) to be performed.
        - **keyboard**: The [key press action](#keyboard) to be performed.
        - **mouse**: The [mouse action](#actiondetails) to be performed.
        - **teams_reaction**: The [Teams reaction](#actiondetails) to be performed.
        - **meeting_action**: The [meeting action](#actiondetails) to be performed.
        - **activate_teams**: Flag to [activate Teams](#actiondetails) (boolean).
        - **command**: The [command](#actiondetails) to be executed.

### Longpress Action

- **longpress_action**: List of actions to be performed on long press. See [Actions](#actions).

### LEDs

- **leds**: List of LED statuses.
    - **button_id**: The ID of the button (1-10).
    - **teams_state**: The [Teams state](#teams-state) for the LED status.
    - **result_command**: The [command](#result-command) for the LED status (on/off).
    - **color_command**: The [command](#color-command) for the LED status (color).
    - **webhook**: Flag to enable color via [webhook](#webhook) (boolean).
    - **off**: Flag to disable the LED (boolean).

### Teams Token

- **teams_token**: The Teams token.

### Virtual Keypad

- **virtual_keypad**: Configuration for the virtual keypad.
    - **bind_address**: The IP address to bind the virtual keypad server to.
    - **bind_port**: The port number to bind the virtual keypad server to.

### Auto Update

- **auto_update**: Flag to enable auto-update (boolean).

### Device Identifications

- **device_identifications**: List of device identifications.
    - **vendor_id**: The vendor ID of the device.
    - **product_id**: The product ID of the device.
    - **serial_number**: The serial number of the device.

### Logging

- **logging**: Configuration for logging.
    - **level**: The logging level.
    - **submodules**: List of submodules for specific logging configurations.
    - **file_enabled**: Flag to enable logging to a file (boolean).
    - **file_level**: The logging level for the log file.
    - **file_max_size**: The maximum size of the log file in bytes.
    - **file_backup_count**: The number of backup log files to keep.
    - **console_enabled**: Flag to enable logging to the console (boolean).
    - **console_level**: The logging level for the console output.

### Proxy

- **proxy**: The proxy endpoint.

## Definitions

### ActionDetails

- **webhook**: The [webhook action](#webhook) to be performed.
- **keyboard**: The [key press action](#keyboard) to be performed.
- **mouse**: The [mouse action](#mouse) to be performed.
- **teams_reaction**: The [Teams reaction](#teams_reaction) to be performed.
- **meeting_action**: The [meeting action](#meeting_action) to be performed.
- **activate_teams**: Flag to [activate Teams](#activate_teams) (boolean).
- **command**: The [command](#command) to be executed.

### ButtonAction

- **button_id**: The ID of the button (1-10).
- **actions**: List of actions to be performed when the button is pressed.

### DeviceInfo

- **vendor_id**: The vendor ID of the device.
- **product_id**: The product ID of the device.
- **serial_number**: The serial number of the device.

### Keyboard

- **press**: The key press action to be performed.
- **release**: The key release action to be performed.
- **tap**: The key tap action to be performed.
- **type**: The key type action to be performed.


### Mouse

- **move**: The mouse move action to be performed.
    - **x**: The x-coordinate to move the mouse to.
    - **y**: The y-coordinate to move the mouse to.
- **click**: The mouse click action to be performed.
    - **button**: The mouse button to click (left, right, middle).
- **scroll**: The mouse scroll action to be performed.
    - **direction**: The direction to scroll (up, down, left, right).
    - **amount**: The amount to scroll.

### Webhook

- **url**: The URL to send the webhook request to.
- **method**: The HTTP method to use for the webhook request (GET, POST, etc.).
- **headers**: The headers to include in the webhook request.
- **data**: The data to include in the webhook request.
- **timeout**: The timeout for the webhook request in seconds.
- **retry**: The number of times to retry the webhook request in case of failure.

### TeamsReaction

- **reaction**: The reaction to be performed (like, love, laugh, etc.).

### MeetingAction

- **toggle-mute**: Toggle the mute state.
- **leave-call**: Leave the current call.
- **toggle-video**: Toggle the video state.

### ActivateTeams

- **activate_teams**: Flag to activate Teams (boolean).

### Command

- **command**: The command to be executed.
- **interval**: The interval between command executions in seconds.
- **timeout**: The timeout for the command execution in seconds.

### LedStatus

- **button_id**: The ID of the button (1-10).
- **teams_state**: The [Teams state](#teams-state) for the LED status.
- **result_command**: The [command](#result-command) for the LED status (on/off).
- **color_command**: The [command](#color-command) for the LED status (color).
- **webhook**: Flag to enable color via [webhook](#webhook) (boolean).
- **off**: Flag to disable the LED (boolean).

### LoggingConfig

- **level**: The logging level.
- **submodules**: List of submodules for specific logging configurations.
  ```
  submodules:
    - "mutenix.hid_device=debug"
    - "mutenix.web_server=warning"
  ```
- **file_enabled**: Flag to enable logging to a file (boolean).
- **file_path**: The file path for the log file.
- **file_level**: The logging level for the log file.
- **file_max_size**: The maximum size of the log file in bytes.
- **file_backup_count**: The number of backup log files to keep.
- **console_enabled**: Flag to enable logging to the console (boolean).
- **console_level**: The logging level for the console output.

### VirtualKeypadConfig

- **bind_address**: The IP address to bind the virtual keypad server to.
- **bind_port**: The port number to bind the virtual keypad server to.


## Example

```yaml
# Example configuration for Mutenix
actions:
- actions:
  - meeting_action: toggle-mute
  button_id: 1
- actions:
  - mouse:
      set:
        x: 200
        y: 400
  button_id: 2
- actions:
  - keyboard:
      tap:
        key: 'P'
        modifiers:
          - ctrl
          - shift
  button_id: 3
- actions:
  - teams_reaction:
      reaction: like
  button_id: 4
- actions:
  - meeting_action: leave-call
  button_id: 5
- actions:
  - webhook:
      url: https://webhook.pb42.de/d365dd04-2a0e-4e08-992e-eed4315c2feb
      method: GET
      headers:
        X-Auth: "12345"
      data: {"key": "value"}
  button_id: 6
- actions:
   - command: echo "Hello, World!"
  button_id: 7
- actions:
  - activate_teams: true
  button_id: 8
- actions:
  - teams_reaction:
      reaction: like
  button_id: 9
- actions:
  - meeting_action: leave-call
  button_id: 10
leds:
- button_id: 1
  teams_state:
    color_off: red
    color_on: green
    teams_state: is-muted
- button_id: 2
  teams_state:
    color_off: black
    color_on: yellow
    teams_state: is-hand-raised
- button_id: 3
  teams_state:
    color_off: red
    color_on: green
    teams_state: is-video-on
- button_id: 4
  color_command:
    command: echo blue
    interval: 5.0
    timeout: 0.5
- button_id: 5
  result_command:
    command: echo blue
    interval: 5.0
    timeout: 0.5
    color_on: pink
    color_off: blue
- button_id: 6
  teams_state:
    color_off: green
    color_on: red
    teams_state: is-muted
- button_id: 7
  teams_state:
    color_off: black
    color_on: yellow
    teams_state: is-hand-raised
- button_id: 8
  teams_state:
    color_off: green
    color_on: red
    teams_state: is-video-on
- button_id: 10
  teams_state:
    color_off: black
    color_on: green
    teams_state: is-in-meeting
longpress_action:
- actions:
  - meeting_action: toggle-video
  button_id: 3
- actions:
  - meeting_action: toggle-video
  button_id: 8
teams_token: new_token
virtual_keypad:
  bind_address: 127.0.0.1
  bind_port: 12909

# yaml-language-server: $schema=https://github.com/mutenix-org/software-host/raw/refs/heads/main/docs/mutenix.schema.json

```
