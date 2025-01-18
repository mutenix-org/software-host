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

function openPopup() {
const popupWidth = document.getElementById('keypads').offsetWidth+20;
const popupHeight = document.getElementById('keypads').offsetHeight+50;
const popup = window.open('/popup', 'popup', `width=${popupWidth},height=${popupHeight},resizable=no,scrollbars=no,toolbar=no,menubar=no,location=no,status=no`);
}

function activateButton(buttonSelection) {
    const fiveButtonDiv = document.getElementById('five_button');
    const tenButtonDiv = document.getElementById('ten_button');
    if (buttonSelection === 'ten') {
        fiveButtonDiv.style.display = 'none';
        tenButtonDiv.style.display = 'block';
        toggleButton.textContent = 'Show 5 Buttons';
    } else {
        fiveButtonDiv.style.display = 'block';
        tenButtonDiv.style.display = 'none';
        toggleButton.textContent = 'Show 10 Buttons';
    }
    localStorage.setItem('buttonSelection', buttonSelection);
    requestState();
}
function toggleButtons() {
    const fiveButtonDiv = document.getElementById('five_button');
    const tenButtonDiv = document.getElementById('ten_button');
    const toggleButton = document.getElementById('toggleButton');

    if (fiveButtonDiv.style.display === 'none') {
        activateButton('five');
    } else {
        activateButton('ten');
    }
}
