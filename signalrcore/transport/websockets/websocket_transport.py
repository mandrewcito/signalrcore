import websocket
import threading
import requests
import traceback
import time
import queue
import ssl
from typing import List, Any, Tuple
from .connection import ConnectionState
from ...hub.errors import HubError, HubConnectionError, UnAuthorizedHubError
from ...protocol.messagepack_protocol import MessagePackHubProtocol
from ..base_transport import BaseTransport
from ...helpers import Helpers


class WebsocketTransport(BaseTransport):
    def __init__(
            self,
            url="",
            headers=None,
            keep_alive_interval=15,
            reconnection_handler=None,
            verify_ssl=False,
            skip_negotiation=False,
            enable_trace=False,
            **kwargs):
        super(WebsocketTransport, self).__init__(**kwargs)
        self._ws = None
        self.enable_trace = enable_trace
        self._thread = None
        self.skip_negotiation = skip_negotiation
        self.url = url
        if headers is None:
            self.headers = dict()
        else:
            self.headers = headers
        self.handshake_received = False
        self.token = None  # auth
        self.connection_alive = False
        self._thread = None
        self._ws = None
        self.verify_ssl = verify_ssl
        self.keep_alive_interval = keep_alive_interval
        self.reconnection_handler = reconnection_handler

        if len(self.logger.handlers) > 0:
            websocket.enableTrace(self.enable_trace, self.logger.handlers[0])
        
        self.state = WsDisconnectedState(self)
        self.queue = queue.Queue(maxsize=1000)
        self.lock = threading.Lock()
        
    def change_state(self, state: ConnectionState) -> None:
        states = {
            ConnectionState.connected: WsConnectedState,
            ConnectionState.connecting: WsConnectingState,
            ConnectionState.disconnected: WsDisconnectedState
        }

        self.state: WsBaseState

        self.state.on_exit()
        del self.state

        self.state = states[state](self)
        self.state.on_enter()
        
    def is_running(self):
        return self.state != ConnectionState.disconnected

    def dispose(self):
        if self._ws is not None:
            self._ws.on_close = None
            self._ws.on_open = None
            self._ws.on_error = None
            self._ws.close()
            self._ws = None
            self._thread = None
        
    def stop(self):
        return self.state.stop()

    def _stop(self):
        self.logger.debug("Websocket.stop state={0}, ".format(self.state))
        if self._ws is not None:
            self._ws.close()

    def start(self) -> bool:
        return self.state.start()
    
    def _start(self) -> bool:
        self.logger.debug("Websocket.start state={0}".format(self.state))

        if not self.skip_negotiation:
            self.negotiate()

        self.logger.debug("start url:" + self.url)

        self._ws = websocket.WebSocketApp(
            self.url,
            header=self.headers,
            on_message=self.on_message,
            on_error=self.on_socket_error,
            on_close=self.on_close,
            on_open=self.on_open,
            )
        try:
            self._thread = threading.Thread(
                target=lambda: self._ws.run_forever(
                    sslopt={"cert_reqs": ssl.CERT_NONE}
                    if not self.verify_ssl else {}
                ))
            self._thread.daemon = True
            self._thread.start()
        except Exception as ex:
            self.logger.error(ex)
            return False
        return True

    def negotiate(self):
        negotiate_url = Helpers.get_negotiate_url(self.url)
        self.logger.debug("Negotiate url:{0}".format(negotiate_url))

        response = requests.post(
            negotiate_url, headers=self.headers, verify=self.verify_ssl)
        self.logger.debug(
            "Response status code: {0}".format(response.status_code))

        if response.status_code != 200:
            raise HubError(response.status_code)\
                if response.status_code != 401 else UnAuthorizedHubError()

        data = response.json()

        if "connectionId" in data.keys():
            self.url = Helpers.encode_connection_id(
                self.url, data["connectionId"])
        
        # Azure
        if 'url' not in data.keys() or 'accessToken' not in data.keys():
            return 
        
        Helpers.get_logger().debug(
            "Azure url, reformat headers, token and url {0}".format(data))
        self.url = data["url"]\
            if data["url"].startswith("ws") else\
            Helpers.http_to_websocket(data["url"])
        self.token = data["accessToken"]
        self.headers = {"Authorization": "Bearer " + self.token}

    def on_open(self, _):
        self.state.on_open()

    def on_close(self, callback, close_status_code=None, close_reason=None):
        is_app_closing = type(callback) is websocket.WebSocketApp
        has_no_params = close_status_code is None and close_reason is None
        try:
            if is_app_closing and has_no_params:
                self.state.on_close(
                    callback,
                    close_reason
                )
            else:
                self.state.on_error(
                    callback,
                    close_status_code,
                    close_reason
                )
        except Exception as ex:
            self.logger.error(ex)
            raise ex

    def on_socket_error(self, app, error):
        """
        Args:
            _: Required to support websocket-client version
                equal or greater than 0.58.0
            error ([type]): [description]

        Raises:
            HubError: [description]
        """
        self.state.on_error(app, error, None)

    def on_message(self, app, raw_message):
        try:
            self.state.on_message(app, raw_message)
        except Exception as ex:
            self.logger.error(ex)
            raise ex
        
    def send(self, message):
        return self.state.send(message)

    def _send(self, message):
        self.logger.debug("Sending message {0}".format(message))
        if self._ws is None:
            self.logger.warning("Cant send message, ws is disposed")
            return None
        try:
            self._ws.send(
                self.protocol.encode(message),
                opcode=0x2
                if type(self.protocol) is MessagePackHubProtocol else
                0x1)
            if self.reconnection_handler is not None:
                self.reconnection_handler.reset()
        except websocket._exceptions.WebSocketConnectionClosedException as ex:
            self.state.on_close(self._ws, ex)
        except OSError as ex:
            self.state.on_error(self._ws, -1, str(ex))
        except Exception as ex:
            raise ex


