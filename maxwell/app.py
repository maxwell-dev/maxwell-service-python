from typing import Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import functools


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

    def __init_ws(self):
        @self.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            try:
                while True:
                    data = await websocket.receive_text()
                    await websocket.send_text(f"Message text was: {data}")
            except WebSocketDisconnect:
                pass
