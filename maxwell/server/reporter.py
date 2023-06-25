import asyncio
import logging
import threading
import traceback
import maxwell.protocol.maxwell_protocol_pb2 as protocol_types
from .connection import Event
from .config import Config
from .master_client import MasterClient

logger = logging.getLogger(__name__)


class Reporter(object):
    # ===========================================
    # apis
    # ===========================================
    def __init__(self, app, loop):
        self.__app = app
        self.__loop = loop

        self.__master_client = None
        self.__running = True
        self.__should_report_event = asyncio.Event()
        self.__should_report_event.clear()

    def start(self):
        t = threading.Thread(target=self.__run_loop, args=(), daemon=True)
        t.start()
        logger.info("Reporter thread started.")

    def stop(self):
        self.__running = False
        self.__should_report_event.clear()

    def __run_loop(self):
        self.__loop.run_until_complete(self.__repeat_report())
        logger.info("Reporter thread stopped.")

    async def __repeat_report(self):
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
                await self.__register_server()
                await self.__add_routes()
                self.__should_report_event.clear()
            except Exception:
                logger.error("Failed to report: %s", traceback.format_exc())
                await asyncio.sleep(1)

        await self.__master_client.close()

    def __on_connected(self):
        self.__should_report_event.set()

    async def __register_server(self):
        req = protocol_types.register_server_req_t()
        req.http_port = Config.singleton().get_port()
        _ = await self.__master_client.request(req)
        logger.info("Registered server successfully!")

    async def __add_routes(self):
        ws_routes = {}
        for path, handler in self.__app.get_ws_routes().items():
            ws_routes[path] = handler[0]
        req = protocol_types.add_routes_req_t()
        req.paths.extend(ws_routes)
        _ = await self.__master_client.request(req)
        logger.info("Added routes successfully!")
