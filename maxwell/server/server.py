import asyncio
import logging
import gunicorn.app.base

from .hooks import Hooks
from .config import Config
from .reporter import Reporter

logger = logging.getLogger(__name__)


class Server(gunicorn.app.base.BaseApplication):
    def __init__(self, app, hooks=None):
        config = Config.singleton()
        hooks = hooks or Hooks()

        self.options = {
            "bind": ["0.0.0.0:{}".format(config.get_port())],
            "workers": config.get_workers(),
            "proc_name": config.get_proc_name(),
            "logconfig_dict": config.get_log_config(),
            "worker_class": "maxwell.server.worker.Worker",
            "proxy_allow_ips": "*",
            "when_ready": self.__on_started,
            "on_exit": self.__on_exit,
            "post_worker_init": hooks.post_app_init,
            "post_fork": hooks.post_worker_fork,
            "worker_exit": hooks.post_worker_exit,
        }
        self.application = app
        super().__init__()

        self.__hooks = hooks
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
