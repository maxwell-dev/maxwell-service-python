from async_lru import alru_cache
import maxwell.protocol.maxwell_protocol_pb2 as protocol_types
from maxwell.utils.connection import Event
from maxwell.utils.logger import get_logger

from .config import Config
from .master_client import MasterClient

logger = get_logger(__name__)


class TopicLocatlizer(object):
    # ===========================================
    # apis
    # ===========================================
    def __init__(self, loop):
        self.__loop = loop

        self.__checksum = 0
        self.__master_client = MasterClient(
            Config.singleton().get_master_endpoints(),
            {"reconnect_delay": 1, "ping_interval": 10},
            self.__loop,
        )
        self.__master_client.add_connection_listener(
            Event.ON_CONNECTED, self.__on_connected_to_master
        )

    async def close(self):
        self.__master_client.delete_connection_listener(
            Event.ON_CONNECTED, self.__on_connected_to_master
        )
        await self.__master_client.close()
        self.locate.cache_clear()
        await self.locate.cache_close()

    @alru_cache(
        maxsize=Config.singleton().get_endpoint_cache_size(),
        ttl=Config.singleton().get_endpoint_cache_ttl(),
    )
    async def locate(self, topic):
        req = protocol_types.locate_topic_req_t()
        req.topic = topic
        rep = await self.__master_client.request(req)
        return rep.endpoint

    # ===========================================
    # internal functions
    # ===========================================
    def __on_connected_to_master(self, *argv, **kwargs):
        self.__loop.create_task(self.__check())

    async def __check(self):
        req = protocol_types.get_topic_dist_checksum_req_t()
        logger.info("Getting TopicDistChecksum: req: %s", req)
        try:
            rep = await self.__master_client.request(req)
            logger.info("Successfully to get TopicDistChecksum: rep: %s", rep)
        except Exception as e:
            logger.error("Failed to get TopicDistChecksum: %s", e)
            return

        if self.__checksum != rep.checksum:
            logger.info(
                "TopicDistChecksum has changed: local: %s, remote: %s, clear cache...",
                self.__checksum,
                rep.checksum,
            )
            self.__checksum = rep.checksum
            self.locate.cache_clear()
        else:
            logger.info(
                "TopicDistChecksum stays the same: local: %s, remote: %s, do nothing.",
                self.__checksum,
                rep.checksum,
            )
