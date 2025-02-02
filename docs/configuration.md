# Configuration

Using the configuration file several things could be configured:

- actions of the buttons (press and longpress)
- led states/colors
- virtual keypad binding (address and port)
- device identification to connect to
- logging configuration
- proxy settings
- deactivate auto update

## Config file location

Mutenix tries to find a file called `mutenix.yaml` in some directories in the following order:

- The config path that is specified.
- if no path is specified: `CWD` the directory it is currently running from
- `$HOME/.config/` if no local file found


## Actions

Actions could be triggered by press (actually the release is used as trigger) or longpress (>400 ms).

You can trigger different actions:

- Trigger teams action (while in a meeting)
- Activate Teams
- Commands, run any command
- Keypress, emulate a keypress, combinatino or a sequence of those
- Mouse, emulate mouse movements and clicks
- Webhooks, perform POST, GET, ... requests to any URL

Each action must have a `button_id` to specify the button triggering the action.

### Teams Actions

Teams supports the following actions:

- `mute`: sets mute
- `unmute`: sets unmute
- `toggle-mute`: toggle mute
- `hide-video`: deactivate the video
- `show-video`: activate the video
- `toggle-video`: toggle video
- `unblur-background`: disable background blur
- `blur-background`: enable background blur
- `toggle-background-blur`: toggle the background blur
- `lower-hand`: lower the hand
- `raise-hand`: raise the hand
- `toggle-hand`: toggle the hand
- `leave-call`: exit the call
- `toggle-ui`:
- `stop-sharing`: stops the current sharing
- `send-reaction`: Send a reaction

#### Reactions supported

- `applause`: clapping hands
- `laugh`: laugh smiley
- `like`: thumbs up
- `love`: heart
- `wow`: the other smiley

### Activate teams

Try to activate Teams and bring it to the foreground. Works good on Mac, sometimes on Windows, untested on Linux

### Command

Extra should be a string or a list of strings. The commands will be executed using `subprocess.run`.

### Keypress

Emulates keypresses. Either a single or multiple key presses or a string to be typed.
`extra` shall be a single or a list of keypresses.

```yaml
key: <key>
modifiers: [<mod1>, <mod2>]
```

or

```yaml
string: Some string to type
```

For detals regarding the keys have a look at: [pynput](https://pynput.readthedocs.io/en/latest/keyboard.html#pynput.keyboard.Key)

### Mouse

Emulate mouse movements. Either a list or single entry. It could be relative movement (with `action` set to `move`) or position on absolute coordinates (`action` set to `set`).

Entries supported:

- Relative Movement
  ```yaml
  action: move
  x: 100
  y: 200
  ```
- Absolute Movement
  ```yaml
  action: set
  x: 100
  y: 200
  ```
- Click
  ```yaml
  action: click
  button: <the button>
  count: <number of clicks>
  ```
- Press (and hold) Button
  ```yaml
  action: press
  button: <the button>
  ```
- Release Button
  ```yaml
  action: release
  button: <the button>
  ```

### Webhook

Trigger a webhook. All methods supported. Default is `GET` data is optional.

```yaml
url: http://example.org
method: POST
data: <json string>
headers:
  x-auth: something
```


## LED Configuration

The leds on the device could be set based on multiple sources

- Teams
- a commands result
- a commands output (color)
- web api call

### Sources

- `teams` Use Teams as source
- `cmd` Trigger a call and check
- `webhook`

### Colors

Using teams as source or `read_result = false` the defined colors are used. `color_on` is used if teams returns `true` for the selected option or the command is return `0`.

### Teams

Using teams specify the information used for the led status in the `extra` field.

- `is-muted`
- `is-hand-raised`
- `is-in-meeting`
- `is-recording-on`
- `is-background-blurred`
- `is-sharing`
- `has-unread-messages`
- `is-video-on`


### Command

A command configuration could look like this:

```yaml
source: cmd
color_off: green
color_on: red
extra: ping google.de -c 1
interval: 10.0
read_result: false
```

**Supported Colors**: `red`, `green`, `blue`, `white`, `black`, `yellow`, `cyan`, `magenta`, `orange`, `purple`


### Webhook

If this configuration is selected, you can set the color using a post request to the webserver (default http://127.0.0.1:12909) and the endpoint `/led` with a json body like this:

```json
{
    "button": 1,
    "color": "blue"
}
```

## Websocket config

- `address`: The bind address.
- `port`: The bind port for the virtual macropad.

## Device Config

Configure how to search for the device. There should be no need to change but you can.

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

After allowing the access to teams, the token is also stored in the file. Changing or deleting requires a reauthentication in teams. This rewrites the file.
