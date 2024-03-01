import asyncio
from enum import Enum
from threading import Thread
import maxwell.protocol.maxwell_protocol_pb2 as protocol_types
from maxwell.utils.connection import Event
from maxwell.utils.logger import get_logger

from .config import Config
from .master_client import MasterClient

logger = get_logger(__name__)


class Item(Enum):
    NORMAL = 1
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
        self.__master_client = None
        self.__queue = asyncio.Queue()
        self.__put_routes_timer = None
        self.__running = True

    def stop(self):
        self.__running = False

    def run(self):
        logger.info("Registrar thread started.")

        # init
        self.__loop = asyncio.new_event_loop()
        self.__open_event = asyncio.Event()
        self.__master_client = MasterClient(
            Config.singleton().get_master_endpoints(),
            {"reconnect_delay": 1, "ping_interval": 10},
            self.__loop,
        )

        # set routes change listener
        self.__service.on_route_change = self.__put_routes_later

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
        if self.__put_routes_timer:
            self.__put_routes_timer.cancel()
        self.__loop.close()

        logger.info("Registrar thread stopped.")

    # ===========================================
    # internal functions
    # ===========================================

    def __put_routes_later(self, *argv, **kwargs):
        if self.__put_routes_timer:
            self.__put_routes_timer.cancel()
        self.__put_routes_timer = self.__loop.call_later(
            Config.singleton().get_set_routes_delay(), self.__try_put_routes
        )

    def __try_put_routes(self):
        paths = self.__service.get_paths()
        if len(paths) > 0:
            self.__queue.put_nowait((Item.NORMAL, paths))

    def __on_connected_to_master(self, *argv, **kwargs):
        self.__open_event.set()
        self.__try_put_routes()

    def __on_disconnected_from_master(self, *argv, **kwargs):
        self.__open_event.clear()
        self.__queue.put_nowait((Item.CANCEL, None))

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
        req = protocol_types.register_service_req_t()
        req.http_port = Config.singleton().get_port()
        try:
            rep = await self.__master_client.request(req)
            logger.info("Successfully to register service: %s", rep)
        except Exception as e:
            logger.error("Failed to register service: %s", e)
            raise e

    async def __repeat_set_routes(self):
        while self.__running:
            try:
                type, paths = await self.__queue.get()
                logger.info("Got item: type: %s, paths: %s", type, paths)
                if type == Item.NORMAL:
                    await self.__set_routes(paths)
                elif type == Item.CANCEL:
                    return
            except Exception as e:
                logger.error("Failed to set routes: %s", e)
                raise e
            finally:
                self.__queue.task_done()

    async def __set_routes(self, paths):
        req = protocol_types.set_routes_req_t()
        req.paths.extend(paths)
        try:
            rep = await self.__master_client.request(req)
            logger.info("Successfully to set routes: %s", rep)
        except Exception as e:
            logger.error("Failed to set routes: %s", e)
            raise e
