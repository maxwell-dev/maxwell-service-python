import asyncio
import logging
import threading
import gunicorn.app.base
from multiprocessing import Queue, Value
from ctypes import c_bool
import time

from .config import Config
from .hooks import Hooks
from .registrar import Registrar

logger = logging.getLogger(__name__)


class Server(gunicorn.app.base.BaseApplication):
    def __init__(self, service, hooks=None):
        config = Config.singleton()
        hooks = hooks or Hooks()

        self.options = {
            "bind": ["0.0.0.0:{}".format(config.get_port())],
            "workers": config.get_workers(),
            "proc_name": config.get_proc_name(),
            "logconfig_dict": config.get_log_config(),
            "worker_class": "maxwell.service.worker.Worker",
            "proxy_allow_ips": "*",
            "post_worker_init": self.__post_worker_init,
            "post_fork": self.__post_fork,
            "worker_exit": self.__worker_exit,
            "when_ready": self.__when_ready,
            "on_exit": self.__on_exit,
        }
        self.application = service
        super().__init__()

        self.__service = service
        self.__hooks = hooks
        self.__queue = Queue()
        self.__is_first_registered_service = Value(c_bool, True)
        self.__registrar = None

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

    def __post_worker_init(self, worker):
        def wait_service_to_register():
            while True:
                if self.__service.is_registered():
                    logger.info("[2] post_service_init: worker: %s", worker)
                    self.__hooks.post_service_init(worker)

                    with self.__is_first_registered_service.get_lock():
                        if self.__is_first_registered_service.value is True:
                            self.__is_first_registered_service.value = False
                            paths = self.__service.get_paths()
                            logger.info("Sending paths to registrar: %s", paths)
                            self.__queue.put(paths)

                    break

                time.sleep(0.1)

        t = threading.Thread(target=wait_service_to_register, args=(), daemon=True)
        t.start()

    def __post_fork(self, server, worker):
        logger.info("[1] post_worker_fork: server: %s, worker: %s", server, worker)
        self.__hooks.post_worker_fork(server, worker)

    def __worker_exit(self, server, worker):
        logger.info("[3] post_worker_exit: server: %s, worker: %s", server, worker)
        self.__hooks.post_worker_exit(server, worker)

    def __when_ready(self, server):
        logger.info("[0] Server started: server: %s", server)
        if self.__registrar is None:
            self.__registrar = Registrar(queue=self.__queue)
            self.__registrar.start()
        pass

    def __on_exit(self, server):
        logger.info("[N] Server exit: server: %s", server)
        if self.__registrar is not None:
            self.__registrar.stop()
        pass
