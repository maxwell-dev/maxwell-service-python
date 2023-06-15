import asyncio
import logging
import gunicorn.app.base
from .config import Config
from .reporter import Reporter

logger = logging.getLogger(__name__)


class Server(gunicorn.app.base.BaseApplication):
    def __init__(self, app):
        config = Config.singleton()
        self.options = {
            "bind": ["0.0.0.0:{}".format(config.get_port()), "0.0.0.0:2021"],
            "workers": config.get_workers(),
            "proc_name": config.get_proc_name(),
            "logconfig_dict": config.get_log_config(),
            "worker_class": "maxwell.server.worker.Worker",
            "proxy_allow_ips": "*",
            "reuse_port": True,
            "when_ready": self.__on_started,
            "on_exit": self.__on_exit,
        }
        self.application = app
        super().__init__()

        self.__app = app
        self.__loop = asyncio.get_event_loop()

        self.__reporter = Reporter(self.__app, self.__loop)

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

    def __on_started(self, _server):
        self.__reporter.start()

    def __on_exit(self, _server):
        self.__reporter.stop()
