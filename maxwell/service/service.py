import asyncio
import logging
import functools
import inspect
from typing import Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import maxwell.protocol.maxwell_protocol_pb2 as protocol_types
import maxwell.protocol.maxwell_protocol as protocol

from maxwell.service.registrar import Registrar

logger = logging.getLogger(__name__)


class Service(FastAPI):
    def __init__(self, *args: Any, **kwargs: Any):
        super(Service, self).__init__(*args, **kwargs)
        self.__is_registered = False
        self.__ws_routes = {}
        self.__init_ws()

    def register(self):
        if self.__is_registered is False:
            self.__is_registered = True
        return self

    def is_registered(self):
        return self.__is_registered

    def ws(self, path):
        def decorator(func):
            @functools.wraps(func)
            def func_wrapper(*args, **kwargs):
                value = func(*args, **kwargs)
                return value

            self.__ws_routes[path] = [func_wrapper, inspect.iscoroutinefunction(func)]
            return func_wrapper

        return decorator

    def get_ws_routes(self):
        return self.__ws_routes

    def get_paths(self):
        return list(self.__ws_routes.keys())

    def get_handler(self, path):
        return self.__ws_routes.get(path)

    def __init_ws(self):
        @self.websocket("/$ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            try:
                while True:
                    data = await websocket.receive_bytes()
                    asyncio.ensure_future(self.__handle_msg(websocket, data))
            except WebSocketDisconnect:
                logger.warning("Connection was closed.")

    async def __handle_msg(self, websocket, data):
        try:
            req = protocol.decode_msg(data)
            if req.__class__ == protocol_types.req_req_t:
                handler = self.get_handler(req.path)
                if handler is not None:
                    logger.debug("Received msg: %s", req)
                    rep = protocol_types.req_rep_t()
                    if handler[1] is True:
                        rep.payload = await handler[0](req)
                    else:
                        rep.payload = handler[0](req)
                    rep.conn0_ref = req.conn0_ref
                    rep.ref = req.ref
                    await websocket.send_bytes(protocol.encode_msg(rep))
                else:
                    logger.error("Unknown path: %s", req.path)
                    rep = protocol_types.error2_rep_t()
                    rep.code = protocol_types.error_code_t.UNKNOWN_PATH
                    rep.desc = "Unknown path: %s" % req.path
                    rep.conn0_ref = req.conn0_ref
                    rep.ref = req.ref
                    await websocket.send_bytes(protocol.encode_msg(rep))
            elif req.__class__ == protocol_types.ping_req_t:
                rep = protocol_types.ping_rep_t()
                rep.ref = req.ref
                await websocket.send_bytes(protocol.encode_msg(rep))
            else:
                logger.error("Received unknown msg: %s", req)
        except Exception:
            logger.warning("Failed to handle msg: %s", req)
