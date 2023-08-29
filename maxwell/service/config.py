import multiprocessing
import os
import re
import socket
import traceback
import logging
import json
import tomli
from distutils.sysconfig import get_python_lib

logger = logging.getLogger(__name__)


class Config:
    __instance = None

    @staticmethod
    def singleton():
        if Config.__instance == None:
            Config.__instance = Config()
        return Config.__instance

    def __init__(self):
        self.__server_config = self.__build_server_config()
        self.__log_config = self.__build_log_config()

    def get_port(self):
        port = self.__server_config.get("port")
        if port is None:
            port = self.__get_unused_port()
            self.__server_config["port"] = port
            self.__save_port_to_config_file(port)
        return port

    def get_workers(self):
        workers = self.__server_config.get("workers")
        if workers is None or workers == -1:
            return multiprocessing.cpu_count() * 2 + 1
        else:
            return workers

    def get_proc_name(self):
        proc_name = self.__server_config.get("proc_name")
        if proc_name is None:
            return "maxwell-server-python"
        else:
            return proc_name

    def get_master_endpoints(self):
        master_endpoints = self.__server_config.get("master_endpoints")
        if master_endpoints is None:
            raise "Please specify master_endpoints in server.toml"
        else:
            return master_endpoints

    def get_log_config(self):
        return self.__log_config

    def __build_server_config(self):
        config_path = self.__get_server_config_file()
        if os.path.exists(config_path):
            with open(config_path, "rb") as f:
                return tomli.load(f)
        else:
            return {}

    def __get_server_config_file(self):
        specified_config_file = os.getenv("SERVER_CFG_FILE", None)
        if specified_config_file:
            config_file = specified_config_file
        else:
            config_file = os.path.join(self.__get_root_dir(), "config", "service.toml")
        return config_file

    def __build_log_config(self):
        config_path = self.__get_log_config_file()
        if os.path.exists(config_path):
            with open(config_path, "rt") as config_file:
                config = json.load(config_file)
                log_dir = self.__get_log_dir()
                for handler in config["handlers"].values():
                    if "filename" in handler:
                        handler["filename"] = os.path.join(log_dir, handler["filename"])
                return config
        else:
            return None

    def __get_log_config_file(self):
        specified_config_file = os.getenv("LOG_CFG_FILE", None)
        if specified_config_file:
            config_file = specified_config_file
        else:
            config_file = os.path.join(self.__get_root_dir(), "config", "logging.json")
        return config_file

    def __get_root_dir(self):
        root_dir = os.path.abspath(
            os.path.join(get_python_lib(), "..", "..", "..", "..")
        )
        return root_dir

    def __get_log_dir(self):
        return os.path.join(self.__get_root_dir(), "log")

    def __get_unused_port(self):
        # Implement this function instead of using portpicker to be compatiable with proxy chains
        attempt = 1024
        while attempt > 0:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("localhost", 0))
                    _, port = s.getsockname()
                    return port
            except Exception:
                logger.warning("Error occurred: %s", traceback.format_exc())
                attempt -= 1
        raise ValueError("Cannot find unused port")

    def __save_port_to_config_file(self, port):
        try:
            config_path = self.__get_server_config_file()
            append_string = f"port = {port}\n"
            with open(config_path, "r+") as file:
                content = file.read()
                if not re.search(r"^port", content, re.MULTILINE):
                    file.write(append_string + "\n")
                    logger.info(f"Writed new port: %s", port)
                else:
                    logger.info(f"Ignored, as port already exists: %s", port)
        except Exception:
            logger.warning("Error occurred: %s", traceback.format_exc())
