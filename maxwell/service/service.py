import asyncio
from enum import Enum
import functools
import inspect
import json
import traceback
import threading
from typing import Any, TypeAlias
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from maxwell.utils.logger import get_logger
import maxwell.protocol.maxwell_protocol_pb2 as protocol_types
import maxwell.protocol.maxwell_protocol as protocol

logger = get_logger(__name__)


class Change(Enum):
    ADD = 1


class Version(Enum):
    V0 = 0
    V1 = 1


Request: TypeAlias = protocol_types.req_req_t


class Reply:
    def __init__(self, code: int = 0, desc: str = "", payload: str = ""):
        self.code = code
        self.desc = desc
        self.payload = payload


class Service(FastAPI):
    def __init__(self, *args: Any, **kwargs: Any):
        super(Service, self).__init__(*args, **kwargs)
        self.__ws_routes = {}
        self.__ws_routes_lock = threading.Lock()
        self.__on_routes_change_callback = lambda *args, **kwargs: None
        self.__on_ws_msg()

    def ws(self, path):
        def decorator(func):
            @functools.wraps(func)
            def func_wrapper(*args, **kwargs):
                value = func(*args, **kwargs)
                return value

            with self.__ws_routes_lock:
                self.__ws_routes[path] = [
                    func_wrapper,
                    inspect.iscoroutinefunction(func),
                    Version.V0,
                ]
                self.__on_routes_change_callback(Change.ADD, path)

            return func_wrapper

        return decorator

    def add_ws_route(self, path):
        def decorator(func):
            @functools.wraps(func)
            def func_wrapper(*args, **kwargs):
                value = func(*args, **kwargs)
                return value

            with self.__ws_routes_lock:
                self.__ws_routes[path] = [
                    func_wrapper,
                    inspect.iscoroutinefunction(func),
                    Version.V1,
                ]
                self.__on_routes_change_callback(Change.ADD, path)

            return func_wrapper

        return decorator

    def get_ws_routes(self):
        with self.__ws_routes_lock:
            return self.__ws_routes

    def get_paths(self):
        with self.__ws_routes_lock:
            return list(self.__ws_routes.keys())

    def on_routes_change(self, callback):
        self.__on_routes_change_callback = callback

    def __on_ws_msg(self):
        @self.websocket("/$ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            try:
                while True:
                    data = await websocket.receive_bytes()
                    asyncio.ensure_future(self.__handle_msg(websocket, data))
            except WebSocketDisconnect as e:
                logger.warning("Connection was closed: %s", e)
            except Exception:
                logger.error(
                    "Failed to handle data: %s, error: %s", data, traceback.format_exc()
                )

    async def __handle_msg(self, websocket, data):
        try:
            req = protocol.decode_msg(data)
            if req.__class__ == protocol_types.req_req_t:
                logger.debug("Received msg: %s", req)
                handler = self.__ws_routes.get(req.path)
                if handler is not None:
                    handle, is_coroutine, version = handler
                    if version == Version.V1:
                        if is_coroutine is True:
                            userland_rep: Reply = await handle(req)
                        else:
                            userland_rep: Reply = handle(req)
                        if userland_rep.code == protocol_types.error_code_t.OK:
                            rep = protocol_types.req_rep_t()
                            rep.payload = json.dumps(userland_rep.payload)
                            rep.conn0_ref = req.conn0_ref
                            rep.ref = req.ref
                            await websocket.send_bytes(protocol.encode_msg(rep))
                        else:
                            rep = protocol_types.error2_rep_t()
                            rep.code = userland_rep.code
                            rep.desc = userland_rep.desc
                            rep.conn0_ref = req.conn0_ref
                            rep.ref = req.ref
                            await websocket.send_bytes(protocol.encode_msg(rep))
                    elif version == Version.V0:
                        rep = protocol_types.req_rep_t()
                        if is_coroutine is True:
                            rep.payload = await handle(req)
                        else:
                            rep.payload = handle(req)
                        rep.conn0_ref = req.conn0_ref
                        rep.ref = req.ref
                        await websocket.send_bytes(protocol.encode_msg(rep))
                    else:
                        raise SystemExit("Unknown version: %s" % version)
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
            logger.error(
                "Failed to handle msg: %s, error: %s", req, traceback.format_exc()
            )
