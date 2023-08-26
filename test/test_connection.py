import logging
import pytest
from maxwell.service.connection import Connection
import maxwell.protocol.maxwell_protocol_pb2 as protocol_types
import maxwell.protocol.maxwell_protocol as protocol

logger = logging.getLogger(__name__)


class TestConfig:
    @pytest.mark.asyncio
    async def test_all(self):
        conn = Connection(
            endpoint="localhost:8081",
        )
        await conn.wait_open()
        msg = protocol_types.ping_req_t()
        reply = await conn.request(msg)
        await conn.close()
        print(reply)
