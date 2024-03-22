import asyncio
from enum import Enum
import functools
import inspect
import json
import traceback
import threading
import signal
from typing import TypeAlias, override
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__ws_routes = {}
        self.__routes_lock = threading.Lock()
        self.__on_routes_change_callback = lambda *args, **kwargs: None
        self.__running = False

        signal.signal(signal.SIGINT, self.__signal_handler)
        self.__add_websocket_endpoint()

    def ws(self, path):
        def decorator(func):
            @functools.wraps(func)
            def func_wrapper(*args, **kwargs):
                value = func(*args, **kwargs)
                return value

            with self.__routes_lock:
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

            with self.__routes_lock:
                self.__ws_routes[path] = [
                    func_wrapper,
                    inspect.iscoroutinefunction(func),
                    Version.V1,
                ]
                self.__on_routes_change_callback(Change.ADD, path)

            return func_wrapper

        return decorator

    @override
    def get(self, *args, **kwargs):
        with self.__routes_lock:
            get = super().get(*args, **kwargs)
            self.__on_routes_change_callback(Change.ADD, *args, **kwargs)
        return get

    @override
    def post(self, *args, **kwargs):
        with self.__routes_lock:
            post = super().post(*args, **kwargs)
            self.__on_routes_change_callback(Change.ADD, *args, **kwargs)
        return post

    @override
    def put(self, *args, **kwargs):
        with self.__routes_lock:
            put = super().put(*args, **kwargs)
            self.__on_routes_change_callback(Change.ADD, *args, **kwargs)
        return put

    @override
    def patch(self, *args, **kwargs):
        with self.__routes_lock:
            patch = super().patch(*args, **kwargs)
            self.__on_routes_change_callback(Change.ADD, *args, **kwargs)
        return patch

    @override
    def delete(self, *args, **kwargs):
        with self.__routes_lock:
            delete = super().delete(*args, **kwargs)
            self.__on_routes_change_callback(Change.ADD, *args, **kwargs)
        return delete

    @override
    def head(self, *args, **kwargs):
        with self.__routes_lock:
            head = super().head(*args, **kwargs)
            self.__on_routes_change_callback(Change.ADD, *args, **kwargs)
        return head

    @override
    def options(self, *args, **kwargs):
        with self.__routes_lock:
            options = super().options(*args, **kwargs)
            self.__on_routes_change_callback(Change.ADD, *args, **kwargs)
        return options

    @override
    def trace(self, *args, **kwargs):
        with self.__routes_lock:
            trace = super().trace(*args, **kwargs)
            self.__on_routes_change_callback(Change.ADD, *args, **kwargs)
        return trace

    @override
    def include_router(self, *args, **kwargs):
        with self.__routes_lock:
            include_router = super().include_router(*args, **kwargs)
            self.__on_routes_change_callback(Change.ADD, *args, **kwargs)
        return include_router

    @override
    def mount(self, *args, **kwargs):
        with self.__routes_lock:
            mount = super().mount(*args, **kwargs)
            self.__on_routes_change_callback(Change.ADD, *args, **kwargs)
        return mount

    def visit_routes(self, visit):
        with self.__routes_lock:
            return visit(self.root_path, self.__ws_routes, self.routes)

    def on_routes_change(self, callback):
        self.__on_routes_change_callback = callback

    def __add_websocket_endpoint(self):
        @self.websocket("/$ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            try:
                while self.__running:
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

    def __signal_handler(self, signal, frame):
        logger.info("Signal handler triggered: signal: %s, frame: %s", signal, frame)
        self.__running = False
