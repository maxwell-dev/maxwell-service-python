import argparse
import sys
import setproctitle
import uvicorn
from maxwell.utils.logger import get_logger

from .config import Config
from .registrar import Registrar

logger = get_logger(__name__)


class Server(object):
    def __init__(self, service_ref):
        self.__service_ref = service_ref
        [module_name, service_name] = service_ref.split(":")
        service = getattr(sys.modules[module_name], service_name)
        self.__registrar = Registrar(service)

    def run(self):
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--reload", action="store_true", help="Reload service on file changes."
        )
        args = vars(parser.parse_args())

        setproctitle.setproctitle(Config.singleton().get_proc_name())

        self.__registrar.start()
        uvicorn.run(
            self.__service_ref,
            host="0.0.0.0",
            port=Config.singleton().get_port(),
            loop="uvloop",
            http="httptools",
            ws="websockets",
            ws_max_size=134217728,
            ws_ping_interval=None,
            ws_ping_timeout=None,
            lifespan="on",
            interface="asgi3",
            log_level="info",
            reload=args["reload"],
            log_config=Config.singleton().get_log_config(),
        )
        self.__registrar.stop()
