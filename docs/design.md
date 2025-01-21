# Design

The design of the mutenix host software consists of the following parts:

- **macropad**: The central connecting element, including the business logic.
- **hid_device**: Handles the connection to the device, reading writing, triggering the device update
- **tray_icon**: The tray icon and its handlers
- **updates**: checks for updates of the host information and performs the device update
- **virtual_macropad**: Handling the virtual macropad, an extension to the web_server
- **web_server**: for providing the virtual macropad and an endpoint for setting the leds
- **websocker_client**: The connection to teams, handling sending and receiving of messages.