class WsBaseState(object):

    state: ConnectionState

    def __init__(self, context: WebsocketTransport) -> None:
        self.context = context
        self.logger = Helpers.get_logger()

    def start(self) -> None:
        raise NotImplementedError()
    
    def stop(self) -> None:
        raise NotImplementedError()

    def on_enter(self) -> None:
        self.logger.debug(f"Entering state {self.state}")
    
    def on_exit(self) -> None:
        self.logger.debug(f"Exiting state {self.state}")
        
    def send(self, message):
        raise NotImplementedError()
    
    def on_open(self):
        raise NotImplementedError()
    
    def on_message(self, app, raw_message):
        raise NotImplementedError()

    def on_close(self, app: websocket.WebSocketApp, exc: websocket.WebSocketConnectionClosedException):
        raise NotImplementedError()

    def stop(self) -> None:
        self.context._stop()
        self.context.change_state(ConnectionState.disconnected)

    def on_error(self, app, code, reason): 
        self.logger.debug("-- web socket error --")
        self.logger.error(traceback.format_exc(10, True))
        self.logger.error("Websocket raises error: {0} {1}".format(code, reason))
        self.context.change_state(ConnectionState.disconnected)

class WsConnectedState(WsBaseState):

    state: ConnectionState = ConnectionState.connected

    def __init__(self, context: WebsocketTransport) -> None:
        super().__init__(context)

    def start(self) -> None:
        self.logger.warning("Already connected unable to start")
        return False

    def on_open(self):
        self.logger.error("on_open called on connected state")
        
    def send(self, message):
        return self.context._send(message)
        
    def on_message(self, app, raw_message):
        self.logger.debug("Message received {0}".format(raw_message))
        return self.context._on_message(
            self.context.protocol.parse_messages(raw_message))

    def on_close(self, app: websocket.WebSocketApp, exc: websocket.WebSocketConnectionClosedException):
        self.logger.debug("-- web socket close --")
        self.logger.debug(exc)
        self.context.change_state(ConnectionState.disconnected)
    
    def on_enter(self) -> None:
        self.logger.info("Sending queued messages")
        while not self.context.queue.empty():
            message = self.context.queue.get()
            self.send(message)
        super().on_enter()
            
