import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from mutenix.websocket_client import WebSocketClient, Identifier
from mutenix.teams_messages import ClientMessage, MeetingAction

@pytest.fixture
def identifier():
    return Identifier(manufacturer="TestManufacturer", device="TestDevice", app="TestApp", app_version="1.0.0", token="test_token")

@pytest.fixture
def websocket_client(identifier):
    return WebSocketClient(uri="ws://testserver", identifier=identifier)

@pytest.mark.asyncio
async def test_connect(websocket_client):
    with patch('websockets.connect', new_callable=AsyncMock) as mock_connect:
        await websocket_client._connect()
        mock_connect.assert_called_once_with("ws://testserver?protocol-version=2.0.0&manufacturer=TestManufacturer&device=TestDevice&app=TestApp&app-version=1.0.0&token=test_token")

@pytest.mark.asyncio
async def test_send_message(websocket_client):

    with patch.object(websocket_client, '_connection', AsyncMock()) as mock_connection:
        asyncio.get_event_loop().create_task(websocket_client._send_loop())
        message = ClientMessage(action=MeetingAction.React ,type="wow")
        f2 = websocket_client.send_message(message)
        await asyncio.sleep(0.02)
        await websocket_client.stop()
        await f2
        mock_connection.send.assert_called_once_with(message.model_dump_json(by_alias=True))

@pytest.mark.asyncio
async def test_receive_message(websocket_client):
    with patch.object(websocket_client, '_connection', AsyncMock()) as mock_connection:
        asyncio.get_event_loop().create_task(websocket_client._receive_loop())
        callback = AsyncMock()
        websocket_client.register_callback(callback)
        mock_connection.recv = AsyncMock(side_effect=['{"errorMsg": "TEST"}', asyncio.CancelledError()])
        await asyncio.sleep(0.001)
        callback.assert_called_once()

@pytest.mark.asyncio
async def test_process(websocket_client):
    future = asyncio.get_event_loop().create_future()
    def set_connection():
        websocket_client._connection = AsyncMock()
        future.set_result(True)
    with patch.object(websocket_client, '_connect', AsyncMock(side_effect=set_connection)) as mock_connect, \
         patch.object(websocket_client, '_send_loop', AsyncMock()) as mock_send_loop, \
         patch.object(websocket_client, '_receive_loop', AsyncMock()) as mock_receive_loop:
        asyncio.get_event_loop().create_task(websocket_client.process())
        await future
        await websocket_client.stop()
        mock_connect.assert_called_once()
        mock_send_loop.assert_called_once()
        mock_receive_loop.assert_called_once()

@pytest.mark.asyncio
async def test_receive_error(websocket_client):
    with patch.object(websocket_client, '_connection', AsyncMock()) as mock_connection:
        asyncio.get_event_loop().create_task(websocket_client._receive_loop())
        callback = AsyncMock()
        websocket_client.register_callback(callback)
        mock_connection.recv = AsyncMock(side_effect=[asyncio.CancelledError()])
        await asyncio.sleep(0.001)
        callback.assert_not_called()

@pytest.mark.asyncio
async def test_receive_exception(websocket_client):
    with patch.object(websocket_client, '_connection', AsyncMock()) as mock_connection:
        asyncio.get_event_loop().create_task(websocket_client._receive_loop())
        callback = AsyncMock()
        websocket_client.register_callback(callback)
        mock_connection.recv = AsyncMock(side_effect=[Exception("TEST")])
        await asyncio.sleep(0.001)
        callback.assert_not_called()

@pytest.mark.asyncio
async def test_send_exception(websocket_client):
    with patch.object(websocket_client, '_connection', AsyncMock()) as mock_connection:
        asyncio.get_event_loop().create_task(websocket_client._send_loop())
        message = ClientMessage(action=MeetingAction.React ,type="wow")
        f2 = websocket_client.send_message(message)
        await asyncio.sleep(0.02)
        await websocket_client.stop()
        await f2
        mock_connection.send.assert_called_once_with(message.model_dump_json(by_alias=True))

@pytest.mark.asyncio
async def test_receive_timeout(websocket_client):
    with patch.object(websocket_client, '_connection', AsyncMock()) as mock_connection:
        asyncio.get_event_loop().create_task(websocket_client._receive_loop())
        callback = AsyncMock()
        websocket_client.register_callback(callback)
        mock_connection.recv = AsyncMock(side_effect=[asyncio.TimeoutError()])
        await asyncio.sleep(0.001)
        callback.assert_not_called()


@pytest.mark.asyncio
async def test_stop(websocket_client):
    with patch.object(websocket_client, '_connection', AsyncMock()) as mock_connection:
        task = asyncio.get_event_loop().create_task(websocket_client._receive_loop())
        await asyncio.sleep(0.001)
        await websocket_client.stop()
        mock_connection.close.assert_called_once()
        while not task.done():
            task.print_stack()
            await asyncio.sleep(0.01)

@pytest.mark.asyncio
async def test_send_connection_exception(websocket_client):
    with patch.object(websocket_client, '_connection', AsyncMock()) as mock_connection:
        websocket_client._connect = AsyncMock()
        mock_connection.recv = AsyncMock(side_effect=asyncio.TimeoutError())
        asyncio.get_event_loop().create_task(websocket_client.process())
        mock_connection.send.side_effect = Exception("TEST")
        message = ClientMessage(action=MeetingAction.React ,type="wow")
        f2 = websocket_client.send_message(message)

        with pytest.raises(Exception):
            await f2
        await websocket_client.stop()
