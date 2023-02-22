import gunicorn.app.base
from maxwell.config import Config


class Server(gunicorn.app.base.BaseApplication):
    def __init__(self, app):
        config = Config.singleton()
        self.options = {
            "bind": "0.0.0.0:{}".format(config.get_port()),
            "workers": config.get_workers(),
            "proc_name": config.get_proc_name(),
            "logconfig_dict": config.get_log_config(),
            "worker_class": "maxwell.worker.Worker",
            "proxy_allow_ips": "*",
        }
        self.application = app
        super().__init__()

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