class WsConnectingState(WsBaseState):

    state: ConnectionState = ConnectionState.connecting

    def __init__(self, context: WebsocketTransport) -> None:
        super().__init__(context)

    def send(self, message):
        self.logger.warning("Enqueue message, waiting for conneciton")
        self.context.queue.put(message)

    def start(self):
        self.logger.warning("Cant start, state connecting.")
        return False
    
    def on_open(self):
        self.logger.debug("-- web socket open --")
        msg = self.context.protocol.handshake_message()
        self.context._send(msg)

    def evaluate_handshake(self, message) -> Tuple[bool, List[Any]]:
        self.logger.debug("Evaluating handshake {0}".format(message))
        msg, messages = self.context.protocol.decode_handshake(message)
        
        if msg.error is None or msg.error == "":
            return True, messages
        
        self.logger.error(msg.error)
        return False, messages

    def on_message(self, app, raw_message):
        self.logger.debug("Message received {0}".format(raw_message))
        result, messages = self.evaluate_handshake(raw_message)

        if result and self.context._on_open is not None and callable(self.context._on_open):
            try:
                self.context._on_open()
            except Exception as ex:
                self.logger.error(ex)

            self.context.change_state(ConnectionState.connected)

            if len(messages) > 0:
                return self.context._on_message(messages)

            return []
        else:
            self.context.change_state(ConnectionState.disconnected)

        return self.context._on_message(
            self.context.protocol.parse_messages(raw_message))

    def on_enter(self) -> None:
        super(WsConnectingState, self).on_enter()

    def on_exit(self) -> None:
        super().on_exit()
        
    def on_close(self, app: websocket.WebSocketApp, exc: websocket.WebSocketConnectionClosedException):
        self.logger.debug("-- web socket close --")
        self.logger.debug(exc)
        self.context.change_state(ConnectionState.disconnected)

class WsDisconnectedState(WsBaseState):

    state: ConnectionState = ConnectionState.disconnected

    def __init__(self, context: WebsocketTransport) -> None:
        super().__init__(context)
    
    def start(self) -> bool:
        result = self.context._start()
        self.context.change_state(ConnectionState.connecting)
        return result
    
    def on_open(self):
        self.logger.error("on_open called on disconnected state")

    def on_exit(self) -> None:
        super().on_exit()
        
    def send(self, message):
        raise HubConnectionError("Can not send messages, state disconnected.")
    
    def on_message(self, app, raw_message):
        raise HubConnectionError("I'm disconnected, why am i receiving messages?")
    
    def on_enter(self) -> None:
        super(WsDisconnectedState, self).on_enter()
        try:
            if self.context._on_close is not None and callable(self.context._on_close):
                self.context._on_close()
        except Exception as ex:
            self.logger.error(ex)
            
        if self.context.reconnection_handler is not None:
            self.handle_reconnect()

    def on_reconnect(self):
        self.logger.debug("-- web socket reconnecting --")

    def handle_reconnect(self, sleep: int = 5) -> None:
        if sleep:
            time.sleep(sleep)


        self.context.reconnection_handler.reconnecting = True

        try:
            self.context.dispose()
            self.context._start()
            self.context.change_state(ConnectionState.connecting)
        except Exception as ex:
            self.logger.error(ex)
            sleep_time = self.context.reconnection_handler.next()
            threading.Thread(
                target=self.handle_reconnect,
                args=(sleep_time,)
            ).start()
            
    def on_close(self, app: websocket.WebSocketApp, exc: websocket.WebSocketConnectionClosedException):
        self.logger.warning("-- web already socket closed --")