from typing import Any, Dict
from uvicorn.workers import UvicornWorker
from .config import Config


class Worker(UvicornWorker):
    CONFIG_KWARGS: Dict[str, Any] = {
        "loop": "uvloop",
        "http": "httptools",
        "ws": "websockets",
        "ws_max_size": 134217728,
        "ws_ping_interval": None,
        "ws_ping_timeout": None,
        "lifespan": "on",
        "interface": "asgi3",
        "log_config": Config.singleton().get_log_config(),
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super(Worker, self).__init__(*args, **kwargs)
