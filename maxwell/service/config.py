import os
import re
import socket
import json
import tomli
import sysconfig
from maxwell.utils.logger import get_logger

logger = get_logger(__name__)


class Config:
    __instance = None

    # ===========================================
    # apis
    # ===========================================
    def __init__(self):
        self.__service_config = self.__build_service_config()
        self.__log_config = self.__build_log_config()

    @staticmethod
    def singleton():
        if Config.__instance == None:
            Config.__instance = Config()
        return Config.__instance

    def get_port(self):
        port = self.__service_config.get("port")
        if port is None:
            port = self.__get_unused_port()
            self.__service_config["port"] = port
            self.__save_port_to_config_file(port)
        return port

    def get_set_routes_delay(self):
        set_routes_delay = self.__service_config.get("set_routes_delay")
        if set_routes_delay is None or set_routes_delay < 0:
            return 2
        else:
            return set_routes_delay

    def get_proc_name(self):
        proc_name = self.__service_config.get("proc_name")
        if proc_name is None:
            return "maxwell-service-python"
        else:
            return proc_name

    def get_master_endpoints(self):
        master_endpoints = self.__service_config.get("master_endpoints")
        if master_endpoints is None:
            raise "Please specify master_endpoints in service.toml"
        else:
            return master_endpoints

    def get_connection_slot_size(self):
        connection_slot_size = self.__service_config.get("connection_slot_size")
        if connection_slot_size is None:
            return 8
        else:
            return connection_slot_size

    def get_endpoint_cache_size(self):
        endpoint_cache_size = self.__service_config.get("endpoint_cache_size")
        if endpoint_cache_size is None:
            return 20480
        else:
            return endpoint_cache_size

    def get_endpoint_cache_ttl(self):
        endpoint_cache_ttl = self.__service_config.get("endpoint_cache_ttl")
        if endpoint_cache_ttl is None:
            return 60 * 60 * 24
        else:
            return endpoint_cache_ttl

    def get_max_continuous_disconnected_times(self):
        max_continuous_disconnected_times = self.__service_config.get(
            "max_continuous_disconnected_times"
        )
        if max_continuous_disconnected_times is None:
            return 30
        else:
            return max_continuous_disconnected_times

    def get_log_config(self):
        return self.__log_config

    # ===========================================
    # internal functions
    # ===========================================
    def __build_service_config(self):
        config_path = self.__get_service_config_file()
        if os.path.exists(config_path):
            with open(config_path, "rb") as f:
                return tomli.load(f)
        else:
            return {}

    def __get_service_config_file(self):
        specified_config_file = os.getenv("SERVICE_CFG_FILE", None)
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
            os.path.join(sysconfig.get_path("purelib"), "..", "..", "..", "..")
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
            except Exception as e:
                logger.warning("Error occurred: %s", e)
                attempt -= 1
        raise LookupError("Failed to find unused port.")

    def __save_port_to_config_file(self, port):
        try:
            config_path = self.__get_service_config_file()
            append_string = f"port = {port}\n"
            with open(config_path, "r+") as file:
                content = file.read()
                if not re.search(r"^port", content, re.MULTILINE):
                    file.write(append_string + "\n")
                    logger.info(f"Writed new port: %s", port)
                else:
                    logger.info(f"Ignored, as port already exists: %s", port)
        except Exception as e:
            logger.warning("Error occurred: %s", e)
