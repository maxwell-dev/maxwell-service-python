import asyncio
import logging
import threading
import traceback
import maxwell.protocol.maxwell_protocol_pb2 as protocol_types
from .connection import Event
from .config import Config
from .master_client import MasterClient

logger = logging.getLogger(__name__)


class Registrar(object):
    # ===========================================
    # apis
    # ===========================================
    def __init__(self, queue, loop=None):
        self.__queue = queue
        self.__loop = loop if loop else asyncio.new_event_loop()

        self.__master_client = None
        self.__running = True
        self.__should_report_event = asyncio.Event()
        self.__should_report_event.clear()

    def start(self):
        t = threading.Thread(target=self.__run_loop, args=(), daemon=True)
        t.start()
        logger.info("Registrar thread started.")

    def stop(self):
        self.__running = False
        self.__should_report_event.clear()

    def __run_loop(self):
        self.__loop.run_until_complete(self.__repeat_report())
        logger.info("Registrar thread stopped.")

    async def __repeat_report(self):
        paths = self.__queue.get()
        logger.info("Received paths from worker: %s", paths)

        self.__master_client = MasterClient(
            Config.singleton().get_master_endpoints(),
            {"reconnect_delay": 1, "ping_interval": 10},
            self.__loop,
        )
        self.__master_client.add_connection_listener(
            event=Event.ON_CONNECTED, callback=self.__on_connected
        )

        while self.__running:
            try:
                await self.__should_report_event.wait()
                await self.__register_service()
                await self.__set_routes(paths)
                self.__should_report_event.clear()
            except Exception:
                logger.error("Failed to report: %s", traceback.format_exc())
                await asyncio.sleep(1)

        await self.__master_client.close()

    def __on_connected(self):
        self.__should_report_event.set()

    async def __register_service(self):
        req = protocol_types.register_service_req_t()
        req.http_port = Config.singleton().get_port()
        _ = await self.__master_client.request(req)
        logger.info("Registered service successfully!")

    async def __set_routes(self, paths):
        req = protocol_types.set_routes_req_t()
        req.paths.extend(paths)
        _ = await self.__master_client.request(req)
        logger.info("Set routes successfully!")
