import asyncio
from enum import Enum
from threading import Thread
from starlette.routing import Route, Mount
from fastapi.routing import APIWebSocketRoute, APIRoute
from google.protobuf.json_format import MessageToDict
import maxwell.protocol.maxwell_protocol_pb2 as protocol_types
from maxwell.utils.connection import Event
from maxwell.utils.logger import get_logger

from .config import Config
from .master_client import MasterClient

logger = get_logger(__name__)


class Item(Enum):
    ROUTES = 1
    CANCEL = 2


class Registrar(Thread):
    # ===========================================
    # apis
    # ===========================================
    def __init__(self, service):
        super().__init__()

        self.__service = service

        self.daemon = True

        self.__loop = None
        self.__open_event = None
        self.__queue = None
        self.__master_client = None
        self.__put_routes_item_timer = None
        self.__running = True

    def stop(self):
        self.__running = False

    def run(self):
        logger.info("Starting registrar thread...")

        # init
        self.__loop = asyncio.new_event_loop()
        self.__open_event = asyncio.Event()
        self.__queue = asyncio.Queue()
        self.__master_client = MasterClient(
            Config.singleton().get_master_endpoints(),
            {"reconnect_delay": 1, "ping_interval": 10},
            self.__loop,
        )

        # set routes change listener
        self.__service.on_routes_change(self.__put_routes_item_later)

        # add connection listeners
        self.__master_client.add_connection_listener(
            event=Event.ON_CONNECTED, callback=self.__on_connected_to_master
        )
        self.__master_client.add_connection_listener(
            event=Event.ON_DISCONNECTED, callback=self.__on_disconnected_from_master
        )

        # do real stuff
        self.__loop.run_until_complete(self.__repeat_register_service_and_set_routes())

        # clean up
        self.__master_client.delete_connection_listener(
            event=Event.ON_CONNECTED, callback=self.__on_connected_to_master
        )
        self.__master_client.delete_connection_listener(
            event=Event.ON_DISCONNECTED, callback=self.__on_disconnected_from_master
        )
        self.__loop.run_until_complete(self.__master_client.close())
        if self.__put_routes_item_timer:
            self.__put_routes_item_timer.cancel()
        self.__loop.close()

        logger.info("Finished registrar thread.")

    # ===========================================
    # internal functions
    # ===========================================

    def __put_routes_item_later(self, *argv, **kwargs):
        logger.debug("Put routes item later: argv: %s, kwargs: %s", argv, kwargs)
        if self.__put_routes_item_timer:
            self.__put_routes_item_timer.cancel()
        delay = kwargs.get("delay", Config.singleton().get_set_routes_delay())
        self.__put_routes_item_timer = self.__loop.call_soon_threadsafe(
            self.__loop.call_later, delay, self.__put_routes_item
        )

    def __put_routes_item(self):
        req = self.__service.visit_routes(Registrar.__build_set_routes_req)
        self.__queue.put_nowait((Item.ROUTES, req))

    def __put_cancel_item(self):
        self.__queue.put_nowait((Item.CANCEL, None))

    def __on_connected_to_master(self, *argv, **kwargs):
        self.__open_event.set()
        self.__put_routes_item_later(delay=0)

    def __on_disconnected_from_master(self, *argv, **kwargs):
        self.__open_event.clear()
        self.__put_cancel_item()

    async def __repeat_register_service_and_set_routes(self):
        while self.__running:
            try:
                await self.__open_event.wait()
                await self.__register_service()
                await self.__repeat_set_routes()
            except Exception as e:
                logger.error("Failed to register service and set routes: %s", e)
                await asyncio.sleep(1)

    async def __register_service(self):
        req = Registrar.__build_register_service_req()
        try:
            rep = await self.__master_client.request(req)
            logger.info("Successfully to register service: %s", rep)
        except Exception as e:
            logger.error("Failed to register service: %s", e)
            raise e

    async def __repeat_set_routes(self):
        while self.__running:
            try:
                type, req = await self.__queue.get()
                logger.info(
                    "Got item: type: %s, path bundle: %s",
                    type,
                    MessageToDict(req, preserving_proto_field_name=True),
                )
                if type == Item.ROUTES:
                    await self.__set_routes(req)
                elif type == Item.CANCEL:
                    return
            except Exception as e:
                logger.error("Failed to set routes: %s", e)
                raise e
            finally:
                self.__queue.task_done()

    async def __set_routes(self, req):
        try:
            rep = await self.__master_client.request(req)
            logger.info("Successfully to set routes: %s", rep)
        except Exception as e:
            logger.error("Failed to set routes: %s", e)
            raise e

    @staticmethod
    def __build_register_service_req():
        req = protocol_types.register_service_req_t()
        req.http_port = Config.singleton().get_port()
        return req

    @staticmethod
    def __build_set_routes_req(root_path, ws_routes, routes):
        req = protocol_types.set_routes_req_t()
        for ws_path in ws_routes.keys():
            req.ws_paths.extend([Registrar.__prepend_root_path(root_path, ws_path)])
        for route in routes:
            path = Registrar.__prepend_root_path(root_path, route.path)
            if isinstance(route, APIRoute):
                for method in route.methods:
                    if method == "GET":
                        req.get_paths.extend([path])
                    elif method == "POST":
                        req.post_paths.extend([path])
                    elif method == "PUT":
                        req.put_paths.extend([path])
                    elif method == "PATCH":
                        req.patch_paths.extend([path])
                    elif method == "DELETE":
                        req.delete_paths.extend([path])
                    elif method == "HEAD":
                        req.head_paths.extend([path])
                    elif method == "OPTIONS":
                        req.options_paths.extend([path])
                    elif method == "TRACE":
                        req.trace_paths.extend([path])
                    else:
                        logger.error("Unknown method: %s", method)
            elif isinstance(route, Mount):
                req.get_paths.extend([path.rstrip("/") + "/{*p}"])
            elif isinstance(route, APIWebSocketRoute):
                continue
            elif isinstance(route, Route):
                req.get_paths.extend([path])
            else:
                logger.error("Unknown route: %s", route)
        return req

    @staticmethod
    def __prepend_root_path(root_path, path):
        return root_path.rstrip("/") + "/" + path.lstrip("/")
