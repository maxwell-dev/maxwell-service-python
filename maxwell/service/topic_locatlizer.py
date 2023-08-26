import logging
import maxwell.protocol.maxwell_protocol_pb2 as protocol_types
from async_lru import alru_cache
from .config import Config
from .master_client import MasterClient

logger = logging.getLogger(__name__)


class TopicLocatlizer(object):
    # ===========================================
    # apis
    # ===========================================
    def __init__(self, loop):
        self.__loop = loop

        self.__master_client = MasterClient(
            Config.singleton().get_master_endpoints(),
            {"reconnect_delay": 1, "ping_interval": 10},
            self.__loop,
        )

    def close(self):
        self.__master_client.close()
        self.__master_client = None

    @alru_cache(maxsize=10000, ttl=60 * 60 * 24)
    async def locate(self, topic):
        locate_topic_req = protocol_types.locate_topic_req_t()
        locate_topic_req.topic = topic
        locate_topic_rep = await self.__master_client.request(locate_topic_req)
        return locate_topic_rep.endpoint

    def invalidate(self, topic):
        self.locate.cache_invalidate(topic)
