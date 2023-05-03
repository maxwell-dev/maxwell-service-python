import asyncio
import logging
import traceback
import threading
import gunicorn.app.base
import maxwell.protocol.maxwell_protocol_pb2 as protocol_types
from .config import Config
from .connection import Connection
from .connection import Event


logger = logging.getLogger(__name__)


class Server(gunicorn.app.base.BaseApplication):
    def __init__(self, app):
        config = Config.singleton()
        self.options = {
            "bind": "0.0.0.0:{}".format(config.get_port()),
            "workers": config.get_workers(),
            "proc_name": config.get_proc_name(),
            "logconfig_dict": config.get_log_config(),
            "worker_class": "maxwell.server.worker.Worker",
            "proxy_allow_ips": "*",
            "when_ready": self.__on_started,
            "on_exit": self.__on_exit,
        }
        self.application = app
        super().__init__()

        self.__app = app
        self.__loop = asyncio.get_event_loop()
        self.__running = True
        self.__should_report_event = asyncio.Event()
        self.__should_report_event.clear()

    def load_config(self):
        config = {
            key: value
            for key, value in self.options.items()
            if key in self.cfg.settings and value is not None
        }
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application

    def __on_started(self, server):
        t = threading.Thread(target=self.__run_loop, args=(self.__loop,), daemon=True)
        t.start()
        logger.info("Report thread started.")

    def __on_exit(self, server):
        self.__running = False

    def __run_loop(self, loop):
        loop.run_until_complete(self.__repeat_report())
        loop.close()
        logger.info("Report thread stopped.")

    async def __repeat_report(self):
        conn = Connection(endpoint="localhost:8081", loop=self.__loop)
        conn.add_listener(event=Event.ON_CONNECTED, callback=self.__on_connected)

        while self.__running:
            try:
                await self.__should_report_event.wait()
                req = protocol_types.register_server_req_t()
                req.http_port = Config.singleton().get_port()
                _ = await conn.request(req)
                logger.info("Registered server successfully!")
                req = protocol_types.add_routes_req_t()
                req.paths.extend(self.__app.get_ws_routes())
                _ = await conn.request(req)
                logger.info("Added routes successfully!")
                self.__should_report_event.clear()
            except Exception:
                logger.error("Failed to report: %s", traceback.format_exc())
                await asyncio.sleep(1)

        await conn.close()

    def __on_connected(self):
        self.__should_report_event.set()
