// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
const ws = new WebSocket('ws://' + window.location.host + '/ws');
function requestState() {
    //ws.send(JSON.stringify({ command: "state_request"}));
}
ws.onmessage = function (event) {
    const data = JSON.parse(event.data);
    const indicators = document.getElementsByClassName('indicator' + data.button);
    for (let i = 0; i < indicators.length; i++) {
        indicators[i].style.backgroundColor = data.color;
    }
};
function sendButtonPress(button) {
    if (ws.readyState == WebSocket.OPEN) {
        ws.send(JSON.stringify({ command: "button", button: button }));
        console.log('sent button press' + button);
    } else {
        console.log('WebSocket not open');
    }
}
ws.onopen = function () {
    requestState();
};
ws.onclose = function () {
    console.log('WebSocket connection closed');
};
window.onblur = function () {
    requestState();
};
window.onfocus = function () {
    requestState();
};
