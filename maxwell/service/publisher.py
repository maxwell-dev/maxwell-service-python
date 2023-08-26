import random
import logging
import maxwell.protocol.maxwell_protocol_pb2 as protocol_types

from .config import Config
from .connection import Code, Event, Connection
from .topic_locatlizer import TopicLocatlizer

logger = logging.getLogger(__name__)


class Publisher(object):
    # ===========================================
    # apis
    # ===========================================
    def __init__(self, options, loop):
        self.__options = options
        self.__loop = loop

        self.__topic_locatlizer = TopicLocatlizer(self.__loop)
        self.__connections = {}  # endpoint => [connection0, connection1, ...]

    def __del__(self):
        self.close()

    def close(self):
        for connections in self.__connections.values():
            for connection in connections:
                connection.close()

    async def publish(self, topic, value):
        connection = await self.__get_connetion(topic)
        await connection.wait_open()
        await connection.request(self.__build_publish_req(topic, value))

    # ===========================================
    # internal functions
    # ===========================================

    async def __get_connetion(self, topic):
        endpoint = await self.__topic_locatlizer.locate(topic)
        connections = self.__connections.get(endpoint)
        if connections is None:
            connections = []
            for _ in range(3):
                connections.append(Connection(endpoint, self.__options, self.__loop))
            self.__connections[endpoint] = connections
        return connections[random.randint(0, 2)]

    def __build_publish_req(self, topic, value):
        push_req = protocol_types.push_req_t()
        push_req.topic = topic
        push_req.value = value
        return push_req
