import logging
import maxwell.protocol.maxwell_protocol_pb2 as protocol_types
from .connection import Connection

logger = logging.getLogger(__name__)


class MasterClient(object):
    __instance = None

    # ===========================================
    # apis
    # ===========================================
    def __init__(self, endpoints, options, loop):
        self.__endpoints = endpoints
        self.__options = options
        self.__loop = loop

        self.__endpoint_index = -1
        self.__connection = Connection(
            endpoint=self.__next_endpoint, options=self.__options, loop=self.__loop
        )

    def __del__(self):
        self.close()

    @staticmethod
    def singleton(endpoints, options, loop):
        if MasterClient.__instance == None:
            MasterClient.__instance = MasterClient(endpoints, options, loop)
        return MasterClient.__instance

    def close(self):
        self.__connection.close()
        self.__connection = None

    def add_connection_listener(self, event, callback):
        self.__connection.add_listener(event, callback)

    def delete_connection_listener(self, event, callback):
        self.__connection.delete_listener(event, callback)

    async def request(self, msg):
        await self.__connection.wait_open()
        return await self.__connection.request(msg)

    # ===========================================
    # internal functions
    # ===========================================
    def __next_endpoint(self):
        self.__endpoint_index += 1
        if self.__endpoint_index >= len(self.__endpoints):
            self.__endpoint_index = 0
        return self.__endpoints[self.__endpoint_index]
