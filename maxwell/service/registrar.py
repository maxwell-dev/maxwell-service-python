import asyncio
import threading
import maxwell.protocol.maxwell_protocol_pb2 as protocol_types
from maxwell.utils.connection import Event
from maxwell.utils.logger import get_logger

from .config import Config
from .master_client import MasterClient

logger = get_logger(__name__)


class Registrar(object):
    # ===========================================
    # apis
    # ===========================================
    def __init__(self, queue, loop=None):
        self.__queue = queue
        self.__loop = loop if loop else asyncio.new_event_loop()

        self.__running = True
        self.__should_register_event = asyncio.Event()
        self.__should_register_event.clear()

    def start(self):
        t = threading.Thread(target=self.__run_loop, args=(), daemon=True)
        t.start()
        logger.info("Registrar thread started.")

    def stop(self):
        self.__running = False
        self.__should_register_event.clear()

    # ===========================================
    # internal functions
    # ===========================================
    def __run_loop(self):
        self.__loop.run_until_complete(self.__repeat_register())
        logger.info("Registrar thread stopped.")

    async def __repeat_register(self):
        paths = self.__queue.get()
        logger.info("Received paths from worker: %s", paths)

        master_client = MasterClient(
            Config.singleton().get_master_endpoints(),
            {"reconnect_delay": 1, "ping_interval": 10},
            self.__loop,
        )
        master_client.add_connection_listener(
            event=Event.ON_CONNECTED, callback=self.__on_connected_to_master
        )

        while self.__running:
            try:
                await self.__should_register_event.wait()
                await self.__register_service(master_client)
                await self.__set_routes(paths, master_client)
                self.__should_register_event.clear()
            except Exception as e:
                logger.error("Failed to register: %s", e)
                await asyncio.sleep(1)

        master_client.delete_connection_listener(
            event=Event.ON_CONNECTED, callback=self.__on_connected_to_master
        )
        await master_client.close()

    def __on_connected_to_master(self, *argv, **kwargs):
        self.__should_register_event.set()

    async def __register_service(self, master_client):
        req = protocol_types.register_service_req_t()
        req.http_port = Config.singleton().get_port()
        try:
            rep = await master_client.request(req)
            logger.info("Successfully to register service: %s", rep)
        except Exception as e:
            logger.error("Failed to register service: %s", e)
            raise e

    async def __set_routes(self, paths, master_client):
        req = protocol_types.set_routes_req_t()
        req.paths.extend(paths)
        try:
            rep = await master_client.request(req)
            logger.info("successfully to set routes: %s", rep)
        except Exception as e:
            logger.error("Failed to set routes: %s", e)
            raise e
