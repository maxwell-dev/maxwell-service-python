import logging
import functools
from typing import Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import maxwell.protocol.maxwell_protocol_pb2 as protocol_types
import maxwell.protocol.maxwell_protocol as protocol

logger = logging.getLogger(__name__)


class App(FastAPI):
    def __init__(self, *args: Any, **kwargs: Any):
        super(App, self).__init__(*args, **kwargs)
        self.__ws_routes = {}
        self.__init_ws()

    def ws(self, path):
        def decorator(func):
            @functools.wraps(func)
            def func_wrapper(*args, **kwargs):
                value = func(*args, **kwargs)
                return value

            self.__ws_routes[path] = func_wrapper
            return func_wrapper

        return decorator

    def get_ws_routes(self):
        return self.__ws_routes

    def get_handler(self, path):
        return self.__ws_routes.get(path)

    def __init_ws(self):
        @self.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            try:
                while True:
                    data = await websocket.receive_bytes()
                    msg = protocol.decode_msg(data)
                    if msg.__class__ == protocol_types.req_req_t:
                        handler = self.get_handler(msg.path)
                        if handler is not None:
                            logger.debug("Received msg: %s", msg)
                            rep = protocol_types.req_rep_t()
                            rep.payload = handler()
                            rep.conn0_ref = msg.conn0_ref
                            rep.ref = msg.ref
                            await websocket.send_bytes(protocol.encode_msg(rep))
                        else:
                            logger.error("Unknown path: %s", msg.path)
                            rep = protocol_types.error2_rep_t()
                            rep.code = 1
                            rep.desc = "Unknown path: %s" % msg.path
                            rep.conn0_ref = msg.conn0_ref
                            rep.ref = msg.ref
                            await websocket.send_bytes(protocol.encode_msg(rep))
                    elif msg.__class__ == protocol_types.ping_req_t:
                        rep = protocol_types.ping_rep_t()
                        rep.ref = msg.ref
                        await websocket.send_bytes(protocol.encode_msg(rep))
                    else:
                        logger.error("Received unknown msg: %s", msg)
            except WebSocketDisconnect:
                logger.warning("Connection was closed.")